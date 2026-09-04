"""SQLAlchemy models for persistent outreach data."""

from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.schemas.pipeline import (
    ApplicationStatus,
    AuditAction,
    CampaignStatus,
    DraftStatus,
    LeadStatus,
    ReplyIntent,
)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class AppUserModel(TimestampMixin, Base):
    __tablename__ = "app_users"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(300), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GmailAccountModel(TimestampMixin, Base):
    __tablename__ = "gmail_accounts"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(200))
    purpose: Mapped[str] = mapped_column(String(50), nullable=False, default="job_search")
    encrypted_refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    scopes: Mapped[str | None] = mapped_column(Text)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    send_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    reply_sync_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="connected")


class LeadModel(TimestampMixin, Base):
    __tablename__ = "leads"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str | None] = mapped_column(String(320), index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str | None] = mapped_column(String(100))
    company: Mapped[str | None] = mapped_column(String(200))
    title: Mapped[str | None] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(String(100), nullable=False, default="manual")
    notes: Mapped[str | None] = mapped_column(Text)
    linkedin_url: Mapped[str | None] = mapped_column(String(500))
    lead_grade: Mapped[str | None] = mapped_column(String(100))
    outreach_status: Mapped[str | None] = mapped_column(String(100))
    suggested_first_message: Mapped[str | None] = mapped_column(Text)
    opportunity_url: Mapped[str | None] = mapped_column(String(500))
    opportunity_location: Mapped[str | None] = mapped_column(String(200))
    opportunity_description: Mapped[str | None] = mapped_column(Text)
    company_summary: Mapped[str | None] = mapped_column(Text)
    tech_stack: Mapped[str | None] = mapped_column(Text)
    role_fit: Mapped[str | None] = mapped_column(Text)
    source_links: Mapped[str | None] = mapped_column(Text)
    fit_score: Mapped[int | None] = mapped_column(Integer)
    contact_name: Mapped[str | None] = mapped_column(String(200))
    contact_role: Mapped[str | None] = mapped_column(String(200))
    contact_type: Mapped[str | None] = mapped_column(String(100))
    contact_source_url: Mapped[str | None] = mapped_column(String(500))
    contact_confidence_score: Mapped[int | None] = mapped_column(Integer)
    contact_verification_status: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[LeadStatus] = mapped_column(
        Enum(LeadStatus, name="lead_status"),
        nullable=False,
        default=LeadStatus.NEW,
    )

    drafts: Mapped[list["EmailDraftModel"]] = relationship(back_populates="lead")
    replies: Mapped[list["EmailReplyModel"]] = relationship(back_populates="lead")
    contact_research: Mapped[list["ContactResearchModel"]] = relationship(back_populates="lead")
    applications: Mapped[list["ApplicationModel"]] = relationship(back_populates="lead")


class ContactResearchModel(TimestampMixin, Base):
    __tablename__ = "contact_research"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    lead_id: Mapped[UUID] = mapped_column(ForeignKey("leads.id"), nullable=False, index=True)
    contact_name: Mapped[str | None] = mapped_column(String(200))
    contact_email: Mapped[str | None] = mapped_column(String(320))
    contact_role: Mapped[str | None] = mapped_column(String(200))
    contact_type: Mapped[str] = mapped_column(String(100), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(500))
    confidence_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    verification_status: Mapped[str] = mapped_column(String(100), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    lead: Mapped[LeadModel] = relationship(back_populates="contact_research")


class ApplicationModel(TimestampMixin, Base):
    __tablename__ = "applications"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    lead_id: Mapped[UUID | None] = mapped_column(ForeignKey("leads.id"), index=True)
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    job_title: Mapped[str] = mapped_column(String(200), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False, default="Company Site")
    job_url: Mapped[str | None] = mapped_column(String(500))
    location: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(ApplicationStatus, name="application_status"),
        nullable=False,
        default=ApplicationStatus.SAVED,
    )
    applied_date: Mapped[date | None] = mapped_column(Date)
    resume_version: Mapped[str | None] = mapped_column(String(200))
    cover_letter_version: Mapped[str | None] = mapped_column(String(200))
    contact_found: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    gmail_thread_id: Mapped[str | None] = mapped_column(String(500))
    notes: Mapped[str | None] = mapped_column(Text)

    lead: Mapped[LeadModel | None] = relationship(back_populates="applications")


