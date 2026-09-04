"""API routes for the personal outreach workflow."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.email_inbox import EmailInboxError
from app.agents.email_sender import EmailSendError
from app.api.auth import verify_automation_token
from app.db.session import get_db
from app.schemas.pipeline import (
    Application,
    ApplicationCreate,
    ApplicationUpdate,
    AuditEvent,
    Campaign,
    CampaignCreate,
    CareerSource,
    CareerSourceCreate,
    CareerSourceScanRequest,
    CareerSourceUpdate,
    ContactResearch,
    ContactFinderResult,
    DraftCreate,
    DraftArchive,
    DraftQueueGenerateRequest,
    DraftQueueGenerateResult,
    DraftGenerateRequest,
    DraftUpdate,
    EmailReply,
    EmailDraft,
    FollowUpQueueGenerateRequest,
    FollowUpQueueGenerateResult,
    JobDiscoveryImportRequest,
    JobDiscoveryImportResult,
    JobSearchRequest,
    JobSearchResult,
    JobSourceDiscoveryRequest,
    JobSourceDiscoveryResult,
    JobUrlImportRequest,
    JobUrlImportResult,
    Lead,
    LeadContactUpdate,
    LeadCreate,
    LinkedInConnectionMessageResult,
    Opportunity,
    PipelineBatchRunRequest,
    PipelineBatchRunResult,
    PipelineStepResult,
    ProfileSettings,
    ProfileSettingsUpdate,
    ReplyClassifyRequest,
    ReviewDecision,
    ReplySyncResult,
    SendDecision,
    SourceTrackerCsvImportRequest,
    SourceTrackerImportRequest,
    SourceTrackerImportResult,
)
from app.services.job_search_discovery import JobSearchDiscoveryService
from app.services.job_source_discovery import JobSourceDiscoveryService
from app.services.job_url_importer import JobUrlImporter
from app.services.pipeline_service import DuplicateCareerSourceError, PipelineService
from app.services.source_adapters import SourceAdapterError, adapter_for

router = APIRouter(prefix="/api/v1", tags=["pipeline"])


def get_pipeline_service(db: AsyncSession = Depends(get_db)) -> PipelineService:
    return PipelineService(db)


@router.post("/leads", response_model=Lead, status_code=status.HTTP_201_CREATED)
async def create_lead(
    payload: LeadCreate,
    service: PipelineService = Depends(get_pipeline_service),
) -> Lead:
    return await service.create_lead(payload)


@router.post("/leads/batch", response_model=list[Lead], status_code=status.HTTP_201_CREATED)
async def create_leads(
    payload: list[LeadCreate],
    service: PipelineService = Depends(get_pipeline_service),
) -> list[Lead]:
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one contact is required",
        )
    return await service.create_leads(payload)


@router.get("/leads", response_model=list[Lead])
async def list_leads(service: PipelineService = Depends(get_pipeline_service)) -> list[Lead]:
    return await service.list_leads()


@router.get("/profile", response_model=ProfileSettings)
async def get_profile_settings(
    service: PipelineService = Depends(get_pipeline_service),
) -> ProfileSettings:
    return await service.get_profile_settings()


@router.put("/profile", response_model=ProfileSettings)
async def update_profile_settings(
    payload: ProfileSettingsUpdate,
    service: PipelineService = Depends(get_pipeline_service),
) -> ProfileSettings:
    return await service.update_profile_settings(payload)


@router.get("/opportunities", response_model=list[Opportunity])
async def list_opportunities(service: PipelineService = Depends(get_pipeline_service)) -> list[Opportunity]:
    leads = await service.list_leads()
    opportunities = []
    for lead in leads:
        if not lead.opportunity_url and str(lead.source or "").upper() not in {"LINKEDIN", "INDEED"}:
            continue
        skills = [skill.strip() for skill in (lead.tech_stack or "").replace("|", ",").split(",") if skill.strip()]
        opportunities.append(
            Opportunity(
                lead_id=lead.id,
                source=lead.source,
                source_url=lead.opportunity_url or lead.linkedin_url,
                company_name=lead.company,
                job_title=lead.title,
                location=lead.opportunity_location,
                description=lead.opportunity_description,
                required_skills=skills,
                fit_score=lead.fit_score,
                status=lead.outreach_status,
            )
        )
    return opportunities


@router.post(
    "/job-discovery/import",
    response_model=JobDiscoveryImportResult,
    status_code=status.HTTP_201_CREATED,
)
async def import_discovered_jobs(
    payload: JobDiscoveryImportRequest,
    service: PipelineService = Depends(get_pipeline_service),
) -> JobDiscoveryImportResult:
    result = await service.import_discovered_jobs(payload)
    return JobDiscoveryImportResult(
        imported=result.imported,
        skipped=result.skipped,
        leads=result.leads,
    )


@router.post(
    "/job-discovery/import-url",
    response_model=JobUrlImportResult,
    status_code=status.HTTP_201_CREATED,
)
async def import_job_url(
    payload: JobUrlImportRequest,
    service: PipelineService = Depends(get_pipeline_service),
) -> JobUrlImportResult:
    built = await JobUrlImporter().build_job(payload)
    imported = 0
    skipped = 0
    leads = []
    if payload.import_result:
        result = await service.import_discovered_jobs(
            JobDiscoveryImportRequest(
                target_roles=payload.target_roles,
                target_locations=payload.target_locations,
                target_skills=payload.target_skills,
                jobs=[built.job],
            )
        )
        imported = result.imported
        skipped = result.skipped
        leads = result.leads

    return JobUrlImportResult(
        imported=imported,
        skipped=skipped,
        source=built.source,
        extraction_status=built.extraction_status,
        warnings=built.warnings,
        job=built.job,
        leads=leads,
    )


@router.post(
    "/job-discovery/search",
    response_model=JobSearchResult,
    status_code=status.HTTP_201_CREATED,
)
async def search_jobs(
    payload: JobSearchRequest,
    service: PipelineService = Depends(get_pipeline_service),
) -> JobSearchResult:
    discovery = await JobSearchDiscoveryService().search(payload)
    imported = 0
    skipped = 0
    leads = []

    if payload.import_results and discovery.jobs:
        import_result = await service.import_discovered_jobs(
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

    return JobSearchResult(
        searched_sources=discovery.searched_sources,
        discovered=len(discovery.jobs),
        imported=imported,
        skipped=skipped,
        errors=discovery.errors,
        jobs=discovery.jobs,
        leads=leads,
    )


@router.post(
    "/job-discovery/discover",
    response_model=JobSourceDiscoveryResult,
    status_code=status.HTTP_201_CREATED,
)
async def discover_jobs_from_sources(
    payload: JobSourceDiscoveryRequest,
    service: PipelineService = Depends(get_pipeline_service),
) -> JobSourceDiscoveryResult:
    discovery = await JobSourceDiscoveryService().discover(payload)
    imported = 0
    skipped = 0
    leads = []

    if payload.import_results and discovery.jobs:
        import_result = await service.import_discovered_jobs(
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

    return JobSourceDiscoveryResult(
        scanned_sources=discovery.scanned_sources,
        discovered=len(discovery.jobs),
        imported=imported,
        skipped=skipped,
        errors=discovery.errors,
        jobs=discovery.jobs,
        leads=leads,
    )


@router.post("/career-sources", response_model=CareerSource, status_code=status.HTTP_201_CREATED)
async def create_career_source(
    payload: CareerSourceCreate,
    service: PipelineService = Depends(get_pipeline_service),
) -> CareerSource:
    try:
        return await service.create_career_source(payload)
    except DuplicateCareerSourceError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/career-sources", response_model=list[CareerSource])
async def list_career_sources(
    service: PipelineService = Depends(get_pipeline_service),
) -> list[CareerSource]:
    return await service.list_career_sources()


@router.patch("/career-sources/{source_id}", response_model=CareerSource)
async def update_career_source(
    source_id: UUID,
    payload: CareerSourceUpdate,
    service: PipelineService = Depends(get_pipeline_service),
) -> CareerSource:
    career_source = await service.update_career_source(source_id, payload)
    if career_source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Career source not found")
    return career_source


@router.delete("/career-sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_career_source(
    source_id: UUID,
    service: PipelineService = Depends(get_pipeline_service),
) -> None:
    deleted = await service.delete_career_source(source_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Career source not found")


@router.post(
    "/career-sources/scan",
    response_model=JobSourceDiscoveryResult,
    status_code=status.HTTP_201_CREATED,
)
async def scan_career_sources(
    payload: CareerSourceScanRequest,
    service: PipelineService = Depends(get_pipeline_service),
) -> JobSourceDiscoveryResult:
    result, _sources = await service.scan_career_sources(payload)
    if result is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No active career sources selected")
    return JobSourceDiscoveryResult(**result)


async def _import_from_source_tracker(
    source: str,
    payload: SourceTrackerImportRequest,
    service: PipelineService,
) -> SourceTrackerImportResult:
    try:
        adapter = adapter_for(source)
        jobs = adapter.opportunities_from_request(payload)
    except SourceAdapterError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    result = await service.import_discovered_jobs(
        JobDiscoveryImportRequest(
            target_roles=payload.target_roles,
            target_locations=payload.target_locations,
            target_skills=payload.target_skills,
            jobs=jobs,
        )
    )
    return SourceTrackerImportResult(
        imported=result.imported,
        skipped=result.skipped,
        source=adapter.source_name,
        jobs=jobs,
        leads=result.leads,
    )


@router.post(
    "/source-trackers/linkedin/import",
    response_model=SourceTrackerImportResult,
    status_code=status.HTTP_201_CREATED,
)
async def import_linkedin_opportunities(
    payload: SourceTrackerImportRequest,
    service: PipelineService = Depends(get_pipeline_service),
) -> SourceTrackerImportResult:
    return await _import_from_source_tracker("linkedin", payload, service)


@router.post(
    "/source-trackers/indeed/import",
    response_model=SourceTrackerImportResult,
    status_code=status.HTTP_201_CREATED,
)
async def import_indeed_opportunities(
    payload: SourceTrackerImportRequest,
    service: PipelineService = Depends(get_pipeline_service),
) -> SourceTrackerImportResult:
    return await _import_from_source_tracker("indeed", payload, service)


@router.post(
    "/source-trackers/indeed/import-csv",
    response_model=SourceTrackerImportResult,
    status_code=status.HTTP_201_CREATED,
)
async def import_indeed_csv(
    payload: SourceTrackerCsvImportRequest,
    service: PipelineService = Depends(get_pipeline_service),
) -> SourceTrackerImportResult:
    try:
        adapter = adapter_for("indeed")
        jobs = adapter.opportunities_from_csv(payload)
    except SourceAdapterError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    result = await service.import_discovered_jobs(
        JobDiscoveryImportRequest(
            target_roles=payload.target_roles,
            target_locations=payload.target_locations,
            target_skills=payload.target_skills,
            jobs=jobs,
        )
    )
    return SourceTrackerImportResult(
        imported=result.imported,
        skipped=result.skipped,
        source=adapter.source_name,
        jobs=jobs,
        leads=result.leads,
    )


@router.post("/integrations/email/sync-replies", response_model=ReplySyncResult)
async def sync_email_replies(
    _: None = Depends(verify_automation_token),
    service: PipelineService = Depends(get_pipeline_service),
) -> ReplySyncResult:
    try:
        result = await service.sync_email_replies()
    except EmailInboxError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Email reply sync failed: {exc}",
        ) from exc
    return ReplySyncResult(
        fetched=result.fetched,
        matched=result.matched,
        imported=result.imported,
        skipped=result.skipped,
        replies=result.replies,
        details=result.details,
    )


@router.post("/replies/sync", response_model=ReplySyncResult)
async def sync_email_replies_from_dashboard(
    service: PipelineService = Depends(get_pipeline_service),
) -> ReplySyncResult:
    """User-triggered Gmail reply sync from the dashboard."""
    try:
        result = await service.sync_email_replies()
    except EmailInboxError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Email reply sync failed: {exc}",
        ) from exc
    return ReplySyncResult(
        fetched=result.fetched,
        matched=result.matched,
        imported=result.imported,
        skipped=result.skipped,
        replies=result.replies,
        details=result.details,
    )


@router.post("/automation/generate-drafts", response_model=DraftQueueGenerateResult)
async def generate_draft_queue(
    payload: DraftQueueGenerateRequest,
    _: None = Depends(verify_automation_token),
    service: PipelineService = Depends(get_pipeline_service),
) -> DraftQueueGenerateResult:
    result = await service.generate_draft_queue(payload)
    return DraftQueueGenerateResult(
        scanned=result.scanned,
        created=result.created,
        skipped=result.skipped,
        drafts=result.drafts,
    )


@router.post("/automation/generate-followups", response_model=FollowUpQueueGenerateResult)
async def generate_followup_queue(
    payload: FollowUpQueueGenerateRequest,
    _: None = Depends(verify_automation_token),
    service: PipelineService = Depends(get_pipeline_service),
) -> FollowUpQueueGenerateResult:
    result = await service.generate_followup_queue(payload)
    return FollowUpQueueGenerateResult(
        scanned=result.scanned,
        created=result.created,
        skipped=result.skipped,
        drafts=result.drafts,
        details=result.details,
    )


@router.post("/followups/generate", response_model=FollowUpQueueGenerateResult)
async def generate_followup_queue_from_dashboard(
    payload: FollowUpQueueGenerateRequest,
    service: PipelineService = Depends(get_pipeline_service),
) -> FollowUpQueueGenerateResult:
    """User-triggered follow-up draft generation; drafts still require approval."""
    result = await service.generate_followup_queue(payload)
    return FollowUpQueueGenerateResult(
        scanned=result.scanned,
        created=result.created,
        skipped=result.skipped,
        drafts=result.drafts,
        details=result.details,
    )


@router.get("/leads/{lead_id}", response_model=Lead)
async def get_lead(
    lead_id: UUID,
    service: PipelineService = Depends(get_pipeline_service),
) -> Lead:
    lead = await service.get_lead(lead_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
    return lead


@router.patch("/leads/{lead_id}/contact", response_model=Lead)
async def update_lead_contact(
    lead_id: UUID,
    payload: LeadContactUpdate,
    service: PipelineService = Depends(get_pipeline_service),
) -> Lead:
    lead = await service.update_lead_contact(lead_id, payload)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")
    return lead


@router.post("/leads/{lead_id}/research-company", response_model=Lead)
async def research_company(
    lead_id: UUID,
    service: PipelineService = Depends(get_pipeline_service),
) -> Lead:
    lead = await service.research_company(lead_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")
    return lead


@router.post("/leads/{lead_id}/analyze-fit", response_model=Lead)
async def analyze_fit(
    lead_id: UUID,
    service: PipelineService = Depends(get_pipeline_service),
) -> Lead:
    lead = await service.analyze_fit(lead_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")
    return lead


@router.post("/leads/{lead_id}/find-contact", response_model=ContactFinderResult)
async def find_contact(
    lead_id: UUID,
    service: PipelineService = Depends(get_pipeline_service),
) -> ContactFinderResult:
    result = await service.find_contact_for_lead(lead_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")
    lead, contact_found, evidence = result
    return ContactFinderResult(
        lead=lead,
        contact_found=contact_found,
        contact_name=lead.contact_name,
        contact_email=lead.email,
        contact_role=lead.contact_role,
        contact_type=lead.contact_type,
        source_url=lead.contact_source_url,
        confidence_score=lead.contact_confidence_score or 0,
        verification_status=lead.contact_verification_status or "not_found",
        evidence=evidence,
    )


@router.post("/leads/{lead_id}/run-next-step", response_model=PipelineStepResult)
async def run_next_step(
    lead_id: UUID,
    service: PipelineService = Depends(get_pipeline_service),
) -> PipelineStepResult:
    result = await service.run_next_opportunity_step(lead_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")
    return PipelineStepResult(**result)


@router.post("/pipeline/run-batch", response_model=PipelineBatchRunResult)
async def run_pipeline_batch(
    payload: PipelineBatchRunRequest,
    service: PipelineService = Depends(get_pipeline_service),
) -> PipelineBatchRunResult:
    result = await service.run_pipeline_batch(payload)
    return PipelineBatchRunResult(**result)


@router.get("/contact-research", response_model=list[ContactResearch])
async def list_contact_research(
    service: PipelineService = Depends(get_pipeline_service),
) -> list[ContactResearch]:
    return await service.list_contact_research()


@router.post("/applications", response_model=Application, status_code=status.HTTP_201_CREATED)
async def create_application(
    payload: ApplicationCreate,
    service: PipelineService = Depends(get_pipeline_service),
) -> Application:
    application = await service.create_application(payload)
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Linked opportunity not found")
    return application


@router.get("/applications", response_model=list[Application])
async def list_applications(
    service: PipelineService = Depends(get_pipeline_service),
) -> list[Application]:
    return await service.list_applications()


@router.post("/leads/{lead_id}/track-application", response_model=Application, status_code=status.HTTP_201_CREATED)
async def track_application_from_lead(
    lead_id: UUID,
    service: PipelineService = Depends(get_pipeline_service),
) -> Application:
    application = await service.create_application_from_lead(lead_id)
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")
    return application


@router.post("/leads/{lead_id}/mark-applied", response_model=Application)
async def mark_application_applied_from_lead(
    lead_id: UUID,
    service: PipelineService = Depends(get_pipeline_service),
) -> Application:
    application = await service.mark_application_applied_from_lead(
        lead_id,
        note="Applied through the job/source page. No public outreach email was found.",
    )
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")
    return application


@router.post("/leads/{lead_id}/track-application-only", response_model=Application)
async def track_application_only_from_lead(
    lead_id: UUID,
    service: PipelineService = Depends(get_pipeline_service),
) -> Application:
    application = await service.track_application_only_from_lead(
        lead_id,
        note="Applied or saved through the job/source page. No public outreach email is available.",
    )
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")
    return application


@router.patch("/applications/{application_id}", response_model=Application)
async def update_application(
    application_id: UUID,
    payload: ApplicationUpdate,
    service: PipelineService = Depends(get_pipeline_service),
) -> Application:
    application = await service.update_application(application_id, payload)
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return application


@router.delete("/applications/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application(
    application_id: UUID,
    service: PipelineService = Depends(get_pipeline_service),
) -> None:
    deleted = await service.delete_application(application_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")


@router.post("/leads/{lead_id}/linkedin-connection-message", response_model=LinkedInConnectionMessageResult)
async def generate_linkedin_connection_message(
    lead_id: UUID,
    service: PipelineService = Depends(get_pipeline_service),
) -> LinkedInConnectionMessageResult:
    message = await service.generate_linkedin_connection_message(lead_id)
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")
    return LinkedInConnectionMessageResult(
        lead_id=lead_id,
        message=message,
        character_count=len(message),
        safety_note="Manual use only. The app does not send or automate LinkedIn messages.",
    )


@router.delete("/leads/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lead(
    lead_id: UUID,
    service: PipelineService = Depends(get_pipeline_service),
) -> None:
    deleted = await service.delete_lead(lead_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")


@router.post("/campaigns", response_model=Campaign, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    payload: CampaignCreate,
    service: PipelineService = Depends(get_pipeline_service),
) -> Campaign:
    return await service.create_campaign(payload)


@router.get("/campaigns", response_model=list[Campaign])
async def list_campaigns(service: PipelineService = Depends(get_pipeline_service)) -> list[Campaign]:
    return await service.list_campaigns()


@router.post("/drafts", response_model=EmailDraft, status_code=status.HTTP_201_CREATED)
async def create_draft(
    payload: DraftCreate,
    service: PipelineService = Depends(get_pipeline_service),
) -> EmailDraft:
    draft = await service.create_draft(payload)
    if draft is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact or campaign not found",
        )
    return draft


@router.get("/drafts", response_model=list[EmailDraft])
async def list_drafts(service: PipelineService = Depends(get_pipeline_service)) -> list[EmailDraft]:
    return await service.list_drafts()


@router.get("/draft-archives", response_model=list[DraftArchive])
async def list_draft_archives(
    service: PipelineService = Depends(get_pipeline_service),
) -> list[DraftArchive]:
    return await service.list_draft_archives()


@router.post("/drafts/generate", response_model=EmailDraft, status_code=status.HTTP_201_CREATED)
async def generate_draft(
    payload: DraftGenerateRequest,
    service: PipelineService = Depends(get_pipeline_service),
) -> EmailDraft:
    draft = await service.generate_mock_draft(payload)
    if draft is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact or campaign not found",
        )
    return draft


@router.patch("/drafts/{draft_id}", response_model=EmailDraft)
async def update_draft(
    draft_id: UUID,
    payload: DraftUpdate,
    service: PipelineService = Depends(get_pipeline_service),
) -> EmailDraft:
    draft = await service.update_draft(draft_id, payload)
    if draft is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Draft must exist and be pending approval before it can be edited",
        )
    return draft


@router.post("/drafts/{draft_id}/approve", response_model=EmailDraft)
async def approve_draft(
    draft_id: UUID,
    payload: ReviewDecision,
    service: PipelineService = Depends(get_pipeline_service),
) -> EmailDraft:
    draft = await service.approve_draft(draft_id, payload.reviewer, payload.note)
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    return draft


@router.post("/drafts/{draft_id}/reject", response_model=EmailDraft)
async def reject_draft(
    draft_id: UUID,
    payload: ReviewDecision,
    service: PipelineService = Depends(get_pipeline_service),
) -> EmailDraft:
    draft = await service.reject_draft(draft_id, payload.reviewer, payload.note)
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    return draft


@router.post("/drafts/{draft_id}/simulate-send", response_model=EmailDraft)
async def simulate_send_draft(
    draft_id: UUID,
    payload: SendDecision,
    service: PipelineService = Depends(get_pipeline_service),
) -> EmailDraft:
    try:
        draft = await service.send_draft(
            draft_id,
            payload.sender,
            payload.note,
            force_dry_run=True,
        )
    except EmailSendError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Email dry-run failed: {exc}",
        ) from exc
    if draft is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Draft must exist and be approved before it can be marked sent",
        )
    return draft


@router.post("/drafts/{draft_id}/send", response_model=EmailDraft)
async def send_draft(
    draft_id: UUID,
    payload: SendDecision,
    service: PipelineService = Depends(get_pipeline_service),
) -> EmailDraft:
    try:
        draft = await service.send_draft(draft_id, payload.sender, payload.note)
    except EmailSendError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Email send failed: {exc}",
        ) from exc
    if draft is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Draft must exist and be approved before it can be marked sent",
        )
    return draft


@router.post("/replies/classify", response_model=EmailReply, status_code=status.HTTP_201_CREATED)
async def classify_reply(
    payload: ReplyClassifyRequest,
    service: PipelineService = Depends(get_pipeline_service),
) -> EmailReply:
    reply = await service.classify_reply(payload)
    if reply is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Draft must exist and be sent before a reply can be classified",
        )
    return reply


@router.get("/replies", response_model=list[EmailReply])
async def list_replies(service: PipelineService = Depends(get_pipeline_service)) -> list[EmailReply]:
    return await service.list_replies()


@router.get("/audit-events", response_model=list[AuditEvent])
async def list_audit_events(
    service: PipelineService = Depends(get_pipeline_service),
) -> list[AuditEvent]:
    return await service.list_audit_events()
