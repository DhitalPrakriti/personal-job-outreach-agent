"""Safety and quality checks for generated email drafts."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DraftQAResult:
    status: str
    notes: str


class DraftQAAgent:
    """Apply deterministic checks before a draft reaches human approval."""

    SPAM_TERMS = ("guaranteed", "act now", "limited time", "100% free", "risk-free")

    async def review(self, subject: str, body: str, first_name: str | None) -> DraftQAResult:
        blocking: list[str] = []
        warnings: list[str] = []
        normalized = f"{subject} {body}".lower()

        if not subject.strip() or not body.strip():
            blocking.append("Subject and body are required.")
        if len(subject) > 80:
            warnings.append("Subject is longer than 80 characters.")
        word_count = len(body.split())
        if word_count < 35:
            warnings.append("Body may be too short to provide useful context.")
        if word_count > 220:
            warnings.append("Body is longer than the recommended outreach range.")
        if first_name and first_name.lower() not in body.lower():
            warnings.append("Contact first name is not present in the body.")
        if "?" not in body:
            warnings.append("Draft has no clear question or call to action.")
        matched_spam = [term for term in self.SPAM_TERMS if term in normalized]
        if matched_spam:
            blocking.append(f"Spam-like language detected: {', '.join(matched_spam)}.")

        if blocking:
            return DraftQAResult("blocked", " ".join(blocking + warnings))
        if warnings:
            return DraftQAResult("needs_review", " ".join(warnings))
        return DraftQAResult("passed", "Deterministic quality and safety checks passed.")