class ProfileSettingsModel(TimestampMixin, Base):
    __tablename__ = "profile_settings"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    profile_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, default="default")
    owner_name: Mapped[str] = mapped_column(String(200), nullable=False, default="Prakriti Dhital")
    primary_email: Mapped[str | None] = mapped_column(String(320))
    outreach_email: Mapped[str | None] = mapped_column(String(320))
    target_roles: Mapped[str | None] = mapped_column(Text)
    target_locations: Mapped[str | None] = mapped_column(Text)
    target_skills: Mapped[str | None] = mapped_column(Text)
    resume_summary: Mapped[str | None] = mapped_column(Text)
    linkedin_profile_url: Mapped[str | None] = mapped_column(String(500))
    github_url: Mapped[str | None] = mapped_column(String(500))
    portfolio_url: Mapped[str | None] = mapped_column(String(500))
    default_resume_version: Mapped[str | None] = mapped_column(String(200))


class CareerSourceModel(TimestampMixin, Base):
    __tablename__ = "career_sources"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    careers_url: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    source_type: Mapped[str] = mapped_column(String(100), nullable=False, default="company_careers")
    notes: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_result_count: Mapped[int | None] = mapped_column(Integer)
    last_error: Mapped[str | None] = mapped_column(Text)


class CampaignModel(TimestampMixin, Base):
    __tablename__ = "campaigns"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    module: Mapped[str] = mapped_column(String(100), nullable=False, default="Job Search")
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[CampaignStatus] = mapped_column(
        Enum(CampaignStatus, name="campaign_status"),
        nullable=False,
        default=CampaignStatus.DRAFT,
    )

    drafts: Mapped[list["EmailDraftModel"]] = relationship(back_populates="campaign")


class EmailDraftModel(TimestampMixin, Base):
    __tablename__ = "email_drafts"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    lead_id: Mapped[UUID] = mapped_column(ForeignKey("leads.id"), nullable=False, index=True)
    campaign_id: Mapped[UUID | None] = mapped_column(ForeignKey("campaigns.id"), index=True)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    generated_by: Mapped[str] = mapped_column(String(100), nullable=False, default="manual")
    context_summary: Mapped[str | None] = mapped_column(Text)
    status: Mapped[DraftStatus] = mapped_column(
        Enum(DraftStatus, name="draft_status"),
        nullable=False,
        default=DraftStatus.PENDING_APPROVAL,
    )
    reviewer: Mapped[str | None] = mapped_column(String(200))
    review_note: Mapped[str | None] = mapped_column(Text)
    qa_status: Mapped[str | None] = mapped_column(String(50))
    qa_notes: Mapped[str | None] = mapped_column(Text)
    qa_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_provider: Mapped[str | None] = mapped_column(String(50))
    sent_message_id: Mapped[str | None] = mapped_column(String(500))
    sent_thread_id: Mapped[str | None] = mapped_column(String(500))
    send_error: Mapped[str | None] = mapped_column(Text)

    lead: Mapped[LeadModel] = relationship(back_populates="drafts")
    campaign: Mapped[CampaignModel | None] = relationship(back_populates="drafts")
    replies: Mapped[list["EmailReplyModel"]] = relationship(back_populates="draft")


class DraftArchiveModel(Base):
    __tablename__ = "draft_archives"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    original_draft_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    lead_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    company: Mapped[str | None] = mapped_column(String(200))
    job_title: Mapped[str | None] = mapped_column(String(200))
    contact_email: Mapped[str | None] = mapped_column(String(320))
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    generated_by: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    reviewer: Mapped[str | None] = mapped_column(String(200))
    review_note: Mapped[str | None] = mapped_column(Text)
    archived_reason: Mapped[str] = mapped_column(String(200), nullable=False)
    original_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    archived_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class EmailReplyModel(Base):
    __tablename__ = "email_replies"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    draft_id: Mapped[UUID] = mapped_column(
        ForeignKey("email_drafts.id"),
        nullable=False,
        index=True,
    )
    lead_id: Mapped[UUID] = mapped_column(ForeignKey("leads.id"), nullable=False, index=True)
    from_email: Mapped[str] = mapped_column(String(320), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[ReplyIntent] = mapped_column(
        Enum(ReplyIntent, name="reply_intent"),
        nullable=False,
    )
    classification_reason: Mapped[str] = mapped_column(Text, nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(String(500), index=True)
    provider_thread_id: Mapped[str | None] = mapped_column(String(500), index=True)
    subject: Mapped[str | None] = mapped_column(String(500))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    draft: Mapped[EmailDraftModel] = relationship(back_populates="replies")
    lead: Mapped[LeadModel] = relationship(back_populates="replies")


class AuditEventModel(Base):
    __tablename__ = "audit_events"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction, name="audit_action"),
        nullable=False,
    )
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
