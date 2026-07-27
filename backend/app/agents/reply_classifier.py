"""Reply-intent classification with an LLM path and deterministic fallback."""

from __future__ import annotations

import json
from dataclasses import dataclass

import httpx

from app.core.config import get_settings
from app.schemas.pipeline import ReplyIntent


@dataclass(frozen=True)
class ReplyClassification:
    intent: ReplyIntent
    reason: str


class ReplyClassifierAgent:
    async def classify(self, body: str) -> ReplyClassification:
        settings = get_settings()
        if settings.ai_drafting_enabled and settings.litellm_base_url and settings.litellm_master_key:
            try:
                return await self._classify_with_llm(body)
            except Exception:
                pass
        return self._classify_with_rules(body)

    async def _classify_with_llm(self, body: str) -> ReplyClassification:
        settings = get_settings()
        allowed = [intent.value for intent in ReplyIntent]
        payload = {
            "model": settings.fast_model or settings.primary_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Classify a recruiter/company email reply for a job-search outreach workflow. "
                        f"Return valid JSON only with keys intent and reason. intent must be one of: {', '.join(allowed)}. "
                        "Use interview only when they propose an interview/screen/call as a hiring step. "
                        "Use resume_requested when they ask for resume, CV, portfolio, or application material. "
                        "Use interested for positive but non-interview responses. Use unclear when the next step is ambiguous."
                    ),
                },
                {"role": "user", "content": body[:10000]},
            ],
            "max_tokens": 500,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.litellm_master_key}",
        }
        async with httpx.AsyncClient(base_url=settings.litellm_base_url.rstrip("/"), timeout=45) as client:
            response = await client.post("/v1/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        parsed = self._parse_json(content)
        intent_value = str(parsed.get("intent") or "").strip().lower()
        reason = str(parsed.get("reason") or "Classified by LLM.").strip()
        intent = ReplyIntent(intent_value) if intent_value in allowed else ReplyIntent.UNCLEAR
        return ReplyClassification(intent, f"LLM classified reply: {reason}")

    @staticmethod
    def _parse_json(content: str) -> dict:
        text = content.strip()
        if text.startswith("```"):
            text = text.removeprefix("```json").removeprefix("```").strip()
            if text.endswith("```"):
                text = text[:-3].strip()
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and start < end:
            text = text[start:end + 1]
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("Reply classifier response must be a JSON object.")
        return parsed

    @staticmethod
    def _classify_with_rules(body: str) -> ReplyClassification:
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
