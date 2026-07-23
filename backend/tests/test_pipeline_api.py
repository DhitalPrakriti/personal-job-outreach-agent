import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.agents.email_inbox import EmailInboxAgent, InboxMessage
from app.agents.company_research import CompanyResearchAgent, CompanyResearchResult
from app.db.models import Base
from app.db.session import async_session, init_db
from app.main import app
from app.schemas.pipeline import JobDiscoveryItem, LeadCreate
from app.services.notion_importer import NotionLeadImporter
from app.services.job_source_discovery import JobSourceDiscoveryService
from app.services.contact_finder import ContactFinderService, _PageParser


client = TestClient(app)


async def reset_database() -> None:
    await init_db()
    async with async_session() as session:
        for table in reversed(Base.metadata.sorted_tables):
            await session.execute(delete(table))
        await session.commit()


def setup_function() -> None:
    asyncio.run(reset_database())


def test_pipeline_approval_flow() -> None:
    lead_response = client.post(
        "/api/v1/leads",
        json={
            "email": "rory@example.com",
            "first_name": "Rory",
            "last_name": "G",
            "company": "Example Co",
            "title": "Engineering Manager",
            "source": "manual",
        },
    )
    assert lead_response.status_code == 201
    lead = lead_response.json()
    assert lead["status"] == "new"

    campaign_response = client.post(
        "/api/v1/campaigns",
        json={
            "name": "Tech Opportunity Outreach",
            "module": "Job Search",
            "objective": "Validate human-approved personal outreach flow.",
        },
    )
    assert campaign_response.status_code == 201
    campaign = campaign_response.json()

    draft_response = client.post(
        "/api/v1/drafts",
        json={
            "lead_id": lead["id"],
            "campaign_id": campaign["id"],
            "subject": "Quick question about Example Co",
            "body": "Hi Rory, I had a practical question about opportunities at Example Co.",
            "generated_by": "manual",
            "context_summary": "Draft created without external AI calls.",
        },
    )
    assert draft_response.status_code == 201
    draft = draft_response.json()
    assert draft["status"] == "pending_approval"

    refreshed_lead = client.get(f"/api/v1/leads/{lead['id']}").json()
    assert refreshed_lead["status"] == "draft_ready"

    approval_response = client.post(
        f"/api/v1/drafts/{draft['id']}/approve",
        json={"reviewer": "Prakriti", "note": "Approved for MVP test."},
    )
    assert approval_response.status_code == 200
    approved = approval_response.json()
    assert approved["status"] == "approved"
    assert approved["reviewer"] == "Prakriti"

    final_lead = client.get(f"/api/v1/leads/{lead['id']}").json()
    assert final_lead["status"] == "approved"

    audit_events = client.get("/api/v1/audit-events").json()
    assert [event["action"] for event in audit_events] == [
        "lead_created",
        "campaign_created",
        "draft_created",
        "draft_approved",
    ]


