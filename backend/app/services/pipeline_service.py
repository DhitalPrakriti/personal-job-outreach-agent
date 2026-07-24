"""Database-backed service for the personal outreach workflow."""

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.company_research import CompanyResearchAgent
from app.agents.contact_finder import ContactFinderAgent
from app.agents.draft_qa import DraftQAAgent
from app.agents.email_inbox import EmailInboxAgent
from app.agents.email_sender import EmailSenderAgent
from app.agents.reply_classifier import ReplyClassifierAgent
from app.db.models import (
    AuditEventModel,
    ApplicationModel,
    CampaignModel,
    CareerSourceModel,
    ContactResearchModel,
    EmailDraftModel,
    EmailReplyModel,
    LeadModel,
    ProfileSettingsModel,
)
from app.schemas.pipeline import (
    ApplicationCreate,
    ApplicationStatus,
    ApplicationUpdate,
    AuditAction,
    CampaignCreate,
    CampaignStatus,
    CareerSourceCreate,
    CareerSourceScanRequest,
    CareerSourceUpdate,
    DraftCreate,
    DraftGenerateRequest,
    DraftQueueGenerateRequest,
    DraftStatus,
    DraftUpdate,
    FollowUpQueueGenerateRequest,
    JobDiscoveryImportRequest,
    JobDiscoveryItem,
    JobSourceDiscoveryRequest,
    LeadCreate,
    LeadContactUpdate,
    LeadStatus,
    PipelineBatchRunRequest,
    PipelineStage,
    ProfileSettings,
    ProfileSettingsUpdate,
    ReplyClassifyRequest,
)
from app.services.ai_draft_service import AIDraftService
from app.services.job_source_discovery import JobSourceDiscoveryService


class QueueResult:
    def __init__(self) -> None:
        self.scanned = 0
        self.created = 0
        self.skipped = 0
        self.drafts: list[EmailDraftModel] = []


class ReplySyncServiceResult:
    def __init__(self) -> None:
        self.fetched = 0
        self.matched = 0
        self.imported = 0
        self.skipped = 0
        self.replies: list[EmailReplyModel] = []


class DuplicateCareerSourceError(ValueError):
    """Raised when a company career source URL is already saved."""


class JobDiscoveryResult:
    def __init__(self) -> None:
        self.imported = 0
        self.skipped = 0
        self.leads: list[LeadModel] = []


DEFAULT_TARGET_ROLES = [
    "Junior AI Engineer",
    "AI Engineer",
    "Backend Developer",
    "Software Developer",
    "Web Developer",
    "Full Stack Developer",
    "Frontend Developer",
    "Python Developer",
    "Junior Developer",
    "IT Support",
    "QA Analyst",
    "Automation Developer",
]

DEFAULT_TARGET_LOCATIONS = [
    "Canada",
    "Remote Canada",
    "Vancouver",
    "British Columbia",
    "Alberta",
    "Calgary",
    "Edmonton",
    "Saskatchewan",
    "Saskatoon",
    "Regina",
    "Ontario",
    "Toronto",
    "Ottawa",
    "Quebec",
    "Montreal",
    "Manitoba",
    "Winnipeg",
    "Nova Scotia",
    "Halifax",
]

DEFAULT_TARGET_SKILLS = [
    "Python",
    "FastAPI",
    "React",
    "JavaScript",
    "TypeScript",
    "Node.js",
    "SQL",
    "PostgreSQL",
    "REST API",
    "HTML",
    "CSS",
    "LLM",
    "AI",
    "Automation",
    "Git",
    "Docker",
    "Cloud",
    "GCP",
]


