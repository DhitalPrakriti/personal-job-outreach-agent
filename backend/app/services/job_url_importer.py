"""Import a single job URL into the opportunity pipeline.

LinkedIn, Indeed, and Glassdoor are handled as manual-safe sources: the app
stores user-provided URLs and pasted descriptions, but does not scrape them.
Public company and ATS job pages can be fetched to extract JobPosting metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import unescape
from urllib.parse import parse_qs, urlparse
import json
import re

import httpx

from app.schemas.pipeline import JobDiscoveryItem, JobUrlImportRequest
from app.services.job_source_discovery import _clean_text, _html_to_text


_JSON_LD_PATTERN = re.compile(
    r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
    re.IGNORECASE | re.DOTALL,
)
_META_PATTERN_TEMPLATE = r"<meta[^>]+(?:property|name)=[\"']{name}[\"'][^>]+content=[\"']([^\"']+)[\"'][^>]*>"
_TITLE_PATTERN = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_SKILL_HINTS = (
    "Python",
    "FastAPI",
    "React",
    "JavaScript",
    "TypeScript",
    "Node.js",
    "SQL",
    "PostgreSQL",
    "REST API",
    "HTML",
    "CSS",
    "LLM",
    "AI",
    "Automation",
    "Git",
    "Docker",
    "Cloud",
    "GCP",
    "AWS",
    "Azure",
)
_RESTRICTED_SOURCES = {
    "linkedin": ("linkedin.com",),
    "indeed": ("indeed.",),
    "glassdoor": ("glassdoor.",),
}
_SOURCE_DISPLAY = {
    "linkedin": "LinkedIn",
    "indeed": "Indeed",
    "glassdoor": "Glassdoor",
}


@dataclass
class JobUrlBuildResult:
    job: JobDiscoveryItem
    source: str
    extraction_status: str
    warnings: list[str]


class JobUrlImporter:
    async def build_job(self, payload: JobUrlImportRequest) -> JobUrlBuildResult:
        parsed = urlparse(payload.source_url)
        source = self._detect_source(parsed.hostname or "", payload.source_hint)
        pipeline_url, url_warning = self._pipeline_safe_url(payload.source_url, source)
        restricted_source = source.lower()
        if restricted_source in _RESTRICTED_SOURCES:
            return self._restricted_source_job(payload, restricted_source, pipeline_url, url_warning)

        warnings: list[str] = []
        if url_warning:
            warnings.append(url_warning)
        extracted = await self._fetch_public_job(payload.source_url, warnings)
        description = payload.pasted_description or extracted.get("description")
        title = payload.job_title or extracted.get("title") or self._title_from_description(description) or "Job Opportunity"
        company = payload.company_name or extracted.get("company") or self._company_from_hostname(parsed.hostname or "") or "Unknown Company"
        location = payload.location or extracted.get("location")
        skills = self._skills_from_text(" ".join(part for part in (description, title) if part))
        contact_email = payload.contact_email or self._first_email(description or "")

        notes = self._notes(
            payload.notes,
            [
                f"Imported from pasted/public job URL: {payload.source_url}.",
                "Public page extraction attempted.",
                *warnings,
            ],
        )
        job = JobDiscoveryItem(
            company=company,
            title=title,
            location=location,
            url=pipeline_url,
            description=self._limit(description, 4000),
            company_summary=(
                f"{company} job imported from a public job URL. "
                "Structured job metadata was used when available."
            ),
            tech_stack=", ".join(skills) or None,
            role_fit=self._role_fit(title, location, description, payload),
            source_links=self._limit(payload.source_url, 2000),
            contact_email=contact_email,
            contact_name=payload.recruiter_name,
            contact_url=payload.recruiter_profile_url or pipeline_url,
            notes=notes,
            source=source,
        )
        status = "public_page_parsed" if extracted else "public_page_saved"
        return JobUrlBuildResult(job=job, source=source, extraction_status=status, warnings=warnings)

    def _restricted_source_job(
        self,
        payload: JobUrlImportRequest,
        source: str,
        pipeline_url: str,
        url_warning: str | None,
    ) -> JobUrlBuildResult:
        description = payload.pasted_description
        display_source = _SOURCE_DISPLAY.get(source, source.title())
        warnings = [
            f"{display_source} is saved as a manual-safe source. No scraping or messaging automation was performed."
        ]
        if url_warning:
            warnings.append(url_warning)
        if not description:
            warnings.append("Paste the job description later to improve fit scoring and draft quality.")
        title = payload.job_title or self._title_from_description(description) or f"{display_source} Job Opportunity"
        company = payload.company_name or self._company_from_description(description) or "Company from pasted job"
        location = payload.location or self._location_from_description(description)
        skills = self._skills_from_text(description or "")
        notes = self._notes(payload.notes, warnings)
        job = JobDiscoveryItem(
            company=company,
            title=title,
            location=location,
            url=pipeline_url,
            description=self._limit(description, 4000),
            company_summary=(
                f"{display_source} opportunity tracked from a user-pasted URL. "
                "The system does not scrape this source."
            ),
            tech_stack=", ".join(skills) or None,
            role_fit=self._role_fit(title, location, description, payload),
            source_links=self._limit(payload.source_url, 2000),
            contact_email=payload.contact_email,
            contact_name=payload.recruiter_name,
            contact_url=payload.recruiter_profile_url or pipeline_url,
            notes=notes,
            source=source.upper(),
        )
        return JobUrlBuildResult(
            job=job,
            source=source.upper(),
            extraction_status="restricted_source_saved",
            warnings=warnings,
        )

    async def _fetch_public_job(self, source_url: str, warnings: list[str]) -> dict[str, str]:
        headers = {
            "User-Agent": "PersonalOutreachAgent/0.1 (single public job URL import)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        try:
            async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=20) as client:
                response = await client.get(source_url)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            warnings.append(f"Could not fetch public URL automatically: {type(exc).__name__}.")
            return {}

        content_type = response.headers.get("content-type", "")
        if "html" not in content_type and "text" not in content_type:
            warnings.append("URL did not return an HTML/text job page.")
            return {}

        json_ld = self._json_ld_job(response.text)
        if json_ld:
            return json_ld
        text = _html_to_text(response.text)
        title = self._meta(response.text, "og:title") or self._html_title(response.text)
        return {
            key: value
            for key, value in {
                "title": title,
                "description": text[:4000],
            }.items()
            if value
        }

    def _json_ld_job(self, html: str) -> dict[str, str]:
        for raw in _JSON_LD_PATTERN.findall(html):
            for item in self._json_candidates(raw):
                if not self._is_job_posting(item):
                    continue
                organization = item.get("hiringOrganization") or {}
                return {
                    key: value
                    for key, value in {
                        "title": _clean_text(str(item.get("title") or "")),
                        "company": _clean_text(str(organization.get("name") or "")),
                        "location": self._location_from_json_ld(item.get("jobLocation")),
                        "description": _html_to_text(str(item.get("description") or "")),
                    }.items()
                    if value
                }
        return {}

    def _json_candidates(self, raw: str) -> list[dict]:
        try:
            parsed = json.loads(unescape(raw.strip()))
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, dict) and isinstance(parsed.get("@graph"), list):
            return [item for item in parsed["@graph"] if isinstance(item, dict)]
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
        return [parsed] if isinstance(parsed, dict) else []

    @staticmethod
    def _is_job_posting(item: dict) -> bool:
        item_type = item.get("@type")
        if isinstance(item_type, list):
            return any(str(value).lower() == "jobposting" for value in item_type)
        return str(item_type).lower() == "jobposting"

    def _detect_source(self, hostname: str, source_hint: str | None) -> str:
        hint = (source_hint or "").strip().upper()
        if hint and hint != "AUTO":
            return hint
        host = hostname.lower()
        for source, hosts in _RESTRICTED_SOURCES.items():
            if any(marker in host for marker in hosts):
                return source
        if "greenhouse.io" in host:
            return "GREENHOUSE"
        if "lever.co" in host:
            return "LEVER"
        if "ashbyhq.com" in host:
            return "ASHBY"
        if "workdayjobs.com" in host or "myworkdayjobs.com" in host:
            return "WORKDAY"
        if "adzuna." in host:
            return "ADZUNA"
        return "PUBLIC_JOB_URL"

    @staticmethod
    def _pipeline_safe_url(source_url: str, source: str) -> tuple[str, str | None]:
        parsed = urlparse(source_url)
        query = parse_qs(parsed.query)
        hostname = parsed.hostname or ""
        if source.lower() == "linkedin" and query.get("currentJobId"):
            job_id = query["currentJobId"][0]
            return (
                f"https://www.linkedin.com/jobs/view/{job_id}/",
                "LinkedIn search URL was normalized to the direct job-view URL.",
            )

        if source.lower() == "indeed" and query.get("jk"):
            return (
                f"{parsed.scheme}://{parsed.netloc}{parsed.path}?jk={query['jk'][0]}",
                "Indeed tracking URL was normalized to the stable job URL.",
            )

        if len(source_url) <= 500:
            return source_url, None

        for key in ("jk", "vjk", "jobId"):
            if query.get(key):
                short_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{key}={query[key][0]}"
                if len(short_url) <= 500:
                    return short_url, "Long job URL was shortened to keep the stable job identifier."

        path_only = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if hostname and len(path_only) <= 500:
            return path_only, "Long job URL query was removed before storing; original URL is kept in source links."

        return source_url[:500], "Long job URL was truncated for pipeline storage; original URL is kept in source links."

    @staticmethod
    def _location_from_json_ld(value) -> str | None:
        locations = value if isinstance(value, list) else [value]
        parts: list[str] = []
        for location in locations:
            if not isinstance(location, dict):
                continue
            address = location.get("address") or {}
            if isinstance(address, dict):
                candidate = ", ".join(
                    str(part)
                    for part in (
                        address.get("addressLocality"),
                        address.get("addressRegion"),
                        address.get("addressCountry"),
                    )
                    if part
                )
            else:
                candidate = str(address or location.get("name") or "")
            if candidate:
                parts.append(_clean_text(candidate))
        return "; ".join(parts) or None

    @staticmethod
    def _meta(html: str, name: str) -> str | None:
        pattern = re.compile(_META_PATTERN_TEMPLATE.format(name=re.escape(name)), re.IGNORECASE | re.DOTALL)
        match = pattern.search(html)
        return _clean_text(unescape(match.group(1))) if match else None

    @staticmethod
    def _html_title(html: str) -> str | None:
        match = _TITLE_PATTERN.search(html)
        return _clean_text(unescape(match.group(1))) if match else None

    @staticmethod
    def _company_from_hostname(hostname: str) -> str | None:
        host = hostname.lower().removeprefix("www.")
        if not host:
            return None
        label = host.split(".")[0]
        return label.replace("-", " ").replace("_", " ").title()

    @staticmethod
    def _title_from_description(description: str | None) -> str | None:
        if not description:
            return None
        for line in description.splitlines():
            text = _clean_text(line)
            if 5 <= len(text) <= 120 and any(word in text.lower() for word in ("developer", "engineer", "analyst", "support", "specialist", "intern")):
                return text
        return None

    @staticmethod
    def _company_from_description(description: str | None) -> str | None:
        if not description:
            return None
        patterns = (
            r"\bat\s+([A-Z][A-Za-z0-9&.\- ]{2,60})",
            r"\bCompany:\s*([A-Za-z0-9&.\- ]{2,80})",
        )
        for pattern in patterns:
            match = re.search(pattern, description)
            if match:
                return _clean_text(match.group(1))
        return None

    @staticmethod
    def _location_from_description(description: str | None) -> str | None:
        if not description:
            return None
        for marker in ("Location:", "Work location:", "Job location:"):
            if marker in description:
                return _clean_text(description.split(marker, 1)[1].splitlines()[0])
        return None

    @staticmethod
    def _skills_from_text(text: str) -> list[str]:
        lowered = text.lower()
        return [skill for skill in _SKILL_HINTS if skill.lower() in lowered]

    @staticmethod
    def _first_email(text: str) -> str | None:
        match = _EMAIL_PATTERN.search(text)
        return match.group(0) if match else None

    def _role_fit(
        self,
        title: str,
        location: str | None,
        description: str | None,
        payload: JobUrlImportRequest,
    ) -> str:
        text = " ".join(part for part in (title, location, description) if part).lower()
        parts = []
        matched_roles = [role for role in payload.target_roles if role.lower() in text]
        matched_locations = [loc for loc in payload.target_locations if loc.lower() in text]
        matched_skills = [skill for skill in payload.target_skills if skill.lower() in text]
        if matched_roles:
            parts.append(f"Matched roles: {', '.join(matched_roles)}.")
        if matched_locations:
            parts.append(f"Matched locations: {', '.join(matched_locations)}.")
        if matched_skills:
            parts.append(f"Matched skills: {', '.join(matched_skills)}.")
        if not parts:
            parts.append("Needs review after more job details are added.")
        return " ".join(parts)

    @staticmethod
    def _notes(user_notes: str | None, generated_notes: list[str]) -> str:
        parts = [note for note in [user_notes, *generated_notes] if note]
        return " ".join(parts)[:2000]

    @staticmethod
    def _limit(value: str | None, max_length: int) -> str | None:
        if not value:
            return None
        return value[:max_length]