def test_create_draft_requires_existing_lead() -> None:
    response = client.post(
        "/api/v1/drafts",
        json={
            "lead_id": "00000000-0000-0000-0000-000000000000",
            "subject": "Missing lead",
            "body": "This should fail.",
        },
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Contact or campaign not found"


def test_batch_create_leads() -> None:
    response = client.post(
        "/api/v1/leads/batch",
        json=[
            {
                "email": "lead.one@example.com",
                "first_name": "Lead",
                "last_name": "One",
                "company": "Example Co",
            },
            {
                "email": "lead.two@example.com",
                "first_name": "Lead",
                "last_name": "Two",
                "company": "Example Co",
            },
        ],
    )

    assert response.status_code == 201
    leads = response.json()
    assert len(leads) == 2
    assert leads[0]["status"] == "new"

    listed_leads = client.get("/api/v1/leads").json()
    assert [lead["email"] for lead in listed_leads] == [
        "lead.one@example.com",
        "lead.two@example.com",
    ]

    audit_events = client.get("/api/v1/audit-events").json()
    assert [event["action"] for event in audit_events] == [
        "lead_created",
        "lead_created",
    ]


def test_notion_import_route_upserts_leads(monkeypatch) -> None:
    async def fake_fetch_leads(
        self,
        database_id=None,
        data_source_id=None,
        max_pages=100,
    ) -> list[LeadCreate]:
        return [
            LeadCreate(
                first_name="Neil",
                last_name="Jensen",
                company="Steadyhand Investment Funds",
                title="Chief Executive Officer",
                source="notion_contact_source",
                notion_page_id="notion-page-1",
                linkedin_url="https://linkedin.com/in/neil",
                lead_grade="B-Lead",
                outreach_status="Not Contacted",
                suggested_first_message="Hi Neil, I saw your work at Steadyhand.",
            )
        ]

    monkeypatch.setattr(NotionLeadImporter, "fetch_leads", fake_fetch_leads)

    response = client.post(
        "/api/v1/integrations/notion/import-leads",
        json={"data_source_id": "fake-data-source", "max_pages": 10},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["imported"] == 1
    assert payload["updated"] == 0
    assert payload["skipped"] == 0
    assert payload["leads"][0]["email"] is None
    assert payload["leads"][0]["notion_page_id"] == "notion-page-1"
    assert payload["leads"][0]["lead_grade"] == "B-Lead"

    second_response = client.post(
        "/api/v1/integrations/notion/import-leads",
        json={"data_source_id": "fake-data-source", "max_pages": 10},
    )

    assert second_response.status_code == 200
    second_payload = second_response.json()
    assert second_payload["imported"] == 0
    assert second_payload["updated"] == 1

    audit_events = client.get("/api/v1/audit-events").json()
    assert [event["action"] for event in audit_events] == [
        "lead_imported",
        "lead_imported",
    ]


def test_profile_settings_defaults_and_updates() -> None:
    default_response = client.get("/api/v1/profile")
    assert default_response.status_code == 200
    default_profile = default_response.json()
    assert default_profile["owner_name"] == "Prakriti Dhital"
    assert default_profile["primary_email"] == "prakriti.dhital.tech@gmail.com"
    assert "Backend Developer" in default_profile["target_roles"]
    assert "Remote Canada" in default_profile["target_locations"]
    assert "Python" in default_profile["target_skills"]

    update_response = client.put(
        "/api/v1/profile",
        json={
            "owner_name": "Prakriti Dhital",
            "primary_email": "prakriti.dhital.tech@gmail.com",
            "outreach_email": "prakriti.dhital.tech@gmail.com",
            "target_roles": ["Junior AI Engineer", "Backend Developer"],
            "target_locations": ["Canada", "Vancouver"],
            "target_skills": ["Python", "FastAPI", "React"],
            "resume_summary": "AI/backend automation profile.",
            "github_url": "https://github.com/prakriti",
            "default_resume_version": "Resume - AI Backend v2",
        },
    )
    assert update_response.status_code == 200
    profile = update_response.json()
    assert profile["target_roles"] == ["Junior AI Engineer", "Backend Developer"]
    assert profile["target_locations"] == ["Canada", "Vancouver"]
    assert profile["target_skills"] == ["Python", "FastAPI", "React"]
    assert profile["default_resume_version"] == "Resume - AI Backend v2"

    audit_events = client.get("/api/v1/audit-events").json()
    assert audit_events[-1]["action"] == "profile_updated"


def test_career_source_create_update_delete_flow() -> None:
    create_response = client.post(
        "/api/v1/career-sources",
        json={
            "company_name": "Example AI Labs",
            "careers_url": "https://example.com/careers",
            "source_type": "company_careers",
            "notes": "Scan weekly for junior backend and AI roles.",
        },
    )
    assert create_response.status_code == 201
    source = create_response.json()
    assert source["company_name"] == "Example AI Labs"
    assert source["careers_url"] == "https://example.com/careers"
    assert source["active"] is True

    duplicate_response = client.post(
        "/api/v1/career-sources",
        json={
            "company_name": "Duplicate",
            "careers_url": "https://example.com/careers",
        },
    )
    assert duplicate_response.status_code == 409

    list_response = client.get("/api/v1/career-sources")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    update_response = client.patch(
        f"/api/v1/career-sources/{source['id']}",
        json={"active": False, "notes": "Pause this source for now."},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["active"] is False
    assert updated["notes"] == "Pause this source for now."

    delete_response = client.delete(f"/api/v1/career-sources/{source['id']}")
    assert delete_response.status_code == 204
    assert client.get("/api/v1/career-sources").json() == []

    audit_events = client.get("/api/v1/audit-events").json()
    assert [event["action"] for event in audit_events] == [
        "career_source_created",
        "career_source_updated",
        "career_source_deleted",
    ]


def test_career_source_scan_imports_discovered_jobs(monkeypatch) -> None:
    async def fake_discover(self, payload):
        assert payload.source_urls == ["https://example.com/careers"]
        assert payload.target_roles == ["Backend Developer"]
        assert payload.target_locations == ["Remote Canada"]
        assert payload.target_skills == ["Python"]
        return SimpleNamespace(
            scanned_sources=1,
            jobs=[
                JobDiscoveryItem(
                    company="Example Co",
                    title="Backend Developer",
                    location="Remote Canada",
                    url="https://example.com/jobs/backend",
                    description="Build Python services and internal automation.",
                    source_links="https://example.com/careers",
                    source="company_careers",
                )
            ],
            errors=[],
        )

    monkeypatch.setattr(JobSourceDiscoveryService, "discover", fake_discover)

    source = client.post(
        "/api/v1/career-sources",
        json={
            "company_name": "Example Co",
            "careers_url": "https://example.com/careers",
        },
    ).json()

    response = client.post(
        "/api/v1/career-sources/scan",
        json={
            "career_source_ids": [source["id"]],
            "target_roles": ["Backend Developer"],
            "target_locations": ["Remote Canada"],
            "target_skills": ["Python"],
            "import_results": True,
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["scanned_sources"] == 1
    assert payload["discovered"] == 1
    assert payload["imported"] == 1
    assert payload["skipped"] == 0
    assert payload["jobs"][0]["company"] == "Example Co"

    refreshed_source = client.get("/api/v1/career-sources").json()[0]
    assert refreshed_source["last_scanned_at"] is not None
    assert refreshed_source["last_result_count"] == 1
    assert refreshed_source["last_error"] is None

    opportunities = client.get("/api/v1/leads").json()
    assert len(opportunities) == 1
    assert opportunities[0]["company"] == "Example Co"
    assert opportunities[0]["title"] == "Backend Developer"
    assert opportunities[0]["source"] == "company_careers"
    assert opportunities[0]["status"] == "new"
    assert opportunities[0]["outreach_status"] == "ANALYZED"

    audit_events = client.get("/api/v1/audit-events").json()
    assert [event["action"] for event in audit_events] == [
        "career_source_created",
        "opportunity_imported",
        "opportunity_analyzed",
        "career_source_scanned",
    ]


def test_run_next_step_analyzes_discovered_opportunity() -> None:
    lead = client.post(
        "/api/v1/leads",
        json={
            "first_name": "Hiring Team",
            "company": "Pipeline Co",
            "title": "Backend Developer",
            "source": "company_careers",
            "opportunity_url": "https://pipeline.example/jobs/backend",
            "opportunity_location": "Remote Canada",
            "opportunity_description": "Python FastAPI backend automation role.",
            "outreach_status": "DISCOVERED",
        },
    ).json()

    response = client.post(f"/api/v1/leads/{lead['id']}/run-next-step")

    assert response.status_code == 200
    payload = response.json()
    assert payload["action"] == "analyze_fit"
    assert payload["draft"] is None
    assert payload["requires_human_review"] is False
    assert payload["lead"]["fit_score"] is not None
    assert payload["lead"]["outreach_status"] == "ANALYZED"


def test_run_next_step_creates_draft_then_stops_for_human_review() -> None:
    lead = client.post(
        "/api/v1/leads",
        json={
            "email": "recruiter@example.com",
            "first_name": "Recruiting Team",
            "company": "Review Co",
            "title": "Junior AI Engineer",
            "source": "manual_job_target",
            "opportunity_url": "https://review.example/jobs/ai",
            "opportunity_location": "Remote Canada",
            "opportunity_description": "Build AI workflow automation with Python and React.",
            "company_summary": "Technical team building workflow automation tools.",
            "fit_score": 90,
            "outreach_status": "CONTACT_FOUND",
        },
    ).json()

    response = client.post(f"/api/v1/leads/{lead['id']}/run-next-step")

    assert response.status_code == 200
    payload = response.json()
    assert payload["action"] == "generate_draft"
    assert payload["requires_human_review"] is True
    assert payload["draft"]["status"] == "pending_approval"
    assert payload["lead"]["outreach_status"] == "PENDING_APPROVAL"

    second_response = client.post(f"/api/v1/leads/{lead['id']}/run-next-step")
    assert second_response.status_code == 200
    assert second_response.json()["action"] == "human_review_required"


def test_pipeline_batch_advances_safe_steps_without_generating_drafts() -> None:
    discovered = client.post(
        "/api/v1/leads",
        json={
            "first_name": "Hiring Team",
            "company": "Batch Analyze Co",
            "title": "Software Developer",
            "source": "company_careers",
            "opportunity_location": "Canada",
            "opportunity_description": "Python React software role.",
            "outreach_status": "DISCOVERED",
        },
    ).json()
    contact_found = client.post(
        "/api/v1/leads",
        json={
            "email": "careers@example.com",
            "first_name": "Recruiting Team",
            "company": "Batch Draft Co",
            "title": "Backend Developer",
            "source": "company_careers",
            "fit_score": 85,
            "company_summary": "Company already researched.",
            "outreach_status": "CONTACT_FOUND",
        },
    ).json()

    response = client.post(
        "/api/v1/pipeline/run-batch",
        json={
            "stages": ["DISCOVERED", "CONTACT_FOUND"],
            "limit": 10,
            "allow_draft_generation": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["scanned"] == 2
    assert payload["advanced"] == 1
    assert payload["skipped"] == 1
    assert [result["action"] for result in payload["results"]] == [
        "analyze_fit",
        "draft_generation_skipped",
    ]

    refreshed_discovered = client.get(f"/api/v1/leads/{discovered['id']}").json()
    refreshed_contact_found = client.get(f"/api/v1/leads/{contact_found['id']}").json()
    assert refreshed_discovered["outreach_status"] == "ANALYZED"
    assert refreshed_contact_found["outreach_status"] == "CONTACT_FOUND"
    assert client.get("/api/v1/drafts").json() == []


def test_company_research_agent_extracts_public_page_signals(monkeypatch) -> None:
    lead = client.post(
        "/api/v1/leads",
        json={
            "first_name": "Hiring Team",
            "company": "Signal Co",
            "title": "Backend Developer",
            "source": "company_careers",
            "opportunity_url": "https://signal.example/jobs/backend",
            "opportunity_description": "Build Python APIs and React workflow tools.",
            "outreach_status": "ANALYZED",
        },
    ).json()

    async def fake_fetch_public_pages(self, lead_model):
        assert lead_model.company == "Signal Co"
        return [
            {
                "url": "https://signal.example/about",
                "title": "Signal Co - AI Workflow Platform",
                "description": "Signal Co builds automation products for operations teams.",
                "text": "We use Python FastAPI React PostgreSQL and GCP for customer workflow automation.",
                "links": [],
            }
        ]

    monkeypatch.setattr(CompanyResearchAgent, "_fetch_public_pages", fake_fetch_public_pages)

    response = client.post(f"/api/v1/leads/{lead['id']}/research-company")

    assert response.status_code == 200
    researched = response.json()
    assert "Public pages reviewed" in researched["company_summary"]
    assert "Signal Co - AI Workflow Platform" in researched["company_summary"]
    assert "Python" in researched["tech_stack"]
    assert "FastAPI" in researched["tech_stack"]
    assert "React" in researched["tech_stack"]
    assert "https://signal.example/about" in researched["source_links"]
    assert researched["outreach_status"] == "COMPANY_RESEARCHED"


def test_research_company_route_saves_enriched_agent_result(monkeypatch) -> None:
    async def fake_research(self, lead_model):
        return CompanyResearchResult(
            company_summary="Enriched public company summary.",
            suggested_context="Use enriched public company context.",
            tech_stack="Python, FastAPI, GCP",
            role_fit="Backend role aligned with Python API automation.",
            source_links="https://company.example/about\nhttps://company.example/careers",
            evidence=["Company public about page reviewed."],
        )

    monkeypatch.setattr(CompanyResearchAgent, "research", fake_research)

    lead = client.post(
        "/api/v1/leads",
        json={
            "first_name": "Hiring Team",
            "company": "Enriched Co",
            "title": "Junior AI Engineer",
            "source": "company_careers",
            "opportunity_url": "https://company.example/jobs/ai",
            "tech_stack": "React",
            "outreach_status": "ANALYZED",
        },
    ).json()

    response = client.post(f"/api/v1/leads/{lead['id']}/research-company")

    assert response.status_code == 200
    researched = response.json()
    assert researched["company_summary"] == "Enriched public company summary."
    assert researched["tech_stack"] == "React, Python, FastAPI, GCP"
    assert researched["role_fit"] == "Backend role aligned with Python API automation."
    assert "https://company.example/about" in researched["source_links"]
    assert researched["suggested_first_message"] == "Use enriched public company context."


def test_contact_finder_skips_platform_urls_and_expands_company_sources() -> None:
    urls = ContactFinderService._seed_urls(
        None,
        "https://www.linkedin.com/jobs/view/123",
        "https://company.example/careers\nhttps://ca.indeed.com/viewjob?jk=123",
    )

    assert "https://www.linkedin.com/jobs/view/123" not in urls
    assert "https://ca.indeed.com/viewjob?jk=123" not in urls
    assert "https://company.example/careers" in urls
    assert "https://company.example/contact" in urls
    assert "https://company.example/people" in urls


def test_contact_finder_reads_mailto_and_prioritizes_recruiting_emails() -> None:
    parser = _PageParser()
    parser.feed(
        """
        <html>
          <body>
            <a href="mailto:info@signal.dev">General</a>
            <a href="mailto:talent@signal.dev">Talent</a>
            <a href="mailto:no-reply@signal.dev">Ignore</a>
          </body>
        </html>
        """
    )

    candidate = ContactFinderService()._candidate_from_page(
        "https://signal.dev/careers",
        parser,
        "Contact our team at hello@signal.dev",
        None,
    )

    assert candidate.contact_email == "talent@signal.dev"
    assert candidate.contact_type == "careers_or_recruiting_email"
    assert candidate.verification_status == "public_email_found"
    assert candidate.confidence_score >= 90


def test_linkedin_tracker_import_creates_opportunity_contact_research_and_actions() -> None:
    job_url = "https://www.linkedin.com/jobs/view/1234567890"
    recruiter_url = "https://www.linkedin.com/in/jordan-recruiter"
    response = client.post(
        "/api/v1/source-trackers/linkedin/import",
        json={
            "target_roles": ["Junior AI Engineer", "Backend Developer"],
            "target_locations": ["Canada", "Remote Canada"],
            "target_skills": ["Python", "FastAPI", "React"],
            "opportunities": [
                {
                    "source_url": job_url,
                    "company_name": "Example AI",
                    "job_title": "Junior AI Engineer",
                    "location": "Remote Canada",
                    "description": "Build Python and FastAPI automation tools with React dashboards.",
                    "required_skills": ["Python", "FastAPI", "React"],
                    "recruiter_profile_url": recruiter_url,
                    "recruiter_name": "Jordan Recruiter",
                    "notes": "Strong portfolio fit; mention practical AI automation work.",
                }
            ],
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["source"] == "LINKEDIN"
    assert payload["imported"] == 1
    lead = payload["leads"][0]
    assert lead["source"] == "LINKEDIN"
    assert lead["opportunity_url"] == job_url
    assert lead["company"] == "Example AI"
    assert lead["title"] == "Junior AI Engineer"
    assert lead["opportunity_location"] == "Remote Canada"
    assert "FastAPI automation" in lead["opportunity_description"]
    assert "Python" in lead["tech_stack"]
    assert lead["contact_name"] == "Jordan Recruiter"
    assert lead["contact_source_url"] == recruiter_url
    assert lead["contact_type"] == "recruiter_profile"
    assert lead["fit_score"] >= 75

    opportunities = client.get("/api/v1/opportunities").json()
    assert len(opportunities) == 1
    assert opportunities[0]["source"] == "LINKEDIN"
    assert opportunities[0]["source_url"] == job_url
    assert opportunities[0]["required_skills"] == ["Python", "FastAPI", "React"]

    contact_research = client.get("/api/v1/contact-research").json()
    assert len(contact_research) == 1
    assert contact_research[0]["lead_id"] == lead["id"]
    assert contact_research[0]["contact_name"] == "Jordan Recruiter"
    assert contact_research[0]["source_url"] == recruiter_url
    assert contact_research[0]["verification_status"] == "manual_profile_tracked"

    analyze_response = client.post(f"/api/v1/leads/{lead['id']}/analyze-fit")
    assert analyze_response.status_code == 200
    assert analyze_response.json()["fit_score"] >= 75

    linkedin_message_response = client.post(f"/api/v1/leads/{lead['id']}/linkedin-connection-message")
    assert linkedin_message_response.status_code == 200
    linkedin_message = linkedin_message_response.json()
    assert linkedin_message["safety_note"] == "Manual use only. The app does not send or automate LinkedIn messages."
    assert linkedin_message["character_count"] <= linkedin_message["max_character_count"]

    draft_response = client.post(
        "/api/v1/drafts/generate",
        json={
            "lead_id": lead["id"],
            "call_to_action": "Open to a 15-minute conversation?",
            "extra_context": "Use the LinkedIn opportunity and recruiter profile context.",
        },
    )
    assert draft_response.status_code == 201
    assert draft_response.json()["status"] == "pending_approval"

    audit_actions = [event["action"] for event in client.get("/api/v1/audit-events").json()]
    assert "opportunity_imported" in audit_actions
    assert "contact_searched" in audit_actions
    assert audit_actions.count("opportunity_analyzed") == 2
    assert "linkedin_message_created" in audit_actions
    assert "draft_created" in audit_actions


def test_application_tracker_supports_manual_and_opportunity_linked_applications() -> None:
    manual_response = client.post(
        "/api/v1/applications",
        json={
            "company_name": "Manual Co",
            "job_title": "Backend Developer",
            "source": "Company Site",
            "job_url": "https://manual.example/jobs/backend",
            "location": "Remote Canada",
            "status": "APPLIED",
            "applied_date": "2026-07-18",
            "resume_version": "Resume - Backend v1",
            "cover_letter_version": "Cover Letter - Manual Co",
            "contact_found": False,
            "notes": "Applied manually on company site.",
        },
    )

    assert manual_response.status_code == 201
    manual = manual_response.json()
    assert manual["company_name"] == "Manual Co"
    assert manual["status"] == "APPLIED"
    assert manual["applied_date"] == "2026-07-18"

    opportunity_response = client.post(
        "/api/v1/source-trackers/linkedin/import",
        json={
            "target_roles": ["Software Developer"],
            "target_locations": ["Canada"],
            "target_skills": ["Python"],
            "opportunities": [
                {
                    "source_url": "https://www.linkedin.com/jobs/view/999",
                    "company_name": "Tracked AI",
                    "job_title": "Software Developer",
                    "location": "Canada",
                    "description": "Python platform role.",
                    "required_skills": ["Python"],
                }
            ],
        },
    )
    lead = opportunity_response.json()["leads"][0]

    track_response = client.post(f"/api/v1/leads/{lead['id']}/track-application")
    assert track_response.status_code == 201
    tracked = track_response.json()
    assert tracked["lead_id"] == lead["id"]
    assert tracked["company_name"] == "Tracked AI"
    assert tracked["job_title"] == "Software Developer"
    assert tracked["source"] == "LinkedIn"
    assert tracked["status"] == "SAVED"

    duplicate_track_response = client.post(f"/api/v1/leads/{lead['id']}/track-application")
    assert duplicate_track_response.status_code == 201
    assert duplicate_track_response.json()["id"] == tracked["id"]

    update_response = client.patch(
        f"/api/v1/applications/{tracked['id']}",
        json={"status": "INTERVIEW", "contact_found": True},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["status"] == "INTERVIEW"
    assert updated["contact_found"] is True

    refreshed_lead = client.get(f"/api/v1/leads/{lead['id']}").json()
    assert refreshed_lead["outreach_status"] == "REPLIED"

    applications = client.get("/api/v1/applications").json()
    assert len(applications) == 2

    delete_response = client.delete(f"/api/v1/applications/{manual['id']}")
    assert delete_response.status_code == 204
    assert len(client.get("/api/v1/applications").json()) == 1

    audit_actions = [event["action"] for event in client.get("/api/v1/audit-events").json()]
    assert "application_created" in audit_actions
    assert "application_updated" in audit_actions
    assert "application_deleted" in audit_actions


def test_generate_mock_draft_creates_pending_approval_draft() -> None:
    lead = client.post(
        "/api/v1/leads",
        json={
            "email": "ian@example.com",
            "first_name": "Ian",
            "company": "Example Co",
            "source": "manual",
        },
    ).json()
    campaign = client.post(
        "/api/v1/campaigns",
        json={
            "name": "Networking Follow-Up Test",
            "module": "Job Search",
            "objective": "Start a relevant career conversation",
        },
    ).json()

    response = client.post(
        "/api/v1/drafts/generate",
        json={
            "lead_id": lead["id"],
            "campaign_id": campaign["id"],
            "call_to_action": "Open to a brief conversation next week?",
            "extra_context": "Use a concise job-search networking tone.",
        },
    )

    assert response.status_code == 201
    draft = response.json()
    assert draft["status"] == "pending_approval"
    assert draft["generated_by"] == "mock_generator"
    assert draft["subject"] == "Quick idea for Example Co"
    assert "Hi Ian" in draft["body"]
    assert "Open to a brief conversation next week?" in draft["body"]
    assert "Use a concise job-search networking tone." in draft["context_summary"]


def test_approved_draft_can_be_marked_sent_without_real_email() -> None:
    lead = client.post(
        "/api/v1/leads",
        json={
            "email": "test.lead@example.com",
            "first_name": "Test",
            "company": "Example Co",
        },
    ).json()
    draft = client.post(
        "/api/v1/drafts/generate",
        json={"lead_id": lead["id"]},
    ).json()

    early_send = client.post(
        f"/api/v1/drafts/{draft['id']}/simulate-send",
        json={"sender": "Prakriti", "note": "Trying before approval."},
    )
    assert early_send.status_code == 400

    client.post(
        f"/api/v1/drafts/{draft['id']}/approve",
        json={"reviewer": "Prakriti", "note": "Approved for send simulation."},
    )

    send_response = client.post(
        f"/api/v1/drafts/{draft['id']}/simulate-send",
        json={"sender": "Prakriti", "note": "Marked sent locally only."},
    )
    assert send_response.status_code == 200
    sent = send_response.json()
    assert sent["status"] == "sent"
    assert sent["review_note"] == "Marked sent locally only."

    refreshed_lead = client.get(f"/api/v1/leads/{lead['id']}").json()
    assert refreshed_lead["status"] == "sent"

    audit_events = client.get("/api/v1/audit-events").json()
    assert audit_events[-1]["action"] == "draft_sent"


def test_sent_draft_reply_can_be_classified_without_ai() -> None:
    lead = client.post(
        "/api/v1/leads",
        json={
            "email": "recruiter@example.com",
            "first_name": "Recruiter",
            "company": "Example Co",
            "title": "Backend Developer",
        },
    ).json()
    application = client.post(
        "/api/v1/applications",
        json={
            "lead_id": lead["id"],
            "company_name": "Example Co",
            "job_title": "Backend Developer",
            "source": "Company Site",
        },
    ).json()
    draft = client.post(
        "/api/v1/drafts/generate",
        json={"lead_id": lead["id"]},
    ).json()
    assert client.get("/api/v1/applications").json()[0]["status"] == "OUTREACH_DRAFTED"
    client.post(
        f"/api/v1/drafts/{draft['id']}/approve",
        json={"reviewer": "Prakriti", "note": "Approved."},
    )
    assert client.get("/api/v1/applications").json()[0]["status"] == "OUTREACH_APPROVED"
    client.post(
        f"/api/v1/drafts/{draft['id']}/simulate-send",
        json={"sender": "Prakriti", "note": "Marked sent locally."},
    )
    assert client.get("/api/v1/applications").json()[0]["status"] == "OUTREACH_SENT"

    reply_response = client.post(
        "/api/v1/replies/classify",
        json={
            "draft_id": draft["id"],
            "from_email": "recruiter@example.com",
            "body": "This is interesting. Can we schedule a call?",
        },
    )

    assert reply_response.status_code == 201
    reply = reply_response.json()
    assert reply["intent"] == "interested"
    assert reply["classification_reason"] == "Matched positive intent language."

    refreshed_lead = client.get(f"/api/v1/leads/{lead['id']}").json()
    assert refreshed_lead["status"] == "replied"

    replies = client.get("/api/v1/replies").json()
    assert len(replies) == 1
    assert replies[0]["draft_id"] == draft["id"]

    refreshed_application = client.get("/api/v1/applications").json()[0]
    assert refreshed_application["id"] == application["id"]
    assert refreshed_application["status"] == "REPLIED"

    audit_events = client.get("/api/v1/audit-events").json()
    assert "reply_classified" in [event["action"] for event in audit_events]


def test_email_reply_sync_matches_application_by_gmail_thread(monkeypatch) -> None:
    lead = client.post(
        "/api/v1/leads",
        json={
            "email": "known.recruiter@example.com",
            "first_name": "Recruiter",
            "company": "Thread Match Co",
            "title": "AI Engineer",
        },
    ).json()
    application = client.post(
        "/api/v1/applications",
        json={
            "lead_id": lead["id"],
            "company_name": "Thread Match Co",
            "job_title": "AI Engineer",
            "source": "LinkedIn",
            "gmail_thread_id": "gmail-thread-123",
        },
    ).json()
    draft = client.post("/api/v1/drafts/generate", json={"lead_id": lead["id"]}).json()
    client.post(f"/api/v1/drafts/{draft['id']}/approve", json={"reviewer": "Prakriti"})
    client.post(f"/api/v1/drafts/{draft['id']}/simulate-send", json={"sender": "Prakriti"})

    async def fake_fetch_recent(self):
        return [
            InboxMessage(
                provider_message_id="gmail-message-abc",
                provider_thread_id="gmail-thread-123",
                from_email="different.sender@example.com",
                subject="Re: AI Engineer",
                body="Can we schedule an interview next week?",
                received_at=datetime.now(UTC),
            )
        ]

    monkeypatch.setattr(EmailInboxAgent, "fetch_recent", fake_fetch_recent)

    response = client.post("/api/v1/integrations/email/sync-replies")
    assert response.status_code == 200
    payload = response.json()
    assert payload["matched"] == 1
    assert payload["imported"] == 1
    assert payload["replies"][0]["provider_thread_id"] == "gmail-thread-123"
    assert payload["replies"][0]["intent"] == "interview"

    refreshed_application = client.get("/api/v1/applications").json()[0]
    assert refreshed_application["id"] == application["id"]
    assert refreshed_application["status"] == "INTERVIEW"
    assert refreshed_application["gmail_thread_id"] == "gmail-thread-123"


def test_reply_classification_requires_sent_draft() -> None:
    lead = client.post(
        "/api/v1/leads",
        json={
            "email": "recruiter@example.com",
            "first_name": "Recruiter",
        },
    ).json()
    draft = client.post(
        "/api/v1/drafts/generate",
        json={"lead_id": lead["id"]},
    ).json()

    response = client.post(
        "/api/v1/replies/classify",
        json={
            "draft_id": draft["id"],
            "from_email": "recruiter@example.com",
            "body": "Interested.",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Draft must exist and be sent before a reply can be classified"
