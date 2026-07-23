"""Reply-intent classification with a deterministic safe fallback."""

from dataclasses import dataclass

from app.schemas.pipeline import ReplyIntent


@dataclass(frozen=True)
class ReplyClassification:
    intent: ReplyIntent
    reason: str


class ReplyClassifierAgent:
    async def classify(self, body: str) -> ReplyClassification:
        normalized = body.lower()
        if any(term in normalized for term in ("undeliverable", "delivery has failed", "address not found", "mailbox unavailable")):
            return ReplyClassification(ReplyIntent.BOUNCE, "Matched bounce or delivery failure language.")
        if any(term in normalized for term in ("unsubscribe", "remove me", "stop emailing")):
            return ReplyClassification(ReplyIntent.UNSUBSCRIBE, "Matched unsubscribe language.")
        if any(term in normalized for term in ("out of office", "ooo", "away from office")):
            return ReplyClassification(ReplyIntent.OUT_OF_OFFICE, "Matched out-of-office language.")
        if any(term in normalized for term in ("not interested", "no thanks", "not a fit")):
            return ReplyClassification(ReplyIntent.NOT_INTERESTED, "Matched negative intent language.")
        if any(term in normalized for term in ("interview", "phone screen", "screening call", "onsite", "next round")):
            return ReplyClassification(ReplyIntent.INTERVIEW, "Matched interview-stage language.")
        if any(term in normalized for term in ("send your resume", "share your resume", "resume", "cv", "portfolio")):
            return ReplyClassification(ReplyIntent.RESUME_REQUESTED, "Matched resume or portfolio request language.")
        if any(term in normalized for term in ("interested", "tell me more", "book", "schedule")):
            return ReplyClassification(ReplyIntent.INTERESTED, "Matched positive intent language.")
        if any(term in normalized for term in ("maybe", "circle back", "not sure", "forward this", "passed along")):
            return ReplyClassification(ReplyIntent.UNCLEAR, "Matched ambiguous follow-up language.")
        return ReplyClassification(ReplyIntent.NEUTRAL, "No strong intent keywords matched.")
