"""AI drafting agent for personal outreach emails."""

from __future__ import annotations

import json
import re
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


@dataclass(frozen=True)
class PublicDraftBrief:
    greeting_name: str
    company: str
    title: str
    subject: str
    role_phrase: str
    role_focus: str
    opportunity_detail: str
    seniority_note: str
    source_label: str
    cta: str


PLACEHOLDER_COMPANIES = {"company from pasted job", "unknown company"}
PLACEHOLDER_TITLES = {
    "linkedin job opportunity",
    "indeed job opportunity",
    "glassdoor job opportunity",
    "job opportunity",
}
DRAFT_MAX_TOKENS = 1400
EARLY_CAREER_CTA = (
    "If your team considers junior candidates for similar roles, I would be grateful "
    "for any advice, direction, or the right application path."
)


class AIDraftService:
    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def draft_model(self) -> str:
        return self.settings.fast_model or self.settings.primary_model

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
        brief = self._draft_brief(lead, payload)
        objective = campaign.objective if campaign is not None else "start a relevant career conversation"
        context_lines = [
            f"Contact source: {lead.source}.",
            f"Objective: {objective}.",
            f"Public draft brief: {brief.title or 'open role'} at {brief.company}. {brief.role_focus}",
        ]
        if payload.extra_context:
            context_lines.append(f"Extra context: {payload.extra_context}")
        if lead.notes:
            context_lines.append("Research context saved for audit; internal match details are not shown in the email.")
        if fallback_reason:
            context_lines.append(fallback_reason)

        is_follow_up = "follow-up to a prior sent outreach" in (payload.extra_context or "").lower()
        if is_follow_up:
            body = (
                f"Hi {brief.greeting_name},\n\n"
                f"I wanted to follow up on my earlier note about {brief.role_phrase}. "
                "I understand timing may not be right, but I wanted to keep the thread open because "
                f"{brief.opportunity_detail.lower()}\n\n"
                f"{brief.seniority_note}\n\n"
                f"{brief.cta}\n\n"
                "Best,\nPrakriti"
            )
            context_lines.append("Generated as a follow-up draft.")
        elif brief.title:
            body = (
                f"Hi {brief.greeting_name},\n\n"
                f"I came across the {brief.title} role at {brief.company} and wanted to reach out directly. "
                f"{brief.opportunity_detail}\n\n"
                f"{brief.seniority_note}\n\n"
                f"{brief.cta}\n\n"
                "Best,\nPrakriti"
            )
        else:
            body = (
                f"Hi {brief.greeting_name},\n\n"
                f"I came across {brief.company} while exploring junior and early-career technical opportunities. "
                f"{brief.opportunity_detail}\n\n"
                f"{brief.seniority_note}\n\n"
                f"{brief.cta}\n\n"
                "Best,\n"
                "Prakriti"
            )

        return DraftAgentResult(
            subject=brief.subject,
            body=self._remove_internal_language(body),
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
            "model": self.draft_model,
            "messages": [
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": self._user_prompt(lead, campaign, payload)},
            ],
            "max_tokens": DRAFT_MAX_TOKENS,
            "response_format": {"type": "json_object"},
        }
        if not self._is_gemini_model(self.draft_model):
            request_body["temperature"] = 0.35
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
            f"Model: {self.draft_model}.",
        ]
        if notes:
            context_parts.append(f"Agent notes: {notes}")

        return DraftAgentResult(
            subject=subject[:300],
            body=self._clean_public_body(body)[:10000],
            generated_by="ai_drafting_agent",
            context_summary=" ".join(context_parts),
        )

    async def _generate_with_litellm_sdk(
        self,
        lead: LeadModel,
        campaign: CampaignModel | None,
        payload: DraftGenerateRequest,
    ) -> DraftAgentResult:
        resolved_model = resolve_model_alias(self.draft_model)
        provider_key = self._provider_api_key(resolved_model)
        if not provider_key:
            raise AIDraftError(
                f"No provider API key is configured for model {resolved_model}."
            )

        try:
            completion_kwargs: dict[str, Any] = {
                "model": resolved_model,
                "messages": [
                    {"role": "system", "content": self._system_prompt()},
                    {"role": "user", "content": self._user_prompt(lead, campaign, payload)},
                ],
                "max_tokens": DRAFT_MAX_TOKENS,
                "api_key": provider_key,
                "drop_params": True,
                "response_format": {"type": "json_object"},
            }
            if not self._is_gemini_model(resolved_model):
                completion_kwargs["temperature"] = 0.35

            response = await litellm.acompletion(
                **completion_kwargs,
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
            body=self._clean_public_body(body)[:10000],
            generated_by="ai_drafting_agent",
            context_summary=" ".join(context_parts),
        )

    def _provider_api_key(self, resolved_model: str) -> str:
        if self.settings.llm_api_key:
            return self.settings.llm_api_key

        model = resolved_model.lower()
        if model.startswith("anthropic/") or model.startswith("claude"):
            return self.settings.anthropic_api_key
        if model.startswith("openai/") or model.startswith("gpt-"):
            return self.settings.openai_api_key
        if model.startswith("gemini/"):
            return self.settings.gemini_api_key
        if model.startswith("ollama/"):
            return ""
        return (
            self.settings.gemini_api_key
            or self.settings.openai_api_key
            or self.settings.anthropic_api_key
        )

    @staticmethod
    def _is_gemini_model(model_name: str) -> bool:
        return "gemini" in model_name.lower()

    @staticmethod
    def _system_prompt() -> str:
        return (
            "You are a personal AI outreach drafting agent for a technical job seeker. "
            "Write concise, human-reviewable networking and opportunity outreach emails. "
            "The sender is a recent graduate and early-career technical candidate. "
            "Write with a humble, clear, warm tone: interested, capable, and still learning. "
            "Ask for guidance, direction, consideration, or the right application/contact path instead of assuming senior fit. "
            "Use only the provided facts. Do not invent metrics, meetings, relationships, "
            "case studies, referrals, credentials, or claims. Avoid spammy language, hype, pressure tactics, "
            "and fake familiarity. Keep the email plain text and professional. "
            "Do not sound like a senior consultant, sales rep, or executive candidate. "
            "Do not write 'What stood out from my research' unless a specific public job detail was provided. "
            "If research context is weak, simply say the role connects with the sender's early-career interests. "
            "Avoid phrases such as 'I am writing to express my interest', 'I would welcome the opportunity to discuss', "
            "'how my technical skills align with your upcoming engineering milestones', 'data layer evolution', "
            "'very enthusiastic about the work your team is doing', and 'Open to a 15-minute conversation?'. "
            "Never include internal pipeline metadata in the email body: fit scores, confidence scores, "
            "lead grades, source-adapter notes, scraping/legal/compliance notes, JSON field names, "
            "verification statuses, or phrases like 'matched skills' and 'contact/profile link available'. "
            "Always sign the email exactly as: Best, newline Prakriti. Never sign as Candidate. "
            "Return valid JSON only with keys: subject, body, notes."
        )

    @staticmethod
    def _user_prompt(
        lead: LeadModel,
        campaign: CampaignModel | None,
        payload: DraftGenerateRequest,
    ) -> str:
        objective = campaign.objective if campaign is not None else "start a relevant career conversation"
        brief = AIDraftService._draft_brief(lead, payload)
        lead_context: dict[str, Any] = {
            "greeting_name": brief.greeting_name,
            "company": brief.company,
            "job_title": brief.title,
            "subject_hint": brief.subject,
            "role_phrase": brief.role_phrase,
            "role_focus": brief.role_focus,
            "opportunity_detail": brief.opportunity_detail,
            "seniority_note": brief.seniority_note,
            "source": brief.source_label,
            "job_url": lead.opportunity_url or lead.linkedin_url,
            "location": lead.opportunity_location,
            "campaign_objective": objective,
            "call_to_action": brief.cta,
            "extra_context": payload.extra_context,
        }
        return (
            "Create one job-search outreach email draft from this public-facing brief only.\n"
            "Do not mention or infer hidden scoring, matching, scraping, confidence, source adapters, "
            "or internal pipeline state. The email should sound like a real recent graduate asking for "
            "consideration, guidance, or the right application path, not a sales pitch.\n"
            "Email constraints: 70-130 words, one clear CTA, no markdown, no bullets. "
            "Use the subject_hint unless you can make it shorter and clearer. Good subjects: 'Backend Engineer role at Creator' or "
            "'Question about junior software roles at Company'. Do not use salesy subjects like 'Quick idea'. "
            "Mention one position-specific reason using role_focus or opportunity_detail. "
            "Do not say 'very enthusiastic', 'I would welcome the opportunity', or 'Open to a 15-minute conversation?'. "
            "Do not use the phrase 'What stood out from my research'. "
            "Do not mention research if the only context is a source URL, score, keyword match, or generic imported note. "
            "Do not ask for a call unless the call_to_action explicitly asks for one. Sign as Prakriti.\n"
            f"Public draft brief JSON:\n{json.dumps(lead_context, indent=2)}"
        )

    @staticmethod
    def _public_outreach_context(lead: LeadModel) -> str:
        return AIDraftService._draft_brief(lead, DraftGenerateRequest(lead_id=lead.id)).opportunity_detail

    @staticmethod
    def _draft_brief(lead: LeadModel, payload: DraftGenerateRequest) -> PublicDraftBrief:
        company = AIDraftService._public_company(lead)
        title = AIDraftService._public_title(lead)
        greeting_name = AIDraftService._public_greeting_name(lead)
        role_phrase = AIDraftService._public_role_phrase(lead)
        role_focus = AIDraftService._role_focus(lead)
        subject = AIDraftService._public_subject(lead, AIDraftService._public_subject_context(lead))
        opportunity_detail = AIDraftService._opportunity_detail(lead, role_focus)
        seniority_note = AIDraftService._seniority_note(lead)
        source_label = AIDraftService._public_source_label(lead)
        cta = AIDraftService._safe_call_to_action(payload.call_to_action)
        return PublicDraftBrief(
            greeting_name=greeting_name,
            company=company,
            title=title,
            subject=subject,
            role_phrase=role_phrase,
            role_focus=role_focus,
            opportunity_detail=opportunity_detail,
            seniority_note=seniority_note,
            source_label=source_label,
            cta=cta,
        )

    @staticmethod
    def _public_greeting_name(lead: LeadModel) -> str:
        name = (lead.contact_name or lead.first_name or "Hiring Team").strip()
        if not name or "http" in name.lower() or "@" in name:
            return "Hiring Team"
        lowered = name.lower()
        if lowered in {"recruiting team", "recruiter", "hiring team", "team"}:
            return name
        return name.split()[0]

    @staticmethod
    def _public_company(lead: LeadModel) -> str:
        company = (lead.company or "").strip()
        if company and company.lower() not in PLACEHOLDER_COMPANIES:
            return company
        return "your team"

    @staticmethod
    def _public_title(lead: LeadModel) -> str:
        title = (lead.title or "").strip()
        if title and title.lower() not in PLACEHOLDER_TITLES:
            return title
        return ""

    @staticmethod
    def _public_role_phrase(lead: LeadModel) -> str:
        title = AIDraftService._public_title(lead)
        company = AIDraftService._public_company(lead)
        if title:
            if company != "your team":
                return f"the {title} role at {company}"
            return f"the {title} role"
        source = (lead.source or "").lower()
        if "linkedin" in source:
            return "the role I found on LinkedIn"
        if "indeed" in source:
            return "the role I found on Indeed"
        return "this opportunity"

    @staticmethod
    def _public_subject_context(lead: LeadModel) -> str:
        title = AIDraftService._public_title(lead)
        if title:
            return title
        company = AIDraftService._public_company(lead)
        if company != "your team":
            return company
        source = (lead.source or "").lower()
        if "linkedin" in source:
            return "the LinkedIn role"
        if "indeed" in source:
            return "the Indeed role"
        return "your team"

    @staticmethod
    def _public_subject(lead: LeadModel, fallback_context: str) -> str:
        title = AIDraftService._public_title(lead)
        company = AIDraftService._public_company(lead)
        if title and company != "your team":
            return f"{title} role at {company}"
        if title:
            return f"Question about the {title} role"
        if company != "your team":
            return f"Question about junior roles at {company}"
        return f"Question about {fallback_context}"

    @staticmethod
    def _public_skill_list(value: str | None) -> str:
        if not value:
            return ""
        blocked = {
            "fit",
            "score",
            "matched",
            "contact",
            "profile",
            "available",
            "source",
            "links",
            "role",
            "location",
        }
        skills: list[str] = []
        for raw_skill in value.replace("|", ",").split(","):
            skill = raw_skill.strip()
            if not skill:
                continue
            lowered = skill.lower()
            if any(word in lowered for word in blocked):
                continue
            if skill not in skills:
                skills.append(skill)
            if len(skills) == 3:
                break
        if not skills:
            return ""
        if len(skills) == 1:
            return skills[0]
        if len(skills) == 2:
            return f"{skills[0]} and {skills[1]}"
        return f"{skills[0]}, {skills[1]}, and {skills[2]}"

    @staticmethod
    def _role_focus(lead: LeadModel) -> str:
        text = AIDraftService._public_source_text(lead)
        title = AIDraftService._public_title(lead).lower()
        combined = f"{title} {text}".lower()
        if any(token in combined for token in ("qa", "quality assurance", "test automation", "automation engineer")):
            return "testing, automation, and reliable software delivery"
        if any(token in combined for token in ("llm", "machine learning", "ai ", "artificial intelligence", "genai", "rag")):
            return "AI-enabled products, backend systems, and automation"
        if any(token in combined for token in ("backend", "api", "database", "postgres", "python", "fastapi", "node")):
            return "backend development, APIs, and data-driven systems"
        if any(token in combined for token in ("frontend", "front-end", "react", "typescript", "javascript", "web")):
            return "web development, user-facing features, and frontend engineering"
        if any(token in combined for token in ("cloud", "devops", "gcp", "aws", "docker", "kubernetes")):
            return "cloud, automation, and infrastructure-adjacent engineering"
        if any(token in combined for token in ("support", "help desk", "it ", "systems")):
            return "technical support, systems, and practical problem solving"
        skills = AIDraftService._public_skill_list(lead.tech_stack)
        if skills:
            return f"{skills} and practical software work"
        return "software development and practical automation work"

    @staticmethod
    def _opportunity_detail(lead: LeadModel, role_focus: str) -> str:
        highlight = AIDraftService._public_job_highlight(lead)
        if highlight:
            return (
                f"The role stood out to me because it involves {role_focus}, especially {highlight}."
            )
        return (
            f"The role stood out to me because it connects with my project work around {role_focus}."
        )

    @staticmethod
    def _seniority_note(lead: LeadModel) -> str:
        source_text = AIDraftService._public_source_text(lead).lower()
        if re.search(r"\b(senior|sr\.?|staff|principal|lead|manager|director|architect)\b", source_text):
            return (
                "I realize this role may be more experienced than my current level, but I am a recent graduate "
                "and would be grateful for guidance on junior-friendly openings or the right path to be considered."
            )
        return (
            "As a recent graduate, I am looking for junior-friendly opportunities where I can keep learning "
            "while contributing carefully through practical engineering work."
        )

    @staticmethod
    def _public_job_highlight(lead: LeadModel) -> str:
        text = AIDraftService._clean_public_text(
            lead.opportunity_description
            or lead.company_summary
            or lead.role_fit
            or lead.tech_stack
            or ""
        )
        if not text:
            return ""
        sentence = re.split(r"(?<=[.!?])\s+", text.strip())[0]
        sentence = re.sub(r"\s+", " ", sentence).strip(" .")
        if len(sentence) > 150:
            sentence = sentence[:147].rsplit(" ", 1)[0] + "..."
        return sentence

    @staticmethod
    def _public_source_text(lead: LeadModel) -> str:
        return AIDraftService._clean_public_text(
            " ".join(
                part
                for part in (
                    lead.title,
                    lead.opportunity_location,
                    lead.opportunity_description,
                    lead.company_summary,
                    lead.tech_stack,
                    lead.role_fit,
                )
                if part
            )
        )

    @staticmethod
    def _public_source_label(lead: LeadModel) -> str:
        source = str(lead.source or "").upper()
        if "LINKEDIN" in source:
            return "LinkedIn"
        if "INDEED" in source:
            return "Indeed"
        if source:
            return source.title()
        return "job source"

    @staticmethod
    def _clean_public_text(value: str | None) -> str:
        text = re.sub(r"https?://\S+", "", value or "")
        text = re.sub(
            r"(?i)\b(company from pasted job|unknown company|linkedin job opportunity|"
            r"indeed job opportunity|glassdoor job opportunity)\b",
            "",
            text,
        )
        text = re.sub(
            r"(?i)\b(fit score|score basis|matched role keywords?|matched roles?|matched locations?|matched skills?|"
            r"contact/profile link available|contact finder status|confidence|verification|source links?)\b[^.?!]*(?:[.?!]|$)",
            "",
            text,
        )
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def _remove_internal_language(body: str) -> str:
        blocked_fragments = [
            "fit score",
            "score basis",
            "matched role",
            "matched location",
            "matched skills",
            "matched locations",
            "contact/profile link available",
            "no scraping",
            "source data",
            "manual url/description tracking",
            "linkedin automation",
            "confidence",
            "verification",
            "source adapter",
            "source links",
            "lead grade",
            "outreach status",
            "contact finder status",
            "what stood out from my research",
        ]
        lines = []
        for line in body.splitlines():
            lowered = line.lower()
            if any(fragment in lowered for fragment in blocked_fragments):
                continue
            lines.append(line)
        cleaned = "\n".join(lines).strip()
        cleaned = re.sub(r"\bI\W+d\b", "I would", cleaned)
        replacements = {
            r"(?i)\bI am writing to express my interest in\b": "I came across",
            r"(?i)\bI am reaching out regarding\b": "I came across",
            r"(?i)\bI would welcome the opportunity to discuss how my technical skills align with[^.?!]*[.?!]": EARLY_CAREER_CTA,
            r"(?i)\bI would welcome the opportunity to discuss[^.?!]*[.?!]": EARLY_CAREER_CTA,
            r"(?i)\bI would be happy to discuss how my background[^.?!]*[.?!]": EARLY_CAREER_CTA,
            r"(?i)\bOpen to a 15-minute conversation\?": EARLY_CAREER_CTA,
            r"(?i)\bWould it be worth a quick conversation next week\?": EARLY_CAREER_CTA,
            r"(?i)\bWould you be open to a brief conversation[^.?!]*[.?!]": EARLY_CAREER_CTA,
            r"(?i)\byour upcoming engineering milestones and data layer evolution\b": "the role and your team's work",
            r"(?i)\bvery enthusiastic about the work your team is doing to\b": "interested in learning more about how your team works on",
            r"(?i)\bWith my professional background\b": "As a recent graduate with project experience",
            r"(?i)\bmy professional experience\b": "my project experience",
        }
        for pattern, replacement in replacements.items():
            cleaned = re.sub(pattern, replacement, cleaned)
        return cleaned.strip()

    @staticmethod
    def _safe_call_to_action(call_to_action: str | None) -> str:
        if not call_to_action:
            return EARLY_CAREER_CTA
        cleaned = AIDraftService._remove_internal_language(call_to_action.strip())
        blocked = (
            "15-minute conversation",
            "quick conversation",
            "technical skills align",
            "upcoming engineering milestones",
        )
        if not cleaned or any(fragment in cleaned.lower() for fragment in blocked):
            return EARLY_CAREER_CTA
        return cleaned

    @staticmethod
    def _clean_public_body(body: str) -> str:
        cleaned = AIDraftService._remove_internal_language(body)
        cleaned = re.sub(
            r"\n+\s*(best regards|best|regards|sincerely|thanks),?\s*(\n+\s*(candidate|prakriti))?\s*$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        ).strip()
        return f"{cleaned}\n\nBest,\nPrakriti"

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
        content = content.strip()
        if content.startswith("```"):
            content = content.removeprefix("```json").removeprefix("```").strip()
            if content.endswith("```"):
                content = content[:-3].strip()
        candidates = [content]
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and start < end:
            candidates.append(content[start:end + 1])
        last_error: json.JSONDecodeError | None = None
        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
                break
            except json.JSONDecodeError as exc:
                last_error = exc
        else:
            raise AIDraftError("AI response was not valid JSON.") from last_error
        if not isinstance(parsed, dict):
            raise AIDraftError("AI response JSON must be an object.")
        return parsed