class PipelineService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_lead(self, payload: LeadCreate) -> LeadModel:
        data = payload.model_dump()
        if not data.get("outreach_status"):
            data["outreach_status"] = PipelineStage.CONTACT_FOUND if data.get("email") else PipelineStage.DISCOVERED
        lead = LeadModel(status=LeadStatus.NEW, **data)
        self.session.add(lead)
        await self.session.flush()
        self._audit(AuditAction.LEAD_CREATED, "contact", lead.id, self._lead_summary("Contact created", lead))
        await self.session.commit()
        await self.session.refresh(lead)
        return lead

    async def create_leads(self, payloads: list[LeadCreate]) -> list[LeadModel]:
        leads = []
        for payload in payloads:
            data = payload.model_dump()
            if not data.get("outreach_status"):
                data["outreach_status"] = PipelineStage.CONTACT_FOUND if data.get("email") else PipelineStage.DISCOVERED
            leads.append(LeadModel(status=LeadStatus.NEW, **data))
        self.session.add_all(leads)
        await self.session.flush()
        for lead in leads:
            self._audit(AuditAction.LEAD_CREATED, "contact", lead.id, self._lead_summary("Contact created", lead))
        await self.session.commit()
        for lead in leads:
            await self.session.refresh(lead)
        return leads

    async def import_discovered_jobs(self, payload: JobDiscoveryImportRequest) -> JobDiscoveryResult:
        result = JobDiscoveryResult()
        for item in payload.jobs:
            score, score_notes = self._score_discovered_job(payload, item)
            duplicate = await self._find_existing_job_target(
                company=item.company,
                title=item.title,
                url=item.url,
            )
            if duplicate is not None:
                if self._apply_duplicate_job_update(duplicate, item, score, score_notes):
                    self._audit(
                        AuditAction.OPPORTUNITY_IMPORTED,
                        "job_opportunity",
                        duplicate.id,
                        self._lead_summary("Duplicate opportunity updated with better import details for", duplicate),
                    )
                    result.imported += 1
                    result.leads.append(duplicate)
                    continue
                result.skipped += 1
                continue

            source = self._normalized_source(item.source)
            tracked_contact_name = item.contact_name
            tracked_contact_url = item.contact_url
            has_tracked_contact = bool(item.contact_email or tracked_contact_name or tracked_contact_url)
            contact_name = tracked_contact_name or "Hiring Team"
            priority = self._priority_from_score(score)
            note_parts = [
                f"Fit score: {score}/100.",
                f"Score basis: {score_notes}.",
            ]
            if item.notes:
                note_parts.append(f"Notes: {item.notes}")
            if item.location:
                note_parts.append(f"Location: {item.location}.")
            if item.url:
                note_parts.append(f"Job URL: {item.url}.")
            if tracked_contact_url:
                note_parts.append(f"Recruiter/contact URL: {tracked_contact_url}.")
            if tracked_contact_name:
                note_parts.append(f"Recruiter/contact name: {tracked_contact_name}.")
            if item.description:
                note_parts.append(f"Description: {item.description}")
            if item.company_summary:
                note_parts.append(f"Company summary: {item.company_summary}")
            if item.tech_stack:
                note_parts.append(f"Tech stack: {item.tech_stack}")
            if item.role_fit:
                note_parts.append(f"Role fit: {item.role_fit}")
            if item.source_links:
                note_parts.append(f"Source links: {item.source_links}")

            source_context = [
                f"{item.title} at {item.company}",
                f"fit score {score}/100",
                score_notes,
            ]
            if item.company_summary:
                source_context.append(f"company: {item.company_summary}")
            if item.tech_stack:
                source_context.append(f"tech stack: {item.tech_stack}")
            if item.role_fit:
                source_context.append(f"role fit: {item.role_fit}")

            lead = LeadModel(
                email=str(item.contact_email) if item.contact_email else None,
                first_name=contact_name,
                last_name=None,
                company=item.company,
                title=item.title,
                source=source,
                notes=" ".join(note_parts)[:2000],
                linkedin_url=item.url,
                lead_grade=priority,
                outreach_status=PipelineStage.CONTACT_FOUND if has_tracked_contact else PipelineStage.ANALYZED,
                suggested_first_message=". ".join(source_context)[:5000],
                opportunity_url=item.url,
                opportunity_location=item.location,
                opportunity_description=item.description,
                company_summary=item.company_summary,
                tech_stack=item.tech_stack,
                role_fit=item.role_fit,
                source_links=item.source_links,
                fit_score=score,
                contact_name=tracked_contact_name if has_tracked_contact else None,
                contact_role="Recruiter / Hiring Manager" if has_tracked_contact else None,
                contact_type=self._contact_type_for_import(item) if has_tracked_contact else None,
                contact_source_url=tracked_contact_url or (item.url if item.contact_email else None),
                contact_confidence_score=self._contact_confidence_for_import(item) if has_tracked_contact else None,
                contact_verification_status=self._contact_verification_for_import(item) if has_tracked_contact else None,
                status=LeadStatus.NEW,
            )
            self.session.add(lead)
            await self.session.flush()
            if has_tracked_contact:
                contact_research = self._contact_research_from_import(lead, item)
                self.session.add(contact_research)
                self._audit(
                    AuditAction.CONTACT_SEARCHED,
                    "contact_research",
                    lead.id,
                    f"Contact research created from {source} manual tracker input",
                )
            self._audit(
                AuditAction.OPPORTUNITY_IMPORTED,
                "job_opportunity",
                lead.id,
                self._lead_summary(f"Discovered job imported with fit score {score}", lead),
            )
            self._audit(
                AuditAction.OPPORTUNITY_ANALYZED,
                "job_opportunity",
                lead.id,
                f"Opportunity analyzed with fit score {score}/100: {score_notes}",
            )
            result.imported += 1
            result.leads.append(lead)

        await self.session.commit()
        for lead in result.leads:
            await self.session.refresh(lead)
        return result

    def _apply_duplicate_job_update(
        self,
        duplicate: LeadModel,
        item: JobDiscoveryItem,
        score: int,
        score_notes: str,
    ) -> bool:
        changed = False
        placeholder_companies = {"Company from pasted job", "Unknown Company"}
        placeholder_titles = {
            "Indeed Job Opportunity",
            "LinkedIn Job Opportunity",
            "Glassdoor Job Opportunity",
            "Job Opportunity",
            "Open role",
        }

        if item.company and (not duplicate.company or duplicate.company in placeholder_companies):
            duplicate.company = item.company
            changed = True
        if item.title and (not duplicate.title or duplicate.title in placeholder_titles):
            duplicate.title = item.title
            changed = True
        if item.location and not duplicate.opportunity_location:
            duplicate.opportunity_location = item.location
            changed = True
        if item.description and not duplicate.opportunity_description:
            duplicate.opportunity_description = item.description
            changed = True
        if item.company_summary and not duplicate.company_summary:
            duplicate.company_summary = item.company_summary
            changed = True
        if item.tech_stack and not duplicate.tech_stack:
            duplicate.tech_stack = item.tech_stack
            changed = True
        if item.role_fit and (
            not duplicate.role_fit
            or "Needs review" in duplicate.role_fit
            or "Needs review" in (duplicate.suggested_first_message or "")
        ):
            duplicate.role_fit = item.role_fit
            changed = True
        if item.notes and ("Paste the job description later" in (duplicate.notes or "")):
            duplicate.notes = item.notes
            changed = True

        if changed:
            duplicate.fit_score = score
            duplicate.lead_grade = self._priority_from_score(score)
            duplicate.suggested_first_message = (
                f"{duplicate.title or item.title} at {duplicate.company or item.company}. "
                f"fit score {score}/100. {score_notes}"
            )[:5000]
        return changed

    async def analyze_fit(self, lead_id: UUID) -> LeadModel | None:
        lead = await self.get_lead(lead_id)
        if lead is None:
            return None

        score, score_notes = self._score_discovered_job(
            SimpleNamespace(
                target_roles=DEFAULT_TARGET_ROLES,
                target_locations=DEFAULT_TARGET_LOCATIONS,
                target_skills=DEFAULT_TARGET_SKILLS,
            ),
            SimpleNamespace(
                company=lead.company,
                title=lead.title,
                location=lead.opportunity_location,
                description=lead.opportunity_description,
                company_summary=lead.company_summary,
                tech_stack=lead.tech_stack,
                role_fit=lead.role_fit,
                contact_email=lead.email,
                contact_url=lead.contact_source_url,
            ),
        )
        lead.fit_score = score
        lead.lead_grade = self._priority_from_score(score)
        lead.role_fit = f"Fit score {score}/100. {score_notes}"
        if lead.outreach_status in {None, PipelineStage.DISCOVERED}:
            lead.outreach_status = PipelineStage.ANALYZED
        lead.suggested_first_message = self._opportunity_message_context(lead)[:5000]
        self._audit(
            AuditAction.OPPORTUNITY_ANALYZED,
            "job_opportunity",
            lead.id,
            f"Opportunity analyzed with fit score {score}/100: {score_notes}",
        )
        await self.session.commit()
        await self.session.refresh(lead)
        return lead

    async def research_company(self, lead_id: UUID) -> LeadModel | None:
        lead = await self.get_lead(lead_id)
        if lead is None:
            return None

        research = await CompanyResearchAgent().research(lead)
        if research.company_summary:
            lead.company_summary = research.company_summary
        if research.tech_stack:
            lead.tech_stack = self._merge_csv_text(lead.tech_stack, research.tech_stack, limit=1000)
        if research.role_fit:
            lead.role_fit = research.role_fit
        if research.source_links:
            lead.source_links = self._merge_lines(lead.source_links, research.source_links, limit=2000)
        lead.outreach_status = PipelineStage.COMPANY_RESEARCHED if not lead.email else PipelineStage.CONTACT_FOUND
        lead.suggested_first_message = research.suggested_context[:5000]
        self._audit(
            AuditAction.COMPANY_RESEARCHED,
            "job_opportunity",
            lead.id,
            self._lead_summary("Company research updated for", lead),
        )
        await self.session.commit()
        await self.session.refresh(lead)
        return lead

    async def find_contact_for_lead(self, lead_id: UUID) -> tuple[LeadModel, bool, list[str]] | None:
        lead = await self.get_lead(lead_id)
        if lead is None:
            return None

        candidate = await ContactFinderAgent().find_for_opportunity(
            company=lead.company,
            job_url=lead.opportunity_url or lead.linkedin_url,
            source_links=lead.source_links,
        )
        lead.contact_name = candidate.contact_name
        lead.contact_role = candidate.contact_role
        lead.contact_type = candidate.contact_type
        lead.contact_source_url = candidate.source_url
        lead.contact_confidence_score = candidate.confidence_score
        lead.contact_verification_status = candidate.verification_status
        if candidate.contact_email:
            lead.email = candidate.contact_email
            lead.first_name = candidate.contact_name or "Recruiting Team"
            lead.outreach_status = PipelineStage.CONTACT_FOUND
        elif candidate.source_url:
            lead.first_name = candidate.contact_name or "Hiring Team"
            lead.linkedin_url = candidate.source_url
            lead.outreach_status = PipelineStage.CONTACT_FOUND if candidate.found else PipelineStage.COMPANY_RESEARCHED
        else:
            lead.first_name = "Hiring Team"
            lead.outreach_status = PipelineStage.COMPANY_RESEARCHED

        evidence_note = " ".join(candidate.evidence)
        if evidence_note:
            lead.notes = self._append_note(lead.notes, f"Contact finder: {evidence_note}")[:2000]
        lead.suggested_first_message = self._opportunity_message_context(lead)[:5000]
        self.session.add(
            ContactResearchModel(
                lead_id=lead.id,
                contact_name=lead.contact_name,
                contact_email=lead.email,
                contact_role=lead.contact_role,
                contact_type=lead.contact_type or "fallback",
                source_url=lead.contact_source_url,
                confidence_score=lead.contact_confidence_score or 0,
                verification_status=lead.contact_verification_status or "not_found",
                notes=evidence_note or None,
            )
        )
        self._audit(
            AuditAction.CONTACT_SEARCHED,
            "job_opportunity",
            lead.id,
            (
                f"Contact search completed for {lead.company or 'opportunity'} "
                f"with status {candidate.verification_status}"
            ),
        )
        await self.session.commit()
        await self.session.refresh(lead)
        return lead, candidate.found, candidate.evidence

    async def list_contact_research(self) -> list[ContactResearchModel]:
        result = await self.session.execute(select(ContactResearchModel).order_by(ContactResearchModel.created_at))
        return list(result.scalars().all())

    async def create_application(self, payload: ApplicationCreate) -> ApplicationModel | None:
        data = payload.model_dump()
        lead = None
        if payload.lead_id is not None:
            lead = await self.get_lead(payload.lead_id)
            if lead is None:
                return None
            data = self._application_data_from_lead(lead, data)

        application = ApplicationModel(**data)
        self.session.add(application)
        await self.session.flush()
        self._sync_lead_from_application(application, lead)
        self._audit(
            AuditAction.APPLICATION_CREATED,
            "application",
            application.id,
            f"Application tracked: {application.job_title} at {application.company_name}",
        )
        await self.session.commit()
        await self.session.refresh(application)
        return application

    async def create_application_from_lead(self, lead_id: UUID) -> ApplicationModel | None:
        lead = await self.get_lead(lead_id)
        if lead is None:
            return None
        existing = await self.get_application_by_lead_id(lead_id)
        if existing is not None:
            return existing
        return await self.create_application(
            ApplicationCreate(
                lead_id=lead.id,
                company_name=lead.company or "Unknown Company",
                job_title=lead.title or "Open role",
                source=self._application_source_from_lead(lead),
                job_url=lead.opportunity_url or lead.linkedin_url,
                location=lead.opportunity_location,
                status=ApplicationStatus.SAVED,
                contact_found=bool(lead.email or lead.contact_source_url),
                notes=lead.notes,
            )
        )

    async def mark_application_applied_from_lead(self, lead_id: UUID, note: str | None = None) -> ApplicationModel | None:
        lead = await self.get_lead(lead_id)
        if lead is None:
            return None
        application = await self.create_application_from_lead(lead_id)
        if application is None:
            return None
        application.status = ApplicationStatus.APPLIED
        application.applied_date = date.today()
        application.contact_found = bool(lead.email or lead.contact_source_url)
        if note:
            application.notes = f"{application.notes or ''}\n\n{note}".strip()[:2000]
        self._sync_lead_from_application(application, lead)
        self._audit(
            AuditAction.APPLICATION_UPDATED,
            "application",
            application.id,
            f"Application marked applied: {application.job_title} at {application.company_name}",
        )
        await self.session.commit()
        await self.session.refresh(application)
        return application

    async def list_applications(self) -> list[ApplicationModel]:
        result = await self.session.execute(select(ApplicationModel).order_by(ApplicationModel.created_at))
        return list(result.scalars().all())

    async def get_application(self, application_id: UUID) -> ApplicationModel | None:
        return await self.session.get(ApplicationModel, application_id)

    async def get_application_by_lead_id(self, lead_id: UUID) -> ApplicationModel | None:
        result = await self.session.execute(
            select(ApplicationModel).where(ApplicationModel.lead_id == lead_id).limit(1)
        )
        return result.scalar_one_or_none()

    async def update_application(
        self,
        application_id: UUID,
        payload: ApplicationUpdate,
    ) -> ApplicationModel | None:
        application = await self.get_application(application_id)
        if application is None:
            return None
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(application, key, value)
        lead = await self.get_lead(application.lead_id) if application.lead_id else None
        self._sync_lead_from_application(application, lead)
        self._audit(
            AuditAction.APPLICATION_UPDATED,
            "application",
            application.id,
            f"Application updated to {application.status}: {application.job_title} at {application.company_name}",
        )
        await self.session.commit()
        await self.session.refresh(application)
        return application

    async def delete_application(self, application_id: UUID) -> bool:
        application = await self.get_application(application_id)
        if application is None:
            return False
        self._audit(
            AuditAction.APPLICATION_DELETED,
            "application",
            application.id,
            f"Application deleted: {application.job_title} at {application.company_name}",
        )
        await self.session.delete(application)
        await self.session.commit()
        return True

    async def generate_linkedin_connection_message(self, lead_id: UUID) -> str | None:
        lead = await self.get_lead(lead_id)
        if lead is None:
            return None
        company = lead.company or "your team"
        role = lead.title or "the opportunity"
        context = lead.role_fit or lead.company_summary or lead.suggested_first_message or ""
        message = (
            f"Hi {lead.contact_name or lead.first_name}, I came across {role} at {company} "
            "and wanted to connect. My background is in practical AI, backend, and automation work, "
            "and I would appreciate following your updates."
        )
        if "junior" in f"{role} {context}".lower():
            message = (
                f"Hi {lead.contact_name or lead.first_name}, I saw {role} at {company} and wanted to connect. "
                "I am exploring junior AI/backend/software roles and would appreciate following your updates."
            )
        message = message[:300]
        self._audit(
            AuditAction.LINKEDIN_MESSAGE_CREATED,
            "job_opportunity",
            lead.id,
            "LinkedIn connection message generated for manual use only",
        )
        await self.session.commit()
        return message

    async def run_next_opportunity_step(self, lead_id: UUID) -> dict | None:
        lead = await self.get_lead(lead_id)
        if lead is None:
            return None

        stage = str(lead.outreach_status or PipelineStage.DISCOVERED)
        active_draft = await self.get_active_draft_for_lead(lead.id)
        if active_draft is not None:
            return {
                "lead": lead,
                "action": "human_review_required",
                "message": "A draft already exists. Review, edit, approve, or reject it before continuing.",
                "draft": active_draft,
                "requires_human_review": True,
            }

        if stage in {PipelineStage.DISCOVERED, PipelineStage.DISCOVERED.value} or lead.fit_score is None:
            lead = await self.analyze_fit(lead.id)
            return {
                "lead": lead,
                "action": "analyze_fit",
                "message": f"Fit analyzed at {lead.fit_score}/100. Next step: research the company.",
                "draft": None,
                "requires_human_review": False,
            }

        if stage in {PipelineStage.ANALYZED, PipelineStage.ANALYZED.value} or not lead.company_summary:
            lead = await self.research_company(lead.id)
            return {
                "lead": lead,
                "action": "research_company",
                "message": "Company research updated. Next step: search for a public recruiting contact.",
                "draft": None,
                "requires_human_review": False,
            }

        if stage in {PipelineStage.COMPANY_RESEARCHED, PipelineStage.COMPANY_RESEARCHED.value}:
            result = await self.find_contact_for_lead(lead.id)
            if result is None:
                return None
            lead, contact_found, _evidence = result
            message = "Contact found. Next step: generate a Gmail draft." if contact_found else (
                "No public contact found. Kept Hiring Team/source URL fallback for manual review."
            )
            return {
                "lead": lead,
                "action": "find_contact",
                "message": message,
                "draft": None,
                "requires_human_review": False,
            }

        if stage in {PipelineStage.CONTACT_FOUND, PipelineStage.CONTACT_FOUND.value}:
            draft = await self.generate_mock_draft(
                DraftGenerateRequest(
                    lead_id=lead.id,
                    call_to_action="Open to a 15-minute conversation?",
                    extra_context=(
                        "Use the opportunity research, public contact/source context, and Prakriti's profile. "
                        "Keep the message concise, career-focused, and ready for human approval."
                    ),
                )
            )
            refreshed = await self.get_lead(lead.id)
            if refreshed is not None:
                await self.session.refresh(refreshed)
            return {
                "lead": refreshed,
                "action": "generate_draft",
                "message": "Gmail draft created. Human approval is required before sending.",
                "draft": draft,
                "requires_human_review": True,
            }

        return {
            "lead": lead,
            "action": "human_review_required",
            "message": "This opportunity is waiting on human review, approval, sending, reply sync, or follow-up handling.",
            "draft": None,
            "requires_human_review": True,
        }

    async def run_pipeline_batch(self, payload: PipelineBatchRunRequest) -> dict:
        query = select(LeadModel)
        if payload.stages:
            query = query.where(LeadModel.outreach_status.in_([str(stage) for stage in payload.stages]))
        if payload.lead_grades:
            query = query.where(LeadModel.lead_grade.in_(payload.lead_grades))
        query = query.order_by(LeadModel.created_at).limit(payload.limit)
        leads = list((await self.session.execute(query)).scalars().all())

        results = []
        advanced = 0
        skipped = 0
        for lead in leads:
            if not payload.allow_draft_generation and str(lead.outreach_status) == PipelineStage.CONTACT_FOUND.value:
                skipped += 1
                results.append(
                    {
                        "lead": lead,
                        "action": "draft_generation_skipped",
                        "message": "Stopped at CONTACT_FOUND because draft generation is disabled for this batch.",
                        "draft": None,
                        "requires_human_review": True,
                    }
                )
                continue

            result = await self.run_next_opportunity_step(lead.id)
            if result is None:
                skipped += 1
                continue
            if result["action"] in {"human_review_required", "draft_generation_skipped"}:
                skipped += 1
            else:
                advanced += 1
            results.append(result)

        return {
            "scanned": len(leads),
            "advanced": advanced,
            "skipped": skipped,
            "results": results,
        }

    async def list_leads(self) -> list[LeadModel]:
        result = await self.session.execute(select(LeadModel).order_by(LeadModel.created_at))
        return list(result.scalars().all())

    async def get_lead(self, lead_id: UUID) -> LeadModel | None:
        return await self.session.get(LeadModel, lead_id)

    async def update_lead_contact(self, lead_id: UUID, payload: LeadContactUpdate) -> LeadModel | None:
        lead = await self.get_lead(lead_id)
        if lead is None:
            return None

        lead.email = str(payload.email)
        if payload.contact_name:
            lead.contact_name = payload.contact_name
            lead.first_name = payload.contact_name
            lead.last_name = None
        if payload.contact_role:
            lead.contact_role = payload.contact_role
        lead.contact_type = lead.contact_type or "manual_email"
        if payload.contact_source_url:
            lead.contact_source_url = payload.contact_source_url
        lead.contact_confidence_score = max(lead.contact_confidence_score or 0, 80)
        lead.contact_verification_status = "manual_email_added"
        if str(lead.outreach_status or "") in {
            PipelineStage.DISCOVERED.value,
            PipelineStage.ANALYZED.value,
            PipelineStage.COMPANY_RESEARCHED.value,
        }:
            lead.outreach_status = PipelineStage.CONTACT_FOUND
        if payload.note:
            lead.notes = f"{lead.notes or ''} Manual contact note: {payload.note}".strip()[:2000]

        await self._update_application_for_lead(lead.id, status=ApplicationStatus.CONTACT_FOUND)
        self._audit(
            AuditAction.CONTACT_SEARCHED,
            "job_opportunity",
            lead.id,
            f"Manual contact email added for {lead.company or lead.first_name}: {lead.email}",
        )
        await self.session.commit()
        await self.session.refresh(lead)
        return lead

    async def delete_lead(self, lead_id: UUID) -> bool:
        lead = await self.get_lead(lead_id)
        if lead is None:
            return False

        draft_ids = list(
            (
                await self.session.execute(
                    select(EmailDraftModel.id).where(EmailDraftModel.lead_id == lead_id)
                )
            ).scalars().all()
        )
        reply_ids = list(
            (
                await self.session.execute(
                    select(EmailReplyModel.id).where(EmailReplyModel.lead_id == lead_id)
                )
            ).scalars().all()
        )
        audit_entity_ids = [lead_id, *draft_ids, *reply_ids]
        await self.session.execute(
            delete(AuditEventModel).where(AuditEventModel.entity_id.in_(audit_entity_ids))
        )
        await self.session.execute(delete(ApplicationModel).where(ApplicationModel.lead_id == lead_id))
        await self.session.execute(delete(ContactResearchModel).where(ContactResearchModel.lead_id == lead_id))
        await self.session.execute(delete(EmailReplyModel).where(EmailReplyModel.lead_id == lead_id))
        await self.session.execute(delete(EmailDraftModel).where(EmailDraftModel.lead_id == lead_id))
        await self.session.delete(lead)
        await self.session.commit()
        return True

    async def _find_existing_job_target(
        self,
        company: str,
        title: str,
        url: str | None,
    ) -> LeadModel | None:
        if url:
            result = await self.session.execute(
                select(LeadModel).where(
                    (LeadModel.opportunity_url == url) | (LeadModel.linkedin_url == url)
                ).limit(1)
            )
            found = result.scalar_one_or_none()
            if found is not None:
                return found
        result = await self.session.execute(
            select(LeadModel).where(
                LeadModel.company == company,
                LeadModel.title == title,
            ).limit(1)
        )
        return result.scalar_one_or_none()

    async def create_campaign(self, payload: CampaignCreate) -> CampaignModel:
        campaign = CampaignModel(status=CampaignStatus.DRAFT, **payload.model_dump())
        self.session.add(campaign)
        await self.session.flush()
        self._audit(AuditAction.CAMPAIGN_CREATED, "campaign", campaign.id, f"Campaign created: {campaign.name}")
        await self.session.commit()
        await self.session.refresh(campaign)
        return campaign

    async def list_campaigns(self) -> list[CampaignModel]:
        result = await self.session.execute(select(CampaignModel).order_by(CampaignModel.created_at))
        return list(result.scalars().all())

    async def get_campaign(self, campaign_id: UUID) -> CampaignModel | None:
        return await self.session.get(CampaignModel, campaign_id)

    async def create_draft(self, payload: DraftCreate) -> EmailDraftModel | None:
        lead = await self.get_lead(payload.lead_id)
        if lead is None:
            return None
        if payload.campaign_id is not None and await self.get_campaign(payload.campaign_id) is None:
            return None
        qa = await DraftQAAgent().review(payload.subject, payload.body, lead.first_name)
        draft = EmailDraftModel(
            status=DraftStatus.PENDING_APPROVAL,
            qa_status=qa.status,
            qa_notes=qa.notes,
            qa_checked_at=datetime.now(UTC),
            **payload.model_dump(),
        )
        self.session.add(draft)
        await self.session.flush()
        lead.status = LeadStatus.DRAFT_READY
        lead.outreach_status = PipelineStage.PENDING_APPROVAL
        await self._update_application_for_lead(
            lead.id,
            status=ApplicationStatus.OUTREACH_DRAFTED,
        )
        self._audit(AuditAction.DRAFT_CREATED, "email_draft", draft.id, self._lead_summary("Draft created for contact", lead))
        await self.session.commit()
        await self.session.refresh(draft)
        return draft

    async def generate_mock_draft(self, payload: DraftGenerateRequest) -> EmailDraftModel | None:
        lead = await self.get_lead(payload.lead_id)
        if lead is None:
            return None
        existing = await self.get_active_draft_for_lead(payload.lead_id)
        if existing is not None:
            return existing
        campaign = None
        if payload.campaign_id is not None:
            campaign = await self.get_campaign(payload.campaign_id)
            if campaign is None:
                return None
        generated = await AIDraftService().generate_draft(lead, campaign, payload)
        return await self.create_draft(
            DraftCreate(
                lead_id=payload.lead_id,
                campaign_id=payload.campaign_id,
                subject=generated.subject,
                body=generated.body,
                generated_by=generated.generated_by,
                context_summary=generated.context_summary,
            )
        )

    async def generate_draft_queue(self, payload: DraftQueueGenerateRequest) -> QueueResult:
        query = select(LeadModel).where(
            LeadModel.outreach_status == payload.outreach_status,
            LeadModel.lead_grade.in_(payload.lead_grades),
        ).order_by(LeadModel.created_at).limit(payload.limit)
        leads = list((await self.session.execute(query)).scalars().all())
        result = QueueResult()
        result.scanned = len(leads)
        for lead in leads:
            if await self.get_active_draft_for_lead(lead.id):
                result.skipped += 1
                continue
            draft = await self.generate_mock_draft(
                DraftGenerateRequest(
                    lead_id=lead.id,
                    call_to_action=payload.call_to_action,
                    extra_context=payload.extra_context,
                )
            )
            if draft is None:
                result.skipped += 1
            else:
                result.created += 1
                result.drafts.append(draft)
        return result

    async def generate_followup_queue(self, payload: FollowUpQueueGenerateRequest) -> QueueResult:
        drafts = list((await self.session.execute(
            select(EmailDraftModel).where(EmailDraftModel.status == DraftStatus.SENT).order_by(EmailDraftModel.created_at)
        )).scalars().all())
        cutoff = datetime.now(UTC) - timedelta(days=payload.days_since_sent)
        result = QueueResult()
        for sent_draft in drafts:
            sent_time = sent_draft.sent_at or sent_draft.created_at
            if sent_time > cutoff or result.scanned >= payload.limit:
                continue
            result.scanned += 1
            lead = await self.get_lead(sent_draft.lead_id)
            has_reply = bool((await self.session.execute(
                select(EmailReplyModel.id).where(EmailReplyModel.lead_id == sent_draft.lead_id).limit(1)
            )).scalar_one_or_none())
            if lead is None or not lead.email or has_reply or await self.get_active_draft_for_lead(lead.id):
                result.skipped += 1
                continue
            context = "Follow-up to a prior sent outreach."
            if payload.extra_context:
                context = f"{context} {payload.extra_context}"
            draft = await self.generate_mock_draft(
                DraftGenerateRequest(lead_id=lead.id, call_to_action=payload.call_to_action, extra_context=context)
            )
            if draft:
                result.created += 1
                result.drafts.append(draft)
            else:
                result.skipped += 1
        return result

    async def list_drafts(self) -> list[EmailDraftModel]:
        result = await self.session.execute(select(EmailDraftModel).order_by(EmailDraftModel.created_at))
        return list(result.scalars().all())

    async def get_draft(self, draft_id: UUID) -> EmailDraftModel | None:
        return await self.session.get(EmailDraftModel, draft_id)

    async def get_active_draft_for_lead(self, lead_id: UUID) -> EmailDraftModel | None:
        result = await self.session.execute(
            select(EmailDraftModel).where(
                EmailDraftModel.lead_id == lead_id,
                EmailDraftModel.status.in_([DraftStatus.PENDING_APPROVAL, DraftStatus.APPROVED]),
            ).order_by(EmailDraftModel.created_at.desc())
        )
        return result.scalars().first()

    async def update_draft(self, draft_id: UUID, payload: DraftUpdate) -> EmailDraftModel | None:
        draft = await self.get_draft(draft_id)
        if draft is None or draft.status != DraftStatus.PENDING_APPROVAL:
            return None
        lead = await self.get_lead(draft.lead_id)
        qa = await DraftQAAgent().review(payload.subject, payload.body, lead.first_name if lead else None)
        draft.subject = payload.subject
        draft.body = payload.body
        draft.reviewer = payload.editor
        draft.review_note = payload.note
        draft.qa_status = qa.status
        draft.qa_notes = qa.notes
        draft.qa_checked_at = datetime.now(UTC)
        self._audit(AuditAction.DRAFT_UPDATED, "email_draft", draft_id, f"Draft edited by {payload.editor}")
        await self.session.commit()
        await self.session.refresh(draft)
        return draft

    async def approve_draft(self, draft_id: UUID, reviewer: str, note: str | None) -> EmailDraftModel | None:
        draft = await self.get_draft(draft_id)
        if draft is None or draft.qa_status == "blocked":
            return None
        return await self._review_draft(draft, DraftStatus.APPROVED, LeadStatus.APPROVED, reviewer, note, AuditAction.DRAFT_APPROVED, "Draft approved")

    async def reject_draft(self, draft_id: UUID, reviewer: str, note: str | None) -> EmailDraftModel | None:
        draft = await self.get_draft(draft_id)
        if draft is None:
            return None
        return await self._review_draft(draft, DraftStatus.REJECTED, LeadStatus.REJECTED, reviewer, note, AuditAction.DRAFT_REJECTED, "Draft rejected")

    async def send_draft(self, draft_id: UUID, sender: str, note: str | None) -> EmailDraftModel | None:
        draft = await self.get_draft(draft_id)
        if draft is None or draft.status != DraftStatus.APPROVED:
            return None
        lead = await self.get_lead(draft.lead_id)
        if lead is None or not lead.email:
            return None
        try:
            send_result = await EmailSenderAgent().send(lead.email, draft.subject, draft.body)
        except Exception as exc:
            draft.send_error = str(exc)
            await self.session.commit()
            raise
        draft.status = DraftStatus.SENT
        draft.reviewer = sender
        draft.review_note = note
        draft.sent_at = datetime.now(UTC)
        draft.sent_provider = send_result.provider
        draft.sent_message_id = send_result.message_id
        draft.sent_thread_id = send_result.thread_id
        draft.send_error = None
        lead.status = LeadStatus.SENT
        lead.outreach_status = PipelineStage.SENT
        await self._update_application_for_lead(
            lead.id,
            status=ApplicationStatus.OUTREACH_SENT,
            gmail_thread_id=send_result.thread_id or send_result.message_id,
        )
        summary = (
            "Draft marked sent in dry-run"
            if send_result.dry_run
            else f"Draft sent through {send_result.provider}"
        )
        self._audit(AuditAction.DRAFT_SENT, "email_draft", draft_id, summary)
        await self.session.commit()
        await self.session.refresh(draft)
        return draft

    async def classify_reply(self, payload: ReplyClassifyRequest) -> EmailReplyModel | None:
        draft = await self.get_draft(payload.draft_id)
        if draft is None or draft.status != DraftStatus.SENT:
            return None
        classification = await ReplyClassifierAgent().classify(payload.body)
        reply = EmailReplyModel(
            draft_id=draft.id,
            lead_id=draft.lead_id,
            from_email=str(payload.from_email),
            body=payload.body,
            intent=classification.intent,
            classification_reason=classification.reason,
        )
        self.session.add(reply)
        await self.session.flush()
        lead = await self.get_lead(draft.lead_id)
        if lead:
            lead.status = LeadStatus.REPLIED
            lead.outreach_status = self._reply_intent_to_pipeline_status(classification.intent)
            await self._update_application_from_reply(
                lead_id=lead.id,
                intent=classification.intent,
                provider_thread_id=draft.sent_thread_id,
                provider_message_id=draft.sent_message_id,
            )
        self._audit(AuditAction.REPLY_CLASSIFIED, "email_reply", reply.id, f"Reply classified as {classification.intent.value}")
        await self.session.commit()
        await self.session.refresh(reply)
        return reply

    async def sync_email_replies(self) -> ReplySyncServiceResult:
        messages = await EmailInboxAgent().fetch_recent()
        result = ReplySyncServiceResult()
        result.fetched = len(messages)
        for message in messages:
            duplicate = (await self.session.execute(
                select(EmailReplyModel.id).where(EmailReplyModel.provider_message_id == message.provider_message_id)
            )).scalar_one_or_none()
            if duplicate:
                result.skipped += 1
                continue
            lead, draft = await self._reply_target_for_message(message)
            if lead is None or draft is None:
                result.skipped += 1
                continue
            result.matched += 1
            classification = await ReplyClassifierAgent().classify(message.body)
            reply = EmailReplyModel(
                draft_id=draft.id,
                lead_id=lead.id,
                from_email=message.from_email,
                body=message.body,
                intent=classification.intent,
                classification_reason=classification.reason,
                provider_message_id=message.provider_message_id,
                provider_thread_id=message.provider_thread_id,
                subject=message.subject,
                received_at=message.received_at,
            )
            self.session.add(reply)
            await self.session.flush()
            lead.status = LeadStatus.REPLIED
            lead.outreach_status = self._reply_intent_to_pipeline_status(classification.intent)
            await self._update_application_from_reply(
                lead_id=lead.id,
                intent=classification.intent,
                provider_thread_id=message.provider_thread_id,
                provider_message_id=message.provider_message_id,
            )
            self._audit(AuditAction.REPLY_SYNCED, "email_reply", reply.id, f"Email reply synced as {classification.intent.value}")
            result.imported += 1
            result.replies.append(reply)
        await self.session.commit()
        for reply in result.replies:
            await self.session.refresh(reply)
        return result

    async def list_replies(self) -> list[EmailReplyModel]:
        result = await self.session.execute(select(EmailReplyModel).order_by(EmailReplyModel.created_at))
        return list(result.scalars().all())

    async def list_audit_events(self) -> list[AuditEventModel]:
        result = await self.session.execute(select(AuditEventModel).order_by(AuditEventModel.created_at))
        return list(result.scalars().all())

    async def get_profile_settings(self) -> ProfileSettings:
        profile = await self._get_or_create_profile_settings()
        return self._profile_schema(profile)

    async def update_profile_settings(self, payload: ProfileSettingsUpdate) -> ProfileSettings:
        profile = await self._get_or_create_profile_settings()
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            if key in {"target_roles", "target_locations", "target_skills"}:
                setattr(profile, key, self._serialize_profile_list(value or []))
            else:
                setattr(profile, key, value)
        self._audit(
            AuditAction.PROFILE_UPDATED,
            "profile_settings",
            profile.id,
            f"Profile settings updated for {profile.owner_name}",
        )
        await self.session.commit()
        await self.session.refresh(profile)
        return self._profile_schema(profile)

    async def create_career_source(self, payload: CareerSourceCreate) -> CareerSourceModel:
        duplicate = (
            await self.session.execute(
                select(CareerSourceModel).where(CareerSourceModel.careers_url == payload.careers_url).limit(1)
            )
        ).scalar_one_or_none()
        if duplicate is not None:
            raise DuplicateCareerSourceError("Career source URL already exists")
        source = CareerSourceModel(**payload.model_dump())
        self.session.add(source)
        await self.session.flush()
        self._audit(
            AuditAction.CAREER_SOURCE_CREATED,
            "career_source",
            source.id,
            f"Career source saved: {source.company_name}",
        )
        await self.session.commit()
        await self.session.refresh(source)
        return source

    async def list_career_sources(self) -> list[CareerSourceModel]:
        result = await self.session.execute(select(CareerSourceModel).order_by(CareerSourceModel.company_name))
        return list(result.scalars().all())

    async def update_career_source(
        self,
        source_id: UUID,
        payload: CareerSourceUpdate,
    ) -> CareerSourceModel | None:
        source = await self.session.get(CareerSourceModel, source_id)
        if source is None:
            return None
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(source, key, value)
        self._audit(
            AuditAction.CAREER_SOURCE_UPDATED,
            "career_source",
            source.id,
            f"Career source updated: {source.company_name}",
        )
        await self.session.commit()
        await self.session.refresh(source)
        return source

    async def delete_career_source(self, source_id: UUID) -> bool:
        source = await self.session.get(CareerSourceModel, source_id)
        if source is None:
            return False
        self._audit(
            AuditAction.CAREER_SOURCE_DELETED,
            "career_source",
            source.id,
            f"Career source deleted: {source.company_name}",
        )
        await self.session.delete(source)
        await self.session.commit()
        return True

    async def scan_career_sources(self, payload: CareerSourceScanRequest):
        if payload.career_source_ids:
            sources = list(
                (
                    await self.session.execute(
                        select(CareerSourceModel).where(CareerSourceModel.id.in_(payload.career_source_ids))
                    )
                ).scalars().all()
            )
        else:
            sources = list(
                (
                    await self.session.execute(
                        select(CareerSourceModel).where(CareerSourceModel.active.is_(True))
                    )
                ).scalars().all()
            )
        source_urls = [source.careers_url for source in sources if source.active and source.careers_url]
        if not source_urls:
            return None, sources

        discovery_request = JobSourceDiscoveryRequest(
            target_roles=payload.target_roles,
            target_locations=payload.target_locations,
            target_skills=payload.target_skills,
            source_urls=source_urls,
            import_results=payload.import_results,
        )
        discovery = await JobSourceDiscoveryService().discover(discovery_request)
        now = datetime.now(UTC)
        for source in sources:
            source.last_scanned_at = now
            source.last_error = None
            source.last_result_count = len(
                [
                    job
                    for job in discovery.jobs
                    if job.url == source.careers_url
                    or source.careers_url in str(job.source_links or "")
                    or source.company_name.lower() in job.company.lower()
                ]
            )
        imported = 0
        skipped = 0
        leads = []
        if payload.import_results and discovery.jobs:
            import_result = await self.import_discovered_jobs(
                JobDiscoveryImportRequest(
                    target_roles=payload.target_roles,
                    target_locations=payload.target_locations,
                    target_skills=payload.target_skills,
                    jobs=discovery.jobs,
                )
            )
            imported = import_result.imported
            skipped = import_result.skipped
            leads = import_result.leads
        for source in sources:
            self._audit(
                AuditAction.CAREER_SOURCE_SCANNED,
                "career_source",
                source.id,
                f"Career source scanned: {source.company_name}",
            )
        await self.session.commit()
        return {
            "scanned_sources": discovery.scanned_sources,
            "discovered": len(discovery.jobs),
            "imported": imported,
            "skipped": skipped,
            "errors": discovery.errors,
            "jobs": discovery.jobs,
            "leads": leads,
        }, sources

    async def _get_or_create_profile_settings(self) -> ProfileSettingsModel:
        profile = (
            await self.session.execute(
                select(ProfileSettingsModel).where(ProfileSettingsModel.profile_key == "default").limit(1)
            )
        ).scalar_one_or_none()
        if profile is not None:
            return profile
        profile = ProfileSettingsModel(
            profile_key="default",
            owner_name="Prakriti Dhital",
            primary_email="prakriti.dhital.tech@gmail.com",
            outreach_email="prakriti.dhital.tech@gmail.com",
            target_roles=self._serialize_profile_list(DEFAULT_TARGET_ROLES),
            target_locations=self._serialize_profile_list(DEFAULT_TARGET_LOCATIONS),
            target_skills=self._serialize_profile_list(DEFAULT_TARGET_SKILLS),
            resume_summary=(
                "Building practical AI, backend, automation, and web systems. "
                "Interested in junior AI engineering, backend, software developer, web developer, "
                "automation, QA, and IT roles in Canada or remote Canada."
            ),
            default_resume_version="Resume - Tech Opportunities",
        )
        self.session.add(profile)
        await self.session.commit()
        await self.session.refresh(profile)
        return profile

    @classmethod
    def _profile_schema(cls, profile: ProfileSettingsModel) -> ProfileSettings:
        return ProfileSettings(
            id=profile.id,
            owner_name=profile.owner_name,
            primary_email=profile.primary_email,
            outreach_email=profile.outreach_email,
            target_roles=cls._parse_profile_list(profile.target_roles),
            target_locations=cls._parse_profile_list(profile.target_locations),
            target_skills=cls._parse_profile_list(profile.target_skills),
            resume_summary=profile.resume_summary,
            linkedin_profile_url=profile.linkedin_profile_url,
            github_url=profile.github_url,
            portfolio_url=profile.portfolio_url,
            default_resume_version=profile.default_resume_version,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )

    @staticmethod
    def _serialize_profile_list(values: list[str]) -> str:
        return "\n".join(value.strip() for value in values if value and value.strip())

    @staticmethod
    def _parse_profile_list(value: str | None) -> list[str]:
        return [item.strip() for item in str(value or "").splitlines() if item.strip()]

    async def _reply_target_for_message(self, message) -> tuple[LeadModel | None, EmailDraftModel | None]:
        draft = None
        lead = None
        thread_keys = [
            key
            for key in (message.provider_thread_id, message.provider_message_id)
            if key
        ]
        if thread_keys:
            draft = (
                await self.session.execute(
                    select(EmailDraftModel)
                    .where(
                        EmailDraftModel.status == DraftStatus.SENT,
                        or_(
                            EmailDraftModel.sent_thread_id.in_(thread_keys),
                            EmailDraftModel.sent_message_id.in_(thread_keys),
                        ),
                    )
                    .order_by(EmailDraftModel.sent_at.desc().nullslast(), EmailDraftModel.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if draft is not None:
                lead = await self.get_lead(draft.lead_id)
                return lead, draft

            application = (
                await self.session.execute(
                    select(ApplicationModel)
                    .where(ApplicationModel.gmail_thread_id.in_(thread_keys))
                    .order_by(ApplicationModel.updated_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if application and application.lead_id:
                lead = await self.get_lead(application.lead_id)
                if lead is not None:
                    draft = await self._latest_sent_draft_for_lead(lead.id)
                    if draft is not None:
                        return lead, draft

        lead = (
            await self.session.execute(
                select(LeadModel).where(LeadModel.email == message.from_email).limit(1)
            )
        ).scalar_one_or_none()
        if lead is None:
            return None, None
        return lead, await self._latest_sent_draft_for_lead(lead.id)

    async def _latest_sent_draft_for_lead(self, lead_id: UUID) -> EmailDraftModel | None:
        return (
            await self.session.execute(
                select(EmailDraftModel)
                .where(
                    EmailDraftModel.lead_id == lead_id,
                    EmailDraftModel.status == DraftStatus.SENT,
                )
                .order_by(EmailDraftModel.sent_at.desc().nullslast(), EmailDraftModel.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    async def _update_application_for_lead(
        self,
        lead_id: UUID,
        status: ApplicationStatus,
        gmail_thread_id: str | None = None,
    ) -> ApplicationModel | None:
        application = await self.get_application_by_lead_id(lead_id)
        if application is None:
            return None
        application.status = status
        if gmail_thread_id:
            application.gmail_thread_id = gmail_thread_id
        if status in {
            ApplicationStatus.CONTACT_FOUND,
            ApplicationStatus.OUTREACH_DRAFTED,
            ApplicationStatus.OUTREACH_APPROVED,
            ApplicationStatus.OUTREACH_SENT,
            ApplicationStatus.REPLIED,
            ApplicationStatus.INTERVIEW,
            ApplicationStatus.FOLLOW_UP_DUE,
        }:
            application.contact_found = True
        self._audit(
            AuditAction.APPLICATION_UPDATED,
            "application",
            application.id,
            f"Application auto-updated to {application.status}: {application.job_title} at {application.company_name}",
        )
        return application

    async def _update_application_from_reply(
        self,
        lead_id: UUID,
        intent,
        provider_thread_id: str | None = None,
        provider_message_id: str | None = None,
    ) -> ApplicationModel | None:
        status = self._reply_intent_to_application_status(intent)
        return await self._update_application_for_lead(
            lead_id=lead_id,
            status=status,
            gmail_thread_id=provider_thread_id or provider_message_id,
        )

    async def _review_draft(self, draft: EmailDraftModel, draft_status: DraftStatus, lead_status: LeadStatus, reviewer: str, note: str | None, action: AuditAction, summary: str) -> EmailDraftModel:
        draft.status = draft_status
        draft.reviewer = reviewer
        draft.review_note = note
        lead = await self.get_lead(draft.lead_id)
        if lead:
            lead.status = lead_status
            if draft_status == DraftStatus.APPROVED:
                lead.outreach_status = PipelineStage.APPROVED
                await self._update_application_for_lead(
                    lead.id,
                    status=ApplicationStatus.OUTREACH_APPROVED,
                )
            elif draft_status == DraftStatus.REJECTED:
                lead.outreach_status = PipelineStage.CLOSED
        self._audit(action, "email_draft", draft.id, summary)
        await self.session.commit()
        await self.session.refresh(draft)
        return draft

    def _audit(self, action: AuditAction, entity_type: str, entity_id: UUID, summary: str) -> None:
        self.session.add(AuditEventModel(action=action, entity_type=entity_type, entity_id=entity_id, summary=summary))

    @staticmethod
    def _lead_summary(prefix: str, lead: LeadModel) -> str:
        identifier = lead.email or " ".join(part for part in (lead.first_name, lead.last_name) if part)
        return f"{prefix} {identifier}".strip()

    @staticmethod
    def _append_note(existing: str | None, note: str) -> str:
        if not existing:
            return note
        if note in existing:
            return existing
        return f"{existing} {note}"

    @staticmethod
    def _merge_csv_text(existing: str | None, incoming: str | None, *, limit: int) -> str | None:
        values = []
        for raw_value in [existing, incoming]:
            for item in (raw_value or "").split(","):
                clean = item.strip()
                if clean and clean.lower() not in {value.lower() for value in values}:
                    values.append(clean)
        merged = ", ".join(values)
        return merged[:limit] if merged else None

    @staticmethod
    def _merge_lines(existing: str | None, incoming: str | None, *, limit: int) -> str | None:
        lines = []
        for raw_value in [existing, incoming]:
            for line in (raw_value or "").splitlines():
                clean = line.strip()
                if clean and clean not in lines:
                    lines.append(clean)
        merged = "\n".join(lines)
        return merged[:limit] if merged else None

    @staticmethod
    def _opportunity_message_context(lead: LeadModel) -> str:
        parts = []
        if lead.title and lead.company:
            parts.append(f"{lead.title} at {lead.company}.")
        if lead.fit_score is not None:
            parts.append(f"Fit score {lead.fit_score}/100.")
        if lead.company_summary:
            parts.append(f"Company research: {lead.company_summary}")
        if lead.tech_stack:
            parts.append(f"Tech stack: {lead.tech_stack}.")
        if lead.role_fit:
            parts.append(f"Role fit: {lead.role_fit}.")
        if lead.contact_verification_status:
            parts.append(
                f"Contact finder status: {lead.contact_verification_status}; "
                f"confidence {lead.contact_confidence_score or 0}/100."
            )
        if lead.contact_source_url:
            parts.append(f"Contact/source URL: {lead.contact_source_url}.")
        return " ".join(parts)

    @staticmethod
    def _reply_intent_to_pipeline_status(intent) -> str:
        value = str(intent)
        if value in {"interview", "resume_requested"}:
            return PipelineStage.REPLIED
        if value in {"interested", "neutral", "unclear"}:
            return PipelineStage.REPLIED
        if value == "out_of_office":
            return PipelineStage.FOLLOW_UP_DUE
        if value in {"not_interested", "unsubscribe", "bounce"}:
            return PipelineStage.CLOSED
        return PipelineStage.REPLIED

    @staticmethod
    def _reply_intent_to_application_status(intent) -> ApplicationStatus:
        value = str(intent)
        if value in {"interview", "resume_requested"}:
            return ApplicationStatus.INTERVIEW
        if value in {"interested", "neutral", "unclear"}:
            return ApplicationStatus.REPLIED
        if value == "out_of_office":
            return ApplicationStatus.FOLLOW_UP_DUE
        if value == "not_interested":
            return ApplicationStatus.REJECTED
        if value in {"unsubscribe", "bounce"}:
            return ApplicationStatus.CLOSED
        return ApplicationStatus.REPLIED

    @staticmethod
    def _score_discovered_job(payload: JobDiscoveryImportRequest, item) -> tuple[int, str]:
        text = " ".join(
            part
            for part in (
                item.company,
                item.title,
                item.location,
                item.description,
                item.company_summary,
                item.tech_stack,
                item.role_fit,
            )
            if part
        ).lower()
        score = 35
        notes: list[str] = []

        matched_roles = [role for role in payload.target_roles if role and role.lower() in text]
        if matched_roles:
            score += 25
            notes.append(f"matched roles: {', '.join(matched_roles)}")
        else:
            matched_role_tokens = PipelineService._matched_target_tokens(text, payload.target_roles)
            if matched_role_tokens:
                score += min(20, len(matched_role_tokens) * 5)
                notes.append(f"matched role keywords: {', '.join(matched_role_tokens)}")

        matched_locations = [
            location for location in payload.target_locations if location and location.lower() in text
        ]
        if matched_locations:
            score += 20
            notes.append(f"matched locations: {', '.join(matched_locations)}")
        elif any(location.lower() == "remote canada" for location in payload.target_locations) and "remote" in text:
            score += 15
            notes.append("matched remote preference")

        matched_skills = [skill for skill in payload.target_skills if skill and skill.lower() in text]
        if matched_skills:
            score += min(20, len(matched_skills) * 5)
            notes.append(f"matched skills: {', '.join(matched_skills)}")

        if item.contact_email:
            score += 10
            notes.append("contact email available")
        elif item.contact_url:
            score += 5
            notes.append("contact/profile link available")

        score = max(0, min(score, 100))
        return score, "; ".join(notes) if notes else "no explicit role, location, or skill matches"

    @staticmethod
    def _normalized_source(source: str | None) -> str:
        value = str(source or "manual_discovery").strip()
        normalized = value.lower().replace("job_discovery:", "")
        if normalized in {"linkedin", "linkedin_tracker"}:
            return "LINKEDIN"
        if normalized in {"indeed", "indeed_tracker"}:
            return "INDEED"
        if normalized in {"remotive", "remoteok", "adzuna", "jobbank", "glassdoor"}:
            return normalized.upper()
        return value

    @staticmethod
    def _contact_type_for_import(item) -> str:
        if item.contact_email:
            return "public_email"
        if item.contact_url and "linkedin.com/in/" in item.contact_url.lower():
            return "recruiter_profile"
        if item.contact_name:
            return "named_recruiter"
        return "source_contact_link"

    @staticmethod
    def _contact_confidence_for_import(item) -> int:
        if item.contact_email and (item.contact_name or item.contact_url):
            return 90
        if item.contact_email:
            return 85
        if item.contact_name and item.contact_url:
            return 75
        if item.contact_url:
            return 65
        return 55

    @staticmethod
    def _contact_verification_for_import(item) -> str:
        if item.contact_email:
            return "manual_public_email"
        if item.contact_name and item.contact_url:
            return "manual_profile_tracked"
        if item.contact_url:
            return "manual_contact_url_tracked"
        return "manual_name_tracked"

    @staticmethod
    def _contact_research_from_import(lead: LeadModel, item) -> ContactResearchModel:
        return ContactResearchModel(
            lead_id=lead.id,
            contact_name=item.contact_name,
            contact_email=str(item.contact_email) if item.contact_email else None,
            contact_role="Recruiter / Hiring Manager",
            contact_type=PipelineService._contact_type_for_import(item),
            source_url=item.contact_url or item.url,
            confidence_score=PipelineService._contact_confidence_for_import(item),
            verification_status=PipelineService._contact_verification_for_import(item),
            notes=item.notes,
        )

    @staticmethod
    def _application_data_from_lead(lead: LeadModel, data: dict) -> dict:
        data["company_name"] = data.get("company_name") or lead.company or "Unknown Company"
        data["job_title"] = data.get("job_title") or lead.title or "Open role"
        data["source"] = data.get("source") or PipelineService._application_source_from_lead(lead)
        data["job_url"] = data.get("job_url") or lead.opportunity_url or lead.linkedin_url
        data["location"] = data.get("location") or lead.opportunity_location
        data["contact_found"] = data.get("contact_found") or bool(lead.email or lead.contact_source_url)
        data["notes"] = data.get("notes") or lead.notes
        return data

    @staticmethod
    def _application_source_from_lead(lead: LeadModel) -> str:
        source = str(lead.source or "").upper()
        if source == "LINKEDIN" or "linkedin.com" in str(lead.opportunity_url or lead.linkedin_url).lower():
            return "LinkedIn"
        if source == "INDEED" or "indeed." in str(lead.opportunity_url or lead.linkedin_url).lower():
            return "Indeed"
        if lead.opportunity_url:
            return "Company Site"
        return lead.source or "Manual"

    @staticmethod
    def _sync_lead_from_application(application: ApplicationModel, lead: LeadModel | None) -> None:
        if lead is None:
            return
        if application.status == ApplicationStatus.CONTACT_SEARCH_NEEDED:
            lead.outreach_status = PipelineStage.COMPANY_RESEARCHED
        elif application.status == ApplicationStatus.CONTACT_FOUND:
            lead.outreach_status = PipelineStage.CONTACT_FOUND
        elif application.status == ApplicationStatus.OUTREACH_DRAFTED:
            lead.outreach_status = PipelineStage.PENDING_APPROVAL
        elif application.status == ApplicationStatus.OUTREACH_APPROVED:
            lead.outreach_status = PipelineStage.APPROVED
        elif application.status == ApplicationStatus.OUTREACH_SENT:
            lead.outreach_status = PipelineStage.SENT
        elif application.status in {ApplicationStatus.REPLIED, ApplicationStatus.INTERVIEW}:
            lead.outreach_status = PipelineStage.REPLIED
        elif application.status == ApplicationStatus.FOLLOW_UP_DUE:
            lead.outreach_status = PipelineStage.FOLLOW_UP_DUE
        elif application.status in {ApplicationStatus.REJECTED, ApplicationStatus.CLOSED}:
            lead.outreach_status = PipelineStage.CLOSED

    @staticmethod
    def _priority_from_score(score: int) -> str:
        if score >= 75:
            return "High Priority"
        if score >= 55:
            return "Medium Priority"
        if score >= 40:
            return "Low Priority"
        return "Archive"

    @staticmethod
    def _matched_target_tokens(text: str, targets: list[str]) -> list[str]:
        ignored = {
            "junior",
            "senior",
            "entry",
            "level",
            "remote",
            "canada",
            "developer",
            "engineer",
        }
        tokens: list[str] = []
        for target in targets:
            for token in target.lower().replace(".", " ").replace("-", " ").split():
                clean_token = "".join(character for character in token if character.isalnum() or character in {"#", "+"})
                if len(clean_token) < 3 or clean_token in ignored or clean_token in tokens:
                    continue
                if clean_token in text:
                    tokens.append(clean_token)
        return tokens
