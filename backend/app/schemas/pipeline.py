"""Schemas for the personal outreach workflow."""

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class LeadStatus(StrEnum):
    NEW = "new"
    RESEARCHED = "researched"
    DRAFT_READY = "draft_ready"
    APPROVED = "approved"
    REJECTED = "rejected"
    SENT = "sent"
    REPLIED = "replied"


class CampaignStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETE = "complete"


class DraftStatus(StrEnum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    SENT = "sent"


class ReplyIntent(StrEnum):
    INTERESTED = "interested"
    INTERVIEW = "interview"
    RESUME_REQUESTED = "resume_requested"
    NOT_INTERESTED = "not_interested"
    UNSUBSCRIBE = "unsubscribe"
    OUT_OF_OFFICE = "out_of_office"
    BOUNCE = "bounce"
    UNCLEAR = "unclear"
    NEUTRAL = "neutral"


class ApplicationStatus(StrEnum):
    SAVED = "SAVED"
    APPLIED = "APPLIED"
    CONTACT_SEARCH_NEEDED = "CONTACT_SEARCH_NEEDED"
    CONTACT_FOUND = "CONTACT_FOUND"
    OUTREACH_DRAFTED = "OUTREACH_DRAFTED"
    OUTREACH_APPROVED = "OUTREACH_APPROVED"
    OUTREACH_SENT = "OUTREACH_SENT"
    REPLIED = "REPLIED"
    INTERVIEW = "INTERVIEW"
    REJECTED = "REJECTED"
    FOLLOW_UP_DUE = "FOLLOW_UP_DUE"
    CLOSED = "CLOSED"


class PipelineStage(StrEnum):
    DISCOVERED = "DISCOVERED"
    ANALYZED = "ANALYZED"
    COMPANY_RESEARCHED = "COMPANY_RESEARCHED"
    CONTACT_SEARCH_NEEDED = "CONTACT_SEARCH_NEEDED"
    CONTACT_FOUND = "CONTACT_FOUND"
    DRAFTED = "DRAFTED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    SENT = "SENT"
    REPLIED = "REPLIED"
    FOLLOW_UP_DUE = "FOLLOW_UP_DUE"
    CLOSED = "CLOSED"


class AuditAction(StrEnum):
    LEAD_CREATED = "lead_created"
    LEAD_IMPORTED = "lead_imported"
    OPPORTUNITY_IMPORTED = "opportunity_imported"
    OPPORTUNITY_ANALYZED = "opportunity_analyzed"
    COMPANY_RESEARCHED = "company_researched"
    CONTACT_SEARCHED = "contact_searched"
    LINKEDIN_MESSAGE_CREATED = "linkedin_message_created"
    APPLICATION_CREATED = "application_created"
    APPLICATION_UPDATED = "application_updated"
    APPLICATION_DELETED = "application_deleted"
    PROFILE_UPDATED = "profile_updated"
    CAREER_SOURCE_CREATED = "career_source_created"
    CAREER_SOURCE_UPDATED = "career_source_updated"
    CAREER_SOURCE_DELETED = "career_source_deleted"
    CAREER_SOURCE_SCANNED = "career_source_scanned"
    CAMPAIGN_CREATED = "campaign_created"
    DRAFT_CREATED = "draft_created"
    DRAFT_UPDATED = "draft_updated"
    DRAFT_APPROVED = "draft_approved"
    DRAFT_REJECTED = "draft_rejected"
    DRAFT_SENT = "draft_sent"
    DRAFT_ARCHIVED = "draft_archived"
    REPLY_CLASSIFIED = "reply_classified"
    REPLY_SYNCED = "reply_synced"


class LeadCreate(BaseModel):
    email: EmailStr | None = None
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    company: str | None = Field(default=None, max_length=200)
    title: str | None = Field(default=None, max_length=200)
    source: str = Field(default="manual", max_length=100)
    notes: str | None = Field(default=None, max_length=2000)
    linkedin_url: str | None = Field(default=None, max_length=500)
    lead_grade: str | None = Field(default=None, max_length=100)
    outreach_status: str | None = Field(default=None, max_length=100)
    suggested_first_message: str | None = Field(default=None, max_length=5000)
    opportunity_url: str | None = Field(default=None, max_length=500)
    opportunity_location: str | None = Field(default=None, max_length=200)
    opportunity_description: str | None = Field(default=None, max_length=4000)
    company_summary: str | None = Field(default=None, max_length=2000)
    tech_stack: str | None = Field(default=None, max_length=1000)
    role_fit: str | None = Field(default=None, max_length=2000)
    source_links: str | None = Field(default=None, max_length=2000)
    fit_score: int | None = Field(default=None, ge=0, le=100)
    contact_name: str | None = Field(default=None, max_length=200)
    contact_role: str | None = Field(default=None, max_length=200)
    contact_type: str | None = Field(default=None, max_length=100)
    contact_source_url: str | None = Field(default=None, max_length=500)
    contact_confidence_score: int | None = Field(default=None, ge=0, le=100)
    contact_verification_status: str | None = Field(default=None, max_length=100)


class LeadContactUpdate(BaseModel):
    email: EmailStr
    contact_name: str | None = Field(default=None, max_length=200)
    contact_role: str | None = Field(default=None, max_length=200)
    contact_source_url: str | None = Field(default=None, max_length=500)
    note: str | None = Field(default=None, max_length=500)

    @field_validator("contact_name", "contact_role", "contact_source_url", "note", mode="before")
    @classmethod
    def blank_to_none(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value


class JobDiscoveryItem(BaseModel):
    company: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=200)
    location: str | None = Field(default=None, max_length=200)
    url: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=4000)
    company_summary: str | None = Field(default=None, max_length=2000)
    tech_stack: str | None = Field(default=None, max_length=1000)
    role_fit: str | None = Field(default=None, max_length=2000)
    source_links: str | None = Field(default=None, max_length=2000)
    contact_email: EmailStr | None = None
    contact_name: str | None = Field(default=None, max_length=200)
    contact_url: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=2000)
    source: str = Field(default="manual_discovery", max_length=100)

    @field_validator(
        "location",
        "url",
        "description",
        "company_summary",
        "tech_stack",
        "role_fit",
        "source_links",
        "contact_email",
        "contact_name",
        "contact_url",
        "notes",
        mode="before",
    )
    @classmethod
    def blank_to_none(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value


class JobDiscoveryImportRequest(BaseModel):
    target_roles: list[str] = Field(default_factory=list)
    target_locations: list[str] = Field(default_factory=list)
    target_skills: list[str] = Field(default_factory=list)
    jobs: list[JobDiscoveryItem] = Field(min_length=1, max_length=200)


class JobSourceDiscoveryRequest(BaseModel):
    target_roles: list[str] = Field(default_factory=list)
    target_locations: list[str] = Field(default_factory=list)
    target_skills: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(min_length=1, max_length=20)
    max_jobs_per_source: int = Field(default=10, ge=1, le=50)
    import_results: bool = True

    @field_validator("source_urls")
    @classmethod
    def validate_source_urls(cls, values: list[str]) -> list[str]:
        cleaned = []
        for value in values:
            url = value.strip()
            if not url:
                continue
            if not url.startswith(("http://", "https://")):
                raise ValueError("Source URLs must start with http:// or https://")
            cleaned.append(url)
        if not cleaned:
            raise ValueError("At least one source URL is required")
        return cleaned


class JobSearchRequest(BaseModel):
    target_roles: list[str] = Field(default_factory=list)
    target_locations: list[str] = Field(default_factory=list)
    target_skills: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=lambda: ["remotive", "remoteok", "adzuna"])
    posted_within_days: int = Field(default=14, ge=1, le=120)
    max_jobs_per_source: int = Field(default=10, ge=1, le=30)
    import_results: bool = True

    @field_validator("sources")
    @classmethod
    def normalize_sources(cls, values: list[str]) -> list[str]:
        allowed = {"remotive", "remoteok", "adzuna", "indeed", "glassdoor", "jobbank"}
        cleaned = []
        for value in values:
            source = value.strip().lower()
            if not source:
                continue
            if source not in allowed:
                raise ValueError(f"Unsupported job source: {source}")
            if source not in cleaned:
                cleaned.append(source)
        if not cleaned:
            raise ValueError("At least one job source is required")
        return cleaned


