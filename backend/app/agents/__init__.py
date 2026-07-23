"""Agent implementations used by the email automation workflow."""

from app.agents.company_research import CompanyResearchAgent, CompanyResearchResult
from app.agents.contact_finder import ContactFinderAgent
from app.agents.draft_qa import DraftQAAgent, DraftQAResult
from app.agents.email_inbox import EmailInboxAgent, EmailInboxError, InboxMessage
from app.agents.email_sender import EmailSendError, EmailSendResult, EmailSenderAgent
from app.agents.reply_classifier import ReplyClassification, ReplyClassifierAgent

__all__ = [
    "CompanyResearchAgent",
    "CompanyResearchResult",
    "ContactFinderAgent",
    "DraftQAAgent",
    "DraftQAResult",
    "EmailInboxAgent",
    "EmailInboxError",
    "InboxMessage",
    "EmailSendError",
    "EmailSendResult",
    "EmailSenderAgent",
    "ReplyClassification",
    "ReplyClassifierAgent",
]
