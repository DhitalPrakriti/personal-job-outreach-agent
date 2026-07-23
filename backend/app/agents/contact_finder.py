"""Agent wrapper for public contact discovery."""

from app.services.contact_finder import ContactCandidate, ContactFinderService


class ContactFinderAgent(ContactFinderService):
    """Find public recruiting/contact details for a discovered opportunity."""


__all__ = ["ContactCandidate", "ContactFinderAgent"]