class Lead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr | None = None
    first_name: str
    last_name: str | None = None
    company: str | None = None
    title: str | None = None
    source: str
    notes: str | None = None
    linkedin_url: str | None = None
    lead_grade: str | None = None
    outreach_status: str | None = None
    suggested_first_message: str | None = None
    opportunity_url: str | None = None
    opportunity_location: str | None = None
    opportunity_description: str | None = None
    company_summary: str | None = None
    tech_stack: str | None = None
    role_fit: str | None = None
    source_links: str | None = None
    fit_score: int | None = None
    contact_name: str | None = None
    contact_role: str | None = None
    contact_type: str | None = None
    contact_source_url: str | None = None
    contact_confidence_score: int | None = None
    contact_verification_status: str | None = None
    status: LeadStatus
    created_at: datetime
    updated_at: datetime


class Opportunity(BaseModel):
    lead_id: UUID
    source: str
    source_url: str | None = None
    company_name: str | None = None
    job_title: str | None = None
    location: str | None = None
    description: str | None = None
    required_skills: list[str] = Field(default_factory=list)
    fit_score: int | None = None
    status: str | None = None


class ContactResearch(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lead_id: UUID
    contact_name: str | None = None
    contact_email: EmailStr | None = None
    contact_role: str | None = None
    contact_type: str
    source_url: str | None = None
    confidence_score: int
    verification_status: str
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class ApplicationCreate(BaseModel):
    lead_id: UUID | None = None
    company_name: str = Field(min_length=1, max_length=200)
    job_title: str = Field(min_length=1, max_length=200)
    source: str = Field(default="Company Site", max_length=100)
    job_url: str | None = Field(default=None, max_length=500)
    location: str | None = Field(default=None, max_length=200)
    status: ApplicationStatus = ApplicationStatus.SAVED
    applied_date: date | None = None
    resume_version: str | None = Field(default=None, max_length=200)
    cover_letter_version: str | None = Field(default=None, max_length=200)
    contact_found: bool = False
    gmail_thread_id: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("job_url", "location", "resume_version", "cover_letter_version", "gmail_thread_id", "notes", mode="before")
    @classmethod
    def blank_to_none(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value


class ApplicationUpdate(BaseModel):
    company_name: str | None = Field(default=None, min_length=1, max_length=200)
    job_title: str | None = Field(default=None, min_length=1, max_length=200)
    source: str | None = Field(default=None, max_length=100)
    job_url: str | None = Field(default=None, max_length=500)
    location: str | None = Field(default=None, max_length=200)
    status: ApplicationStatus | None = None
    applied_date: date | None = None
    resume_version: str | None = Field(default=None, max_length=200)
    cover_letter_version: str | None = Field(default=None, max_length=200)
    contact_found: bool | None = None
    gmail_thread_id: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("job_url", "location", "resume_version", "cover_letter_version", "gmail_thread_id", "notes", mode="before")
    @classmethod
    def blank_to_none(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value


class Application(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lead_id: UUID | None = None
    company_name: str
    job_title: str
    source: str
    job_url: str | None = None
    location: str | None = None
    status: ApplicationStatus
    applied_date: date | None = None
    resume_version: str | None = None
    cover_letter_version: str | None = None
    contact_found: bool
    gmail_thread_id: str | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class ProfileSettingsUpdate(BaseModel):
    owner_name: str | None = Field(default=None, max_length=200)
    primary_email: EmailStr | None = None
    outreach_email: EmailStr | None = None
    target_roles: list[str] | None = Field(default=None, max_length=50)
    target_locations: list[str] | None = Field(default=None, max_length=100)
    target_skills: list[str] | None = Field(default=None, max_length=100)
    resume_summary: str | None = Field(default=None, max_length=4000)
    linkedin_profile_url: str | None = Field(default=None, max_length=500)
    github_url: str | None = Field(default=None, max_length=500)
    portfolio_url: str | None = Field(default=None, max_length=500)
    default_resume_version: str | None = Field(default=None, max_length=200)

    @field_validator(
        "owner_name",
        "resume_summary",
        "linkedin_profile_url",
        "github_url",
        "portfolio_url",
        "default_resume_version",
        mode="before",
    )
    @classmethod
    def blank_to_none(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value


class ProfileSettings(BaseModel):
    id: UUID
    owner_name: str
    primary_email: EmailStr | None = None
    outreach_email: EmailStr | None = None
    target_roles: list[str] = Field(default_factory=list)
    target_locations: list[str] = Field(default_factory=list)
    target_skills: list[str] = Field(default_factory=list)
    resume_summary: str | None = None
    linkedin_profile_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None
    default_resume_version: str | None = None
    created_at: datetime
    updated_at: datetime


class ContactFinderResult(BaseModel):
    lead: Lead
    contact_found: bool
    contact_name: str | None = None
    contact_email: EmailStr | None = None
    contact_role: str | None = None
    contact_type: str | None = None
    source_url: str | None = None
    confidence_score: int = Field(ge=0, le=100)
    verification_status: str
    evidence: list[str] = Field(default_factory=list)


class JobDiscoveryImportResult(BaseModel):
    imported: int
    skipped: int
    leads: list[Lead]


class JobSourceDiscoveryResult(BaseModel):
    scanned_sources: int
    discovered: int
    imported: int
    skipped: int
    errors: list[str]
    jobs: list[JobDiscoveryItem]
    leads: list[Lead]


class CareerSourceCreate(BaseModel):
    company_name: str = Field(min_length=1, max_length=200)
    careers_url: str = Field(min_length=1, max_length=500)
    source_type: str = Field(default="company_careers", max_length=100)
    notes: str | None = Field(default=None, max_length=1000)
    active: bool = True

    @field_validator("careers_url")
    @classmethod
    def validate_careers_url(cls, value: str) -> str:
        url = value.strip()
        if not url.startswith(("http://", "https://")):
            raise ValueError("Career source URL must start with http:// or https://")
        return url

    @field_validator("notes", mode="before")
    @classmethod
    def blank_to_none(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value


class CareerSourceUpdate(BaseModel):
    company_name: str | None = Field(default=None, min_length=1, max_length=200)
    careers_url: str | None = Field(default=None, min_length=1, max_length=500)
    source_type: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=1000)
    active: bool | None = None

    @field_validator("careers_url")
    @classmethod
    def validate_careers_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        url = value.strip()
        if not url.startswith(("http://", "https://")):
            raise ValueError("Career source URL must start with http:// or https://")
        return url

    @field_validator("notes", mode="before")
    @classmethod
    def blank_to_none(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value


class CareerSource(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_name: str
    careers_url: str
    source_type: str
    notes: str | None = None
    active: bool
    last_scanned_at: datetime | None = None
    last_result_count: int | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


class CareerSourceScanRequest(BaseModel):
    career_source_ids: list[UUID] = Field(default_factory=list, max_length=20)
    target_roles: list[str] = Field(default_factory=list)
    target_locations: list[str] = Field(default_factory=list)
    target_skills: list[str] = Field(default_factory=list)
    import_results: bool = True


class JobSearchResult(BaseModel):
    searched_sources: int
    discovered: int
    imported: int
    skipped: int
    errors: list[str]
    jobs: list[JobDiscoveryItem]
    leads: list[Lead]


class JobUrlImportRequest(BaseModel):
    source_url: str = Field(min_length=1, max_length=5000)
    source_hint: str | None = Field(default=None, max_length=100)
    company_name: str | None = Field(default=None, max_length=200)
    job_title: str | None = Field(default=None, max_length=200)
    location: str | None = Field(default=None, max_length=200)
    pasted_description: str | None = Field(default=None, max_length=8000)
    recruiter_profile_url: str | None = Field(default=None, max_length=500)
    recruiter_name: str | None = Field(default=None, max_length=200)
    contact_email: EmailStr | None = None
    notes: str | None = Field(default=None, max_length=2000)
    target_roles: list[str] = Field(default_factory=list)
    target_locations: list[str] = Field(default_factory=list)
    target_skills: list[str] = Field(default_factory=list)
    import_result: bool = True

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: str) -> str:
        url = value.strip()
        if not url.startswith(("http://", "https://")):
            raise ValueError("Job URL must start with http:// or https://")
        return url

    @field_validator(
        "source_hint",
        "company_name",
        "job_title",
        "location",
        "pasted_description",
        "recruiter_profile_url",
        "recruiter_name",
        "notes",
        mode="before",
    )
    @classmethod
    def blank_to_none(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value


class JobUrlImportResult(BaseModel):
    imported: int
    skipped: int
    source: str
    extraction_status: str
    warnings: list[str]
    job: JobDiscoveryItem
    leads: list[Lead]


class SourceOpportunityCreate(BaseModel):
    source_url: str | None = Field(default=None, max_length=500)
    company_name: str = Field(min_length=1, max_length=200)
    job_title: str = Field(min_length=1, max_length=200)
    location: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    required_skills: list[str] = Field(default_factory=list, max_length=50)
    recruiter_profile_url: str | None = Field(default=None, max_length=500)
    recruiter_name: str | None = Field(default=None, max_length=200)
    contact_email: EmailStr | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("source_url", "recruiter_profile_url", "description", "notes", mode="before")
    @classmethod
    def blank_to_none(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value


class SourceTrackerImportRequest(BaseModel):
    target_roles: list[str] = Field(default_factory=list)
    target_locations: list[str] = Field(default_factory=list)
    target_skills: list[str] = Field(default_factory=list)
    opportunities: list[SourceOpportunityCreate] = Field(min_length=1, max_length=200)


class SourceTrackerCsvImportRequest(BaseModel):
    target_roles: list[str] = Field(default_factory=list)
    target_locations: list[str] = Field(default_factory=list)
    target_skills: list[str] = Field(default_factory=list)
    csv_rows: str = Field(min_length=1, max_length=50000)


class SourceTrackerImportResult(BaseModel):
    imported: int
    skipped: int
    source: str
    jobs: list[JobDiscoveryItem]
    leads: list[Lead]


class LinkedInConnectionMessageResult(BaseModel):
    lead_id: UUID
    message: str
    character_count: int
    max_character_count: int = 300
    safety_note: str


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    module: str = Field(default="Job Search", max_length=100)
    objective: str = Field(min_length=1, max_length=1000)


class Campaign(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    module: str
    objective: str
    status: CampaignStatus
    created_at: datetime
    updated_at: datetime


class DraftCreate(BaseModel):
    lead_id: UUID
    campaign_id: UUID | None = None
    subject: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=10000)
    generated_by: str = Field(default="manual", max_length=100)
    context_summary: str | None = Field(default=None, max_length=2000)


class DraftGenerateRequest(BaseModel):
    lead_id: UUID
    campaign_id: UUID | None = None
    call_to_action: str = Field(
        default="If your team considers junior candidates for similar roles, I’d be grateful for any advice or direction.",
        max_length=500,
    )
    extra_context: str | None = Field(default=None, max_length=2000)


class DraftQueueGenerateRequest(BaseModel):
    outreach_status: str = Field(default=PipelineStage.CONTACT_FOUND, max_length=100)
    lead_grades: list[str] = Field(default_factory=lambda: ["High Priority", "Medium Priority"])
    limit: int = Field(default=5, ge=1, le=25)
    call_to_action: str = Field(
        default="If your team considers junior candidates for similar roles, I’d be grateful for any advice or direction.",
        max_length=500,
    )
    extra_context: str | None = Field(default=None, max_length=2000)


class FollowUpQueueGenerateRequest(BaseModel):
    days_since_sent: int = Field(default=3, ge=0, le=90)
    limit: int = Field(default=5, ge=1, le=25)
    call_to_action: str = Field(
        default="I’d be grateful for any guidance on whether this type of role could be a good fit for someone with my background.",
        max_length=500,
    )
    extra_context: str | None = Field(default=None, max_length=2000)


class DraftUpdate(BaseModel):
    subject: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=10000)
    editor: str = Field(default="Prakriti", min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=2000)


class EmailDraft(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lead_id: UUID
    campaign_id: UUID | None = None
    subject: str
    body: str
    generated_by: str
    context_summary: str | None = None
    status: DraftStatus
    reviewer: str | None = None
    review_note: str | None = None
    qa_status: str | None = None
    qa_notes: str | None = None
    qa_checked_at: datetime | None = None
    sent_at: datetime | None = None
    sent_provider: str | None = None
    sent_message_id: str | None = None
    sent_thread_id: str | None = None
    send_error: str | None = None
    created_at: datetime
    updated_at: datetime


class DraftArchive(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    original_draft_id: UUID
    lead_id: UUID
    company: str | None = None
    job_title: str | None = None
    contact_email: str | None = None
    subject: str
    body: str
    generated_by: str
    status: str
    reviewer: str | None = None
    review_note: str | None = None
    archived_reason: str
    original_created_at: datetime
    archived_at: datetime


class PipelineStepResult(BaseModel):
    lead: Lead
    action: str
    message: str
    draft: EmailDraft | None = None
    requires_human_review: bool = True


class PipelineBatchRunRequest(BaseModel):
    stages: list[str] = Field(
        default_factory=lambda: [
            PipelineStage.DISCOVERED,
            PipelineStage.ANALYZED,
            PipelineStage.COMPANY_RESEARCHED,
        ],
        max_length=10,
    )
    lead_grades: list[str] = Field(default_factory=list, max_length=10)
    limit: int = Field(default=5, ge=1, le=25)
    allow_draft_generation: bool = False


class PipelineBatchRunResult(BaseModel):
    scanned: int
    advanced: int
    skipped: int
    results: list[PipelineStepResult]


class ReviewDecision(BaseModel):
    reviewer: str = Field(min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=2000)


class SendDecision(BaseModel):
    sender: str = Field(min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=2000)


class ReplyClassifyRequest(BaseModel):
    draft_id: UUID
    from_email: EmailStr
    body: str = Field(min_length=1, max_length=10000)


class EmailReply(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    draft_id: UUID
    lead_id: UUID
    from_email: EmailStr
    body: str
    intent: ReplyIntent
    classification_reason: str
    provider_message_id: str | None = None
    provider_thread_id: str | None = None
    subject: str | None = None
    received_at: datetime | None = None
    created_at: datetime


class DraftQueueGenerateResult(BaseModel):
    scanned: int
    created: int
    skipped: int
    drafts: list[EmailDraft]


class FollowUpRunDetail(BaseModel):
    status: str
    reason: str
    lead_id: UUID | None = None
    company: str | None = None
    job_title: str | None = None
    contact_email: str | None = None
    sent_draft_id: UUID | None = None
    sent_subject: str | None = None
    sent_at: datetime | None = None
    followup_draft_id: UUID | None = None
    followup_subject: str | None = None


class FollowUpQueueGenerateResult(BaseModel):
    scanned: int
    created: int
    skipped: int
    drafts: list[EmailDraft]
    details: list[FollowUpRunDetail] = Field(default_factory=list)


class ReplySyncDetail(BaseModel):
    status: str
    reason: str
    from_email: str | None = None
    subject: str | None = None
    provider_message_id: str | None = None
    provider_thread_id: str | None = None
    received_at: datetime | None = None
    lead_id: UUID | None = None
    company: str | None = None
    job_title: str | None = None
    draft_id: UUID | None = None
    draft_subject: str | None = None
    intent: ReplyIntent | None = None


class ReplySyncResult(BaseModel):
    fetched: int
    matched: int
    imported: int
    skipped: int
    replies: list[EmailReply]
    details: list[ReplySyncDetail] = Field(default_factory=list)


class AuditEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    action: AuditAction
    entity_type: str
    entity_id: UUID
    summary: str
    created_at: datetime
