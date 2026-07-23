"""Database engine and session helpers."""

from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.db.models import Base

settings = get_settings()

engine = create_async_engine(settings.database_url, echo=False, poolclass=NullPool)
async_session = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with async_session() as session:
        yield session


async def init_db() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.execute(text("alter type audit_action add value if not exists 'LEAD_IMPORTED'"))
        await connection.execute(text("alter type audit_action add value if not exists 'OPPORTUNITY_IMPORTED'"))
        await connection.execute(text("alter type audit_action add value if not exists 'OPPORTUNITY_ANALYZED'"))
        await connection.execute(text("alter type audit_action add value if not exists 'COMPANY_RESEARCHED'"))
        await connection.execute(text("alter type audit_action add value if not exists 'CONTACT_SEARCHED'"))
        await connection.execute(text("alter type audit_action add value if not exists 'LINKEDIN_MESSAGE_CREATED'"))
        await connection.execute(text("alter type audit_action add value if not exists 'APPLICATION_CREATED'"))
        await connection.execute(text("alter type audit_action add value if not exists 'APPLICATION_UPDATED'"))
        await connection.execute(text("alter type audit_action add value if not exists 'APPLICATION_DELETED'"))
        await connection.execute(text("alter type audit_action add value if not exists 'PROFILE_UPDATED'"))
        await connection.execute(text("alter type audit_action add value if not exists 'CAREER_SOURCE_CREATED'"))
        await connection.execute(text("alter type audit_action add value if not exists 'CAREER_SOURCE_UPDATED'"))
        await connection.execute(text("alter type audit_action add value if not exists 'CAREER_SOURCE_DELETED'"))
        await connection.execute(text("alter type audit_action add value if not exists 'CAREER_SOURCE_SCANNED'"))
        await connection.execute(text("alter type audit_action add value if not exists 'DRAFT_UPDATED'"))
        await connection.execute(text("alter type audit_action add value if not exists 'REPLY_SYNCED'"))
        await connection.execute(text("alter type reply_intent add value if not exists 'INTERVIEW'"))
        await connection.execute(text("alter type reply_intent add value if not exists 'RESUME_REQUESTED'"))
        await connection.execute(text("alter type reply_intent add value if not exists 'BOUNCE'"))
        await connection.execute(text("alter type reply_intent add value if not exists 'UNCLEAR'"))
        await connection.execute(text("alter table leads alter column email drop not null"))
        await connection.execute(text("alter table leads add column if not exists notion_page_id varchar(100)"))
        await connection.execute(text("alter table leads add column if not exists linkedin_url varchar(500)"))
        await connection.execute(text("alter table leads add column if not exists lead_grade varchar(100)"))
        await connection.execute(text("alter table leads add column if not exists outreach_status varchar(100)"))
        await connection.execute(text("alter table leads add column if not exists suggested_first_message text"))
        await connection.execute(text("alter table leads add column if not exists opportunity_url varchar(500)"))
        await connection.execute(text("alter table leads add column if not exists opportunity_location varchar(200)"))
        await connection.execute(text("alter table leads add column if not exists opportunity_description text"))
        await connection.execute(text("alter table leads add column if not exists company_summary text"))
        await connection.execute(text("alter table leads add column if not exists tech_stack text"))
        await connection.execute(text("alter table leads add column if not exists role_fit text"))
        await connection.execute(text("alter table leads add column if not exists source_links text"))
        await connection.execute(text("alter table leads add column if not exists fit_score integer"))
        await connection.execute(text("alter table leads add column if not exists contact_name varchar(200)"))
        await connection.execute(text("alter table leads add column if not exists contact_role varchar(200)"))
        await connection.execute(text("alter table leads add column if not exists contact_type varchar(100)"))
        await connection.execute(text("alter table leads add column if not exists contact_source_url varchar(500)"))
        await connection.execute(text("alter table leads add column if not exists contact_confidence_score integer"))
        await connection.execute(text("alter table leads add column if not exists contact_verification_status varchar(100)"))
        await connection.execute(
            text("alter table leads add column if not exists last_synced_at timestamp with time zone")
        )
        await connection.execute(
            text(
                """
                update leads
                set outreach_status = case outreach_status
                    when 'Ready for Outreach' then 'Contact Found'
                    when 'Not Contacted' then 'Discovered'
                    when 'Message Sent' then 'Sent'
                    when 'Connected' then 'Replied'
                    when 'Follow Up' then 'Follow-up Due'
                    when 'Not a Fit' then 'Closed'
                    when 'Discovered' then 'DISCOVERED'
                    when 'Opportunity Discovered' then 'DISCOVERED'
                    when 'Company Researched' then 'COMPANY_RESEARCHED'
                    when 'Contact Search Needed' then 'COMPANY_RESEARCHED'
                    when 'Contact Found' then 'CONTACT_FOUND'
                    when 'Drafted' then 'PENDING_APPROVAL'
                    when 'Pending Approval' then 'PENDING_APPROVAL'
                    when 'Approved' then 'APPROVED'
                    when 'Sent' then 'SENT'
                    when 'Replied' then 'REPLIED'
                    when 'Follow-up Due' then 'FOLLOW_UP_DUE'
                    when 'Closed' then 'CLOSED'
                    else outreach_status
                end
                where outreach_status in (
                    'Ready for Outreach',
                    'Not Contacted',
                    'Message Sent',
                    'Connected',
                    'Follow Up',
                    'Not a Fit',
                    'Discovered',
                    'Opportunity Discovered',
                    'Company Researched',
                    'Contact Search Needed',
                    'Contact Found',
                    'Drafted',
                    'Pending Approval',
                    'Approved',
                    'Sent',
                    'Replied',
                    'Follow-up Due',
                    'Closed'
                )
                """
            )
        )
        await connection.execute(
            text(
                "create unique index if not exists ix_leads_notion_page_id "
                "on leads (notion_page_id) where notion_page_id is not null"
            )
        )
        await connection.execute(text("alter table email_drafts add column if not exists qa_status varchar(50)"))
        await connection.execute(text("alter table email_drafts add column if not exists qa_notes text"))
        await connection.execute(text("alter table email_drafts add column if not exists qa_checked_at timestamp with time zone"))
        await connection.execute(text("alter table email_drafts add column if not exists sent_at timestamp with time zone"))
        await connection.execute(text("alter table email_drafts add column if not exists sent_provider varchar(50)"))
        await connection.execute(text("alter table email_drafts add column if not exists sent_message_id varchar(500)"))
        await connection.execute(text("alter table email_drafts add column if not exists sent_thread_id varchar(500)"))
        await connection.execute(text("alter table email_drafts add column if not exists send_error text"))
        await connection.execute(text("alter table email_replies add column if not exists provider_message_id varchar(500)"))
        await connection.execute(text("alter table email_replies add column if not exists provider_thread_id varchar(500)"))
        await connection.execute(text("alter table email_replies add column if not exists subject varchar(500)"))
        await connection.execute(text("alter table email_replies add column if not exists received_at timestamp with time zone"))
        await connection.execute(
            text(
                "create unique index if not exists ix_email_replies_provider_message_id "
                "on email_replies (provider_message_id) where provider_message_id is not null"
            )
        )


async def check_database() -> bool:
    async with engine.connect() as connection:
        result = await connection.execute(text("select 1"))
        return result.scalar_one() == 1
