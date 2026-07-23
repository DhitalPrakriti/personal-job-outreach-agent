"""AI drafting agent for personal outreach emails."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx
import litellm

from app.agents.llm import resolve_model_alias
from app.core.config import get_settings
from app.db.models import CampaignModel, LeadModel
from app.schemas.pipeline import DraftGenerateRequest


class AIDraftError(RuntimeError):
    """Raised when the AI drafting agent cannot produce a usable draft."""


@dataclass(frozen=True)
class DraftAgentResult:
    subject: str
    body: str
    generated_by: str
    context_summary: str


class AIDraftService:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def generate_draft(
        self,
        lead: LeadModel,
        campaign: CampaignModel | None,
        payload: DraftGenerateRequest,
    ) -> DraftAgentResult:
        if not self.settings.ai_drafting_enabled:
            return self.generate_fallback_draft(lead, campaign, payload)

        try:
            return await self._generate_with_litellm_proxy(lead, campaign, payload)
        except AIDraftError as proxy_error:
            try:
                return await self._generate_with_litellm_sdk(lead, campaign, payload)
            except AIDraftError as sdk_error:
                fallback_reason = (
                    "AI drafting unavailable; used local fallback. "
                    f"Proxy error: {proxy_error} SDK error: {sdk_error}"
                )

            return self.generate_fallback_draft(
                lead,
                campaign,
                payload,
                fallback_reason=fallback_reason,
            )

    def generate_fallback_draft(
        self,
        lead: LeadModel,
        campaign: CampaignModel | None,
        payload: DraftGenerateRequest,
        fallback_reason: str | None = None,
    ) -> DraftAgentResult:
        company_or_role = lead.company or "your team"
        subject_context = lead.title or company_or_role
        subject = f"Quick idea for {subject_context}"
        objective = campaign.objective if campaign is not None else "start a relevant career conversation"
        context_lines = [
            f"Contact source: {lead.source}.",
            f"Objective: {objective}.",
        ]
        if payload.extra_context:
            context_lines.append(f"Extra context: {payload.extra_context}")
        if lead.notes:
            context_lines.append(f"Research context: {lead.notes}")
        if fallback_reason:
            context_lines.append(fallback_reason)

        is_follow_up = "follow-up to a prior sent outreach" in (payload.extra_context or "").lower()
        suggested_message = (lead.suggested_first_message or "").strip()
        if is_follow_up:
            body = (
                f"Hi {lead.first_name},\n\n"
                "Just following up on my earlier note. I know timing may not be right, "
                f"but I thought the conversation around {objective.lower()} could still be relevant "
                f"given your work with {company_or_role}.\n\n"
                "Happy to keep it practical and brief if useful.\n\n"
                f"{payload.call_to_action}\n\n"
                "Best,\nPrakriti"
            )
            context_lines.append("Generated as a follow-up draft.")
        elif suggested_message:
            context_lines.append("Used contact source suggested first message.")
            role_context = f" the {lead.title} role" if lead.title else " your team"
            body = (
                f"Hi {lead.first_name},\n\n"
                f"I came across{role_context} at {company_or_role} and wanted to reach out because "
                "it looks aligned with the kind of AI, backend, and automation work I am pursuing.\n\n"
                f"What stood out from my research: {suggested_message}\n\n"
                "I would value a brief conversation if there may be a relevant opening, team, "
                "or direction to learn more about.\n\n"
                f"{payload.call_to_action}\n\n"
                "Best,\nPrakriti"
            )
        else:
            body = (
                f"Hi {lead.first_name},\n\n"
                f"I came across your work with {company_or_role} and wanted to reach out "
                f"because I am exploring opportunities and conversations related to {objective.lower()}.\n\n"
                "My background is in building practical AI and automation systems, and I would value "
                "a brief conversation if there may be a relevant team, role, or direction to learn about.\n\n"
                f"{payload.call_to_action}\n\n"
                "Best,\n"
                "Prakriti"
            )

        return DraftAgentResult(
            subject=subject,
            body=body,
            generated_by="mock_generator",
            context_summary=" ".join(context_lines),
        )

    async def _generate_with_litellm_proxy(
        self,
        lead: LeadModel,
        campaign: CampaignModel | None,
        payload: DraftGenerateRequest,
    ) -> DraftAgentResult:
        request_body = {
            "model": self.settings.primary_model,
            "messages": [
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": self._user_prompt(lead, campaign, payload)},
            ],
            "temperature": 0.35,
            "max_tokens": 700,
            "response_format": {"type": "json_object"},
        }
        headers = {"Content-Type": "application/json"}
        if self.settings.litellm_master_key:
            headers["Authorization"] = f"Bearer {self.settings.litellm_master_key}"

        try:
            async with httpx.AsyncClient(
                base_url=self.settings.litellm_base_url.rstrip("/"),
                timeout=45,
            ) as client:
                response = await client.post(
                    "/v1/chat/completions",
                    headers=headers,
                    json=request_body,
                )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AIDraftError("LiteLLM request failed.") from exc

        content = self._extract_message_content(response.json())
        parsed = self._parse_agent_json(content)
        subject = str(parsed.get("subject") or "").strip()
        body = str(parsed.get("body") or "").strip()
        notes = str(parsed.get("notes") or "").strip()
        if not subject or not body:
            raise AIDraftError("AI response did not include subject and body.")

        context_parts = [
            "Generated by AI drafting agent via LiteLLM.",
            f"Model: {self.settings.primary_model}.",
        ]
        if notes:
            context_parts.append(f"Agent notes: {notes}")

        return DraftAgentResult(
            subject=subject[:300],
            body=body[:10000],
            generated_by="ai_drafting_agent",
            context_summary=" ".join(context_parts),
        )

    async def _generate_with_litellm_sdk(
        self,
        lead: LeadModel,
        campaign: CampaignModel | None,
        payload: DraftGenerateRequest,
    ) -> DraftAgentResult:
        if not self.settings.anthropic_api_key:
            raise AIDraftError("ANTHROPIC_API_KEY is not configured.")

        resolved_model = resolve_model_alias(self.settings.primary_model)

        try:
            response = await litellm.acompletion(
                model=resolved_model,
                messages=[
                    {"role": "system", "content": self._system_prompt()},
                    {"role": "user", "content": self._user_prompt(lead, campaign, payload)},
                ],
                temperature=0.35,
                max_tokens=700,
                api_key=self.settings.anthropic_api_key,
                drop_params=True,
            )
        except Exception as exc:
            raise AIDraftError(
                f"LiteLLM SDK request failed: {type(exc).__name__}: {exc}"
            ) from exc

        content = self._extract_message_content(response)
        parsed = self._parse_agent_json(content)
        subject = str(parsed.get("subject") or "").strip()
        body = str(parsed.get("body") or "").strip()
        notes = str(parsed.get("notes") or "").strip()
        if not subject or not body:
            raise AIDraftError("AI response did not include subject and body.")

        context_parts = [
            "Generated by AI drafting agent via LiteLLM SDK.",
            f"Model: {resolved_model}.",
        ]
        if notes:
            context_parts.append(f"Agent notes: {notes}")

        return DraftAgentResult(
            subject=subject[:300],
            body=body[:10000],
            generated_by="ai_drafting_agent",
            context_summary=" ".join(context_parts),
        )

    @staticmethod
    def _system_prompt() -> str:
        return (
            "You are a personal AI outreach drafting agent for a technical job seeker. "
            "Write concise, human-reviewable networking and opportunity outreach emails. "
            "Use only the provided facts. Do not invent metrics, meetings, relationships, "
            "case studies, referrals, credentials, or claims. Avoid spammy language, hype, pressure tactics, "
            "and fake familiarity. Keep the email plain text and professional. "
            "Return valid JSON only with keys: subject, body, notes."
        )

    @staticmethod
    def _user_prompt(
        lead: LeadModel,
        campaign: CampaignModel | None,
        payload: DraftGenerateRequest,
    ) -> str:
        objective = campaign.objective if campaign is not None else "start a relevant career conversation"
        lead_name = " ".join(part for part in (lead.first_name, lead.last_name) if part)
        lead_context: dict[str, Any] = {
            "contact_name": lead_name,
            "first_name": lead.first_name,
            "company": lead.company,
            "title": lead.title,
            "linkedin_url": lead.linkedin_url,
            "lead_grade": lead.lead_grade,
            "outreach_status": lead.outreach_status,
            "opportunity_url": lead.opportunity_url,
            "opportunity_location": lead.opportunity_location,
            "company_summary": lead.company_summary,
            "tech_stack": lead.tech_stack,
            "role_fit": lead.role_fit,
            "fit_score": lead.fit_score,
            "contact_role": lead.contact_role,
            "contact_type": lead.contact_type,
            "contact_source_url": lead.contact_source_url,
            "contact_confidence_score": lead.contact_confidence_score,
            "contact_verification_status": lead.contact_verification_status,
            "research_notes": lead.notes,
            "suggested_first_message_from_contact_source": lead.suggested_first_message,
            "campaign_objective": objective,
            "call_to_action": payload.call_to_action,
            "extra_context": payload.extra_context,
        }
        return (
            "Create one outreach email draft for this contact.\n"
            "Use the contact-source suggested first message as a starting point if it is useful, "
            "but improve clarity and keep it natural.\n"
            "Email constraints: 70-130 words, one clear CTA, no markdown, no bullets.\n"
            f"Contact context JSON:\n{json.dumps(lead_context, indent=2)}"
        )

    @staticmethod
    def _extract_message_content(payload: Any) -> str:
        if hasattr(payload, "model_dump"):
            payload = payload.model_dump()
        elif not isinstance(payload, dict):
            try:
                payload = dict(payload)
            except (TypeError, ValueError) as exc:
                raise AIDraftError("LiteLLM response shape was unexpected.") from exc
        try:
            return str(payload["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise AIDraftError("LiteLLM response shape was unexpected.") from exc

    @staticmethod
    def _parse_agent_json(content: str) -> dict[str, Any]:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise AIDraftError("AI response was not valid JSON.") from exc
        if not isinstance(parsed, dict):
            raise AIDraftError("AI response JSON must be an object.")
        return parsed
