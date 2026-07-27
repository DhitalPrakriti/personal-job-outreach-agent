"""Search external job feeds for matching technical roles."""

from datetime import UTC, datetime, timedelta
from dataclasses import dataclass, field
from urllib.parse import urlencode
import re

import httpx

from app.core.config import get_settings
from app.schemas.pipeline import JobDiscoveryItem, JobSearchRequest
from app.services.job_source_discovery import _html_to_text


_SPACE_PATTERN = re.compile(r"\s+")


@dataclass
class JobSearchServiceResult:
    searched_sources: int = 0
    jobs: list[JobDiscoveryItem] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class JobSearchDiscoveryService:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def search(self, payload: JobSearchRequest) -> JobSearchServiceResult:
        result = JobSearchServiceResult()
        payload.max_jobs_per_source = max(
            1,
            min(payload.max_jobs_per_source, self.settings.max_jobs_per_source),
        )
        headers = {
            "User-Agent": (
                "PersonalOutreachAgent/0.1 "
                "(job search for one user's human-reviewed outreach)"
            ),
            "Accept": "application/json",
        }
        async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=30) as client:
            for source in payload.sources:
                result.searched_sources += 1
                try:
                    if source == "remotive":
                        jobs = await self._search_remotive(client, payload)
                    elif source == "remoteok":
                        jobs = await self._search_remoteok(client, payload)
                    elif source == "adzuna":
                        jobs = await self._search_adzuna(client, payload)
                    elif source in {"indeed", "glassdoor"}:
                        raise ValueError(
                            f"{source} requires approved API/provider access; use pasted job URLs or a licensed feed"
                        )
                    elif source == "jobbank":
                        raise ValueError(
                            "jobbank requires an approved feed/export adapter; use saved Job Bank URLs for now"
                        )
                    else:
                        jobs = []
                except httpx.HTTPStatusError as exc:
                    status_code = exc.response.status_code
                    detail = _clean_text(exc.response.text)[:200]
                    result.errors.append(f"{source}: HTTP {status_code} {detail}".strip())
                    continue
                except httpx.HTTPError as exc:
                    result.errors.append(f"{source}: {type(exc).__name__}")
                    continue
                except ValueError as exc:
                    result.errors.append(f"{source}: {exc}")
                    continue

                result.jobs.extend(jobs)

        result.jobs = self._dedupe(result.jobs)[: self.settings.max_jobs_per_search_run]
        return result

    async def _search_remotive(
        self,
        client: httpx.AsyncClient,
        payload: JobSearchRequest,
    ) -> list[JobDiscoveryItem]:
        jobs: list[JobDiscoveryItem] = []
        searches = self._search_phrases(payload)
        per_query_limit = max(10, min(payload.max_jobs_per_source, 30))
        for phrase in searches:
            query = urlencode({"category": "software-dev", "search": phrase, "limit": per_query_limit})
            response = await client.get(f"https://remotive.com/api/remote-jobs?{query}")
            response.raise_for_status()
            data = response.json()
            for item in data.get("jobs", []):
                job = self._remotive_item(item, payload)
                if job:
                    jobs.append(job)
                if len(jobs) >= payload.max_jobs_per_source:
                    return jobs
        return jobs

    async def _search_remoteok(
        self,
        client: httpx.AsyncClient,
        payload: JobSearchRequest,
    ) -> list[JobDiscoveryItem]:
        response = await client.get("https://remoteok.com/api")
        response.raise_for_status()
        data = response.json()
        jobs: list[JobDiscoveryItem] = []
        for item in data if isinstance(data, list) else []:
            if not isinstance(item, dict) or not item.get("position"):
                continue
            job = self._remoteok_item(item, payload)
            if job:
                jobs.append(job)
            if len(jobs) >= payload.max_jobs_per_source:
                break
        return jobs

    async def _search_adzuna(
        self,
        client: httpx.AsyncClient,
        payload: JobSearchRequest,
    ) -> list[JobDiscoveryItem]:
        if not self.settings.adzuna_app_id or not self.settings.adzuna_app_key:
            raise ValueError("ADZUNA_APP_ID and ADZUNA_APP_KEY are not configured")

        jobs: list[JobDiscoveryItem] = []
        locations = payload.target_locations or ["Canada"]
        for phrase in self._search_phrases(payload):
            for location in locations[:6]:
                query = urlencode(
                    {
                        "app_id": self.settings.adzuna_app_id,
                        "app_key": self.settings.adzuna_app_key,
                        "results_per_page": min(payload.max_jobs_per_source, 50),
                        "what": phrase,
                        "where": location,
                        "sort_by": "date",
                        "content-type": "application/json",
                    }
                )
                url = (
                    f"https://api.adzuna.com/v1/api/jobs/"
                    f"{self.settings.adzuna_country}/search/1?{query}"
                )
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                for item in data.get("results", []):
                    job = self._adzuna_item(item, payload)
                    if job:
                        jobs.append(job)
                    if len(jobs) >= payload.max_jobs_per_source:
                        return jobs
        return jobs

    def _remotive_item(self, item: dict, payload: JobSearchRequest) -> JobDiscoveryItem | None:
        posted_at = self._parse_posted_at(item.get("publication_date"))
        if not self._is_recent_enough(posted_at, payload):
            return None
        title = _clean_text(str(item.get("title") or ""))
        company = _clean_text(str(item.get("company_name") or "Unknown Company"))
        location = _clean_text(str(item.get("candidate_required_location") or "Remote"))
        description = _html_to_text(str(item.get("description") or ""))
        url = str(item.get("url") or "")
        if not self._matches_job(title, location, description, payload):
            return None
        return self._item_from_parts(
            company=company,
            title=title,
            location=location,
            url=url,
            description=description,
            source="remotive",
            source_label="Remotive remote job feed",
            posted_at=posted_at,
            payload=payload,
        )

    def _remoteok_item(self, item: dict, payload: JobSearchRequest) -> JobDiscoveryItem | None:
        posted_at = self._parse_posted_at(item.get("date") or item.get("epoch"))
        if not self._is_recent_enough(posted_at, payload):
            return None
        title = _clean_text(str(item.get("position") or ""))
        company = _clean_text(str(item.get("company") or "Unknown Company"))
        location = _clean_text(str(item.get("location") or "Remote"))
        tags = ", ".join(str(tag) for tag in item.get("tags", []) if tag)
        description = _html_to_text(str(item.get("description") or ""))
        url = str(item.get("url") or item.get("apply_url") or "")
        searchable_description = f"{description} {tags}"
        if not self._matches_job(title, location, searchable_description, payload):
            return None
        return self._item_from_parts(
            company=company,
            title=title,
            location=location,
            url=url,
            description=searchable_description,
            source="remoteok",
            source_label="RemoteOK remote job feed",
            posted_at=posted_at,
            payload=payload,
        )

    def _adzuna_item(self, item: dict, payload: JobSearchRequest) -> JobDiscoveryItem | None:
        posted_at = self._parse_posted_at(item.get("created"))
        if not self._is_recent_enough(posted_at, payload):
            return None
        title = _clean_text(str(item.get("title") or ""))
        company = _clean_text(str((item.get("company") or {}).get("display_name") or "Unknown Company"))
        location = _clean_text(str((item.get("location") or {}).get("display_name") or "Canada"))
        description = _html_to_text(str(item.get("description") or ""))
        url = str(item.get("redirect_url") or "")
        if not self._matches_job(title, location, description, payload):
            return None
        return self._item_from_parts(
            company=company,
            title=title,
            location=location,
            url=url,
            description=description,
            source="adzuna",
            source_label="Adzuna Canada job search",
            posted_at=posted_at,
            payload=payload,
        )

    def _item_from_parts(
        self,
        company: str,
        title: str,
        location: str,
        url: str,
        description: str,
        source: str,
        source_label: str,
        posted_at: datetime | None,
        payload: JobSearchRequest,
    ) -> JobDiscoveryItem:
        matched_roles = self._matched_terms(f"{title} {description}", payload.target_roles)
        matched_locations = self._matched_locations(location, payload.target_locations)
        matched_skills = self._matched_terms(description, payload.target_skills)
        role_keywords = self._matched_role_tokens(f"{title} {description}", payload.target_roles)
        fit_parts = []
        if matched_roles:
            fit_parts.append(f"role match: {', '.join(matched_roles)}")
        if role_keywords:
            fit_parts.append(f"role keywords: {', '.join(role_keywords)}")
        if matched_locations:
            fit_parts.append(f"location match: {', '.join(matched_locations)}")
        if matched_skills:
            fit_parts.append(f"skill match: {', '.join(matched_skills)}")
        posted_label = posted_at.date().isoformat() if posted_at else "date unavailable"
        return JobDiscoveryItem(
            company=company[:200] or "Unknown Company",
            title=title[:200] or "Open IT role",
            location=location[:200] or None,
            url=url[:500] or None,
            description=description[:4000],
            company_summary=f"{company} job discovered through {source_label}. Posted: {posted_label}.",
            tech_stack=", ".join(matched_skills) if matched_skills else None,
            role_fit="; ".join(fit_parts) if fit_parts else "Matched broad IT/software search.",
            source_links=url[:2000] if url else None,
            contact_email=None,
            contact_name=None,
            contact_url=url[:500] if url else None,
            notes=f"Posted: {posted_label}. Search window: last {payload.posted_within_days} days.",
            source=source,
        )

    def _matches_job(
        self,
        title: str,
        location: str,
        description: str,
        payload: JobSearchRequest,
    ) -> bool:
        title_text = title.lower()
        location_text = location.lower()
        text = f"{title} {location} {description}".lower()
        if not text.strip():
            return False
        if self._is_senior_role(title_text) and not self._allows_senior_roles(payload.target_roles):
            return False

        role_match = bool(self._matched_terms(title_text, payload.target_roles))
        role_keyword_match = bool(self._matched_role_tokens(title_text, payload.target_roles))
        technical_title_match = bool(
            re.search(
                r"\b(ai|backend|front\s*end|frontend|full\s*stack|software|web|python|"
                r"developer|engineer|devops|qa|quality|analyst|automation|cloud|data|"
                r"programmer|it support|technical support)\b",
                title_text,
            )
        )
        skill_match = bool(self._matched_terms(text, payload.target_skills))
        location_match = bool(self._matched_locations(location, payload.target_locations))
        remote_match = self._is_remote_compatible_location(location_text, payload.target_locations)

        return (role_match or role_keyword_match or (technical_title_match and skill_match)) and (
            location_match or remote_match
        )

    @staticmethod
    def _matched_terms(text: str, terms: list[str]) -> list[str]:
        lowered = text.lower()
        return [term for term in terms if term and term.lower() in lowered]

    @staticmethod
    def _matched_locations(location: str, targets: list[str]) -> list[str]:
        lowered = location.lower()
        if not targets:
            return ["Canada"]
        matches = [target for target in targets if target and target.lower() in lowered]
        if matches:
            return matches
        wants_remote_anywhere = any(target.lower().strip() == "remote" for target in targets)
        wants_remote_canada = any(target.lower().strip() == "remote canada" for target in targets)
        wants_canada = any("canada" in target.lower() or "canadian" in target.lower() for target in targets)
        if "remote" in lowered and wants_remote_canada and any(word in lowered for word in ("canada", "canadian")):
            return ["Remote Canada"]
        if any(word in lowered for word in ("remote", "worldwide", "anywhere", "global", "americas")) and (
            wants_remote_canada or wants_canada
        ):
            return ["Remote-compatible"]
        if "remote" in lowered and wants_remote_anywhere:
            return ["Remote"]
        if any(word in lowered for word in ("canada", "canadian")):
            return ["Canada"]
        return []

    @staticmethod
    def _is_remote_compatible_location(location_text: str, targets: list[str]) -> bool:
        target_text = " ".join(target.lower().strip() for target in targets)
        wants_remote_or_canada = "remote" in target_text or "canada" in target_text or "canadian" in target_text
        if not wants_remote_or_canada:
            return False
        return any(word in location_text for word in ("remote", "worldwide", "anywhere", "global", "americas"))

    @staticmethod
    def _is_recent_enough(posted_at: datetime | None, payload: JobSearchRequest) -> bool:
        if posted_at is None:
            return True
        cutoff = datetime.now(UTC) - timedelta(days=payload.posted_within_days)
        return posted_at >= cutoff

    @staticmethod
    def _parse_posted_at(value: object) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, int | float):
            timestamp = float(value)
            if timestamp > 10_000_000_000:
                timestamp /= 1000
            return datetime.fromtimestamp(timestamp, tz=UTC)

        raw = str(value).strip()
        if not raw:
            return None
        if raw.isdigit():
            return JobSearchDiscoveryService._parse_posted_at(float(raw))

        normalized = raw.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    @staticmethod
    def _matched_role_tokens(text: str, targets: list[str]) -> list[str]:
        ignored = {
            "junior",
            "senior",
            "entry",
            "level",
            "remote",
            "canada",
            "developer",
            "engineer",
        }
        tokens = []
        lowered = text.lower()
        for target in targets:
            for token in re.findall(r"[a-z0-9+#.]+", target.lower()):
                if len(token) < 3 or token in ignored or token in tokens:
                    continue
                if token in lowered:
                    tokens.append(token)
        return tokens

    @staticmethod
    def _is_senior_role(title_text: str) -> bool:
        return bool(
            re.search(
                r"\b(senior|sr\.?|staff|principal|lead|manager|director|head of|architect|intermediate)\b"
                r"|\b(ii|iii|iv)\b",
                title_text,
            )
        )

    @staticmethod
    def _allows_senior_roles(targets: list[str]) -> bool:
        return any(
            re.search(r"\b(senior|sr\.?|staff|principal|lead|manager|director|architect)\b", target.lower())
            for target in targets
        )

    @staticmethod
    def _search_phrases(payload: JobSearchRequest) -> list[str]:
        phrases = [role for role in payload.target_roles if role.strip()]
        if phrases:
            return phrases[:10]
        return ["software developer", "backend developer", "web developer", "python developer"]

    @staticmethod
    def _dedupe(jobs: list[JobDiscoveryItem]) -> list[JobDiscoveryItem]:
        seen: set[tuple[str, str, str]] = set()
        unique_jobs = []
        for job in jobs:
            key = (job.company.lower(), job.title.lower(), (job.url or "").lower())
            if key in seen:
                continue
            seen.add(key)
            unique_jobs.append(job)
        return unique_jobs


def _clean_text(value: str) -> str:
    return _SPACE_PATTERN.sub(" ", value).strip()
