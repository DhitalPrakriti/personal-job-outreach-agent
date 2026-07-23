"""Discover job opportunities from public career and job listing pages."""

from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
import re

import httpx

from app.schemas.pipeline import JobDiscoveryItem, JobSourceDiscoveryRequest


_EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_SPACE_PATTERN = re.compile(r"\s+")
_JOB_PATH_PATTERN = re.compile(
    r"(job|jobs|career|careers|position|positions|opening|openings|greenhouse|lever|ashby|workable)",
    re.IGNORECASE,
)
_SKIP_PATH_PATTERN = re.compile(
    r"(login|signin|privacy|terms|cookie|policy|benefits|blog|press|news|events|help)",
    re.IGNORECASE,
)
_SKIP_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".zip", ".doc", ".docx")


@dataclass
class DiscoveredJobsResult:
    scanned_sources: int = 0
    jobs: list[JobDiscoveryItem] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class _CareerPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.text_parts: list[str] = []
        self.links: list[tuple[str, str]] = []
        self._in_title = False
        self._current_href: str | None = None
        self._current_link_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "title":
            self._in_title = True
        if tag.lower() == "a":
            attrs_dict = dict(attrs)
            href = attrs_dict.get("href")
            if href:
                self._current_href = href
                self._current_link_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False
        if tag.lower() == "a" and self._current_href:
            link_text = _clean_text(" ".join(self._current_link_text))
            self.links.append((self._current_href, link_text))
            self._current_href = None
            self._current_link_text = []

    def handle_data(self, data: str) -> None:
        text = _clean_text(data)
        if not text:
            return
        self.text_parts.append(text)
        if self._in_title:
            self.title = _clean_text(f"{self.title} {text}")
        if self._current_href:
            self._current_link_text.append(text)


class JobSourceDiscoveryService:
    async def discover(self, payload: JobSourceDiscoveryRequest) -> DiscoveredJobsResult:
        result = DiscoveredJobsResult()
        headers = {
            "User-Agent": (
                "PersonalOutreachAgent/0.1 "
                "(job discovery for one user's human-reviewed outreach)"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=20) as client:
            for source_url in payload.source_urls:
                result.scanned_sources += 1
                try:
                    adapter_jobs = await self._discover_with_known_adapter(client, source_url, payload)
                except httpx.HTTPError as exc:
                    result.errors.append(f"{source_url}: known job-board adapter failed with {type(exc).__name__}")
                    continue
                if adapter_jobs is not None:
                    result.jobs.extend(adapter_jobs)
                    continue

                try:
                    response = await client.get(source_url)
                    response.raise_for_status()
                except httpx.HTTPError as exc:
                    result.errors.append(f"{source_url}: {type(exc).__name__}")
                    continue

                content_type = response.headers.get("content-type", "")
                if "html" not in content_type and "text" not in content_type:
                    result.errors.append(f"{source_url}: response was not an HTML/text page")
                    continue

                jobs = self._extract_jobs(
                    html=response.text,
                    source_url=str(response.url),
                    payload=payload,
                    contact_email=await self._discover_contact_email(client, str(response.url), response.text),
                )
                result.jobs.extend(jobs)

        result.jobs = self._dedupe_jobs(result.jobs)
        return result

    async def _discover_with_known_adapter(
        self,
        client: httpx.AsyncClient,
        source_url: str,
        payload: JobSourceDiscoveryRequest,
    ) -> list[JobDiscoveryItem] | None:
        parsed = urlparse(source_url)
        hostname = parsed.hostname or ""

        if "greenhouse.io" in hostname:
            token = self._greenhouse_board_token(source_url)
            if token:
                return await self._discover_greenhouse(client, source_url, token, payload)

        if "lever.co" in hostname:
            site = self._lever_site_name(source_url)
            if site:
                return await self._discover_lever(client, source_url, site, payload)

        if "ashbyhq.com" in hostname:
            board_name = self._ashby_board_name(source_url)
            if board_name:
                return await self._discover_ashby(client, source_url, board_name, payload)

        return None

    async def _discover_greenhouse(
        self,
        client: httpx.AsyncClient,
        source_url: str,
        board_token: str,
        payload: JobSourceDiscoveryRequest,
    ) -> list[JobDiscoveryItem]:
        api_url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true"
        response = await client.get(api_url, headers={"Accept": "application/json"})
        response.raise_for_status()
        data = response.json()
        jobs = []
        company = board_token.replace("-", " ").replace("_", " ").title()
        for item in data.get("jobs", []):
            title = _clean_text(str(item.get("title") or ""))
            location = _clean_text(str((item.get("location") or {}).get("name") or ""))
            description = _html_to_text(str(item.get("content") or ""))
            job_url = str(item.get("absolute_url") or source_url)
            if not self._looks_like_target_job(f"{title} {location} {description}", payload):
                continue
            jobs.append(
                self._job_item_from_parts(
                    company=company,
                    title=title,
                    location=location,
                    url=job_url,
                    description=description,
                    source_url=source_url,
                    source="greenhouse_api",
                    payload=payload,
                )
            )
            if len(jobs) >= payload.max_jobs_per_source:
                break
        return jobs

    async def _discover_lever(
        self,
        client: httpx.AsyncClient,
        source_url: str,
        site: str,
        payload: JobSourceDiscoveryRequest,
    ) -> list[JobDiscoveryItem]:
        api_url = f"https://api.lever.co/v0/postings/{site}?mode=json"
        response = await client.get(api_url, headers={"Accept": "application/json"})
        response.raise_for_status()
        data = response.json()
        jobs = []
        company = site.replace("-", " ").replace("_", " ").title()
        for item in data if isinstance(data, list) else []:
            title = _clean_text(str(item.get("text") or ""))
            categories = item.get("categories") or {}
            location = _clean_text(str(categories.get("location") or ""))
            description = _clean_text(str(item.get("descriptionPlain") or item.get("openingPlain") or ""))
            job_url = str(item.get("hostedUrl") or source_url)
            if not self._looks_like_target_job(f"{title} {location} {description}", payload):
                continue
            jobs.append(
                self._job_item_from_parts(
                    company=company,
                    title=title,
                    location=location,
                    url=job_url,
                    description=description,
                    source_url=source_url,
                    source="lever_api",
                    payload=payload,
                )
            )
            if len(jobs) >= payload.max_jobs_per_source:
                break
        return jobs

    async def _discover_ashby(
        self,
        client: httpx.AsyncClient,
        source_url: str,
        board_name: str,
        payload: JobSourceDiscoveryRequest,
    ) -> list[JobDiscoveryItem]:
        api_url = f"https://api.ashbyhq.com/posting-api/job-board/{board_name}"
        response = await client.get(api_url, headers={"Accept": "application/json"})
        response.raise_for_status()
        data = response.json()
        jobs = []
        company = board_name.replace("-", " ").replace("_", " ").title()
        for item in data.get("jobs", []):
            title = _clean_text(str(item.get("title") or ""))
            location = _clean_text(str(item.get("location") or ""))
            description = _html_to_text(str(item.get("descriptionHtml") or item.get("descriptionPlain") or ""))
            job_url = str(item.get("jobUrl") or item.get("externalLink") or source_url)
            if not self._looks_like_target_job(f"{title} {location} {description}", payload):
                continue
            jobs.append(
                self._job_item_from_parts(
                    company=company,
                    title=title,
                    location=location,
                    url=job_url,
                    description=description,
                    source_url=source_url,
                    source="ashby_api",
                    payload=payload,
                )
            )
            if len(jobs) >= payload.max_jobs_per_source:
                break
        return jobs

    def _extract_jobs(
        self,
        html: str,
        source_url: str,
        payload: JobSourceDiscoveryRequest,
        contact_email: str | None = None,
    ) -> list[JobDiscoveryItem]:
        parser = _CareerPageParser()
        parser.feed(html)

        page_text = _clean_text(" ".join(parser.text_parts))
        company = self._company_name(source_url, parser.title)
        contact_email = contact_email or self._best_contact_email(page_text)
        jobs: list[JobDiscoveryItem] = []

        for href, link_text in parser.links:
            absolute_url = urljoin(source_url, href)
            if not self._is_candidate_url(absolute_url):
                continue

            combined_text = f"{link_text} {absolute_url}"
            if not self._looks_like_target_job(combined_text, payload):
                continue

            title = self._job_title(link_text, absolute_url)
            if not title:
                continue

            matched_locations = self._matched_terms(combined_text, payload.target_locations)
            matched_skills = self._matched_terms(f"{combined_text} {page_text}", payload.target_skills)
            matched_roles = self._matched_terms(combined_text, payload.target_roles)

            jobs.append(
                JobDiscoveryItem(
                    company=company,
                    title=title,
                    location=", ".join(matched_locations) if matched_locations else None,
                    url=absolute_url,
                    description=f"Discovered from {source_url}. Link text: {title}.",
                    company_summary=self._summary_from_page(company, parser.title, source_url),
                    tech_stack=", ".join(matched_skills) if matched_skills else None,
                    role_fit=self._role_fit_note(matched_roles, matched_locations, matched_skills),
                    source_links=f"{source_url}\n{absolute_url}",
                    contact_email=contact_email,
                    contact_name="Recruiting Team" if contact_email else None,
                    contact_url=source_url,
                    source="career_page_discovery",
                )
            )
            if len(jobs) >= payload.max_jobs_per_source:
                return jobs

        if not jobs and self._looks_like_target_job(page_text, payload):
            matched_roles = self._matched_terms(page_text, payload.target_roles)
            matched_locations = self._matched_terms(page_text, payload.target_locations)
            matched_skills = self._matched_terms(page_text, payload.target_skills)
            title = matched_roles[0] if matched_roles else "Open role"
            jobs.append(
                JobDiscoveryItem(
                    company=company,
                    title=title,
                    location=", ".join(matched_locations) if matched_locations else None,
                    url=source_url,
                    description=_clean_text(page_text[:700]),
                    company_summary=self._summary_from_page(company, parser.title, source_url),
                    tech_stack=", ".join(matched_skills) if matched_skills else None,
                    role_fit=self._role_fit_note(matched_roles, matched_locations, matched_skills),
                    source_links=source_url,
                    contact_email=contact_email,
                    contact_name="Recruiting Team" if contact_email else None,
                    contact_url=source_url,
                    source="career_page_discovery",
                )
            )

        return jobs[: payload.max_jobs_per_source]

    async def _discover_contact_email(
        self,
        client: httpx.AsyncClient,
        source_url: str,
        html: str,
    ) -> str | None:
        parser = _CareerPageParser()
        parser.feed(html)
        page_text = _clean_text(" ".join(parser.text_parts))
        direct_email = self._best_contact_email(page_text)
        if direct_email:
            return direct_email

        contact_urls = []
        for href, link_text in parser.links:
            combined = f"{href} {link_text}".lower()
            if not any(term in combined for term in ("contact", "career", "jobs", "people", "talent")):
                continue
            absolute_url = urljoin(source_url, href)
            if urlparse(absolute_url).hostname != urlparse(source_url).hostname:
                continue
            if absolute_url not in contact_urls:
                contact_urls.append(absolute_url)
            if len(contact_urls) >= 4:
                break

        for contact_url in contact_urls:
            try:
                response = await client.get(contact_url)
                response.raise_for_status()
            except httpx.HTTPError:
                continue
            email = self._best_contact_email(response.text)
            if email:
                return email
        return None

    def _job_item_from_parts(
        self,
        company: str,
        title: str,
        location: str,
        url: str,
        description: str,
        source_url: str,
        source: str,
        payload: JobSourceDiscoveryRequest,
    ) -> JobDiscoveryItem:
        matched_locations = self._matched_terms(f"{title} {location} {description}", payload.target_locations)
        matched_skills = self._matched_terms(f"{title} {location} {description}", payload.target_skills)
        matched_roles = self._matched_terms(f"{title} {location} {description}", payload.target_roles)
        return JobDiscoveryItem(
            company=company,
            title=title,
            location=", ".join(matched_locations) if matched_locations else location or None,
            url=url,
            description=description[:4000],
            company_summary=f"{company} public job board. Public source: {source_url}",
            tech_stack=", ".join(matched_skills) if matched_skills else None,
            role_fit=self._role_fit_note(matched_roles, matched_locations, matched_skills),
            source_links=f"{source_url}\n{url}",
            contact_email=None,
            contact_name=None,
            contact_url=source_url,
            source=source,
        )

    @staticmethod
    def _dedupe_jobs(jobs: list[JobDiscoveryItem]) -> list[JobDiscoveryItem]:
        seen: set[tuple[str, str, str]] = set()
        unique_jobs = []
        for job in jobs:
            key = (job.company.lower(), job.title.lower(), (job.url or "").lower())
            if key in seen:
                continue
            seen.add(key)
            unique_jobs.append(job)
        return unique_jobs

    @staticmethod
    def _is_candidate_url(url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return False
        lowered = url.lower()
        if lowered.endswith(_SKIP_EXTENSIONS):
            return False
        if _SKIP_PATH_PATTERN.search(lowered):
            return False
        return bool(_JOB_PATH_PATTERN.search(lowered))

    def _looks_like_target_job(self, text: str, payload: JobSourceDiscoveryRequest) -> bool:
        lowered = text.lower()
        if _SKIP_PATH_PATTERN.search(lowered):
            return False

        role_terms = self._matched_terms(text, payload.target_roles)
        skill_terms = self._matched_terms(text, payload.target_skills)
        if role_terms:
            return True
        if skill_terms and _JOB_PATH_PATTERN.search(lowered):
            return True

        role_tokens = self._target_tokens(payload.target_roles)
        return bool(role_tokens and _JOB_PATH_PATTERN.search(lowered) and any(token in lowered for token in role_tokens))

    @staticmethod
    def _target_tokens(target_roles: list[str]) -> set[str]:
        ignored = {"junior", "senior", "entry", "level", "remote", "canada"}
        tokens: set[str] = set()
        for role in target_roles:
            for token in re.findall(r"[a-z0-9+#.]+", role.lower()):
                if len(token) >= 3 and token not in ignored:
                    tokens.add(token)
        return tokens

    @staticmethod
    def _matched_terms(text: str, terms: list[str]) -> list[str]:
        lowered = text.lower()
        return [term for term in terms if term and term.lower() in lowered]

    @staticmethod
    def _job_title(link_text: str, url: str) -> str | None:
        text = _clean_text(link_text)
        if not text or len(text) < 3:
            path = urlparse(url).path.strip("/")
            text = path.split("/")[-1].replace("-", " ").replace("_", " ")
        text = _clean_text(text)
        if not text or len(text) < 3:
            return None
        return text[:200]

    @staticmethod
    def _company_name(source_url: str, page_title: str) -> str:
        title = page_title.split("|")[0].split("-")[0].strip()
        lowered_title = title.lower()
        if title and not any(word in lowered_title for word in ("careers", "jobs", "open roles")):
            return title[:200]

        hostname = urlparse(source_url).hostname or "Target Company"
        parts = [part for part in hostname.split(".") if part not in {"www", "jobs", "careers"}]
        if not parts:
            return "Target Company"
        return parts[0].replace("-", " ").title()[:200]

    @staticmethod
    def _summary_from_page(company: str, page_title: str, source_url: str) -> str:
        title = page_title or f"{company} careers page"
        return f"{title}. Public source: {source_url}"[:2000]

    @staticmethod
    def _role_fit_note(
        matched_roles: list[str],
        matched_locations: list[str],
        matched_skills: list[str],
    ) -> str:
        parts = []
        if matched_roles:
            parts.append(f"role match: {', '.join(matched_roles)}")
        if matched_locations:
            parts.append(f"location match: {', '.join(matched_locations)}")
        if matched_skills:
            parts.append(f"skill match: {', '.join(matched_skills)}")
        return "; ".join(parts) if parts else "Potential role discovered from public career page."

    @staticmethod
    def _best_contact_email(text: str) -> str | None:
        emails = sorted({email.lower() for email in _EMAIL_PATTERN.findall(text)})
        emails = [email for email in emails if not email.endswith("@example.com")]
        if not emails:
            return None

        priority_words = ("careers", "jobs", "recruit", "talent", "hr", "people")
        prioritized = [
            email for email in emails if any(word in email.split("@", maxsplit=1)[0] for word in priority_words)
        ]
        return (prioritized or emails)[0]

    @staticmethod
    def _greenhouse_board_token(source_url: str) -> str | None:
        parsed = urlparse(source_url)
        hostname = parsed.hostname or ""
        parts = [part for part in parsed.path.strip("/").split("/") if part]
        if hostname == "boards.greenhouse.io" and parts:
            return parts[0]
        if hostname == "job-boards.greenhouse.io" and parts:
            return parts[0]
        if "boards-api.greenhouse.io" in hostname:
            try:
                boards_index = parts.index("boards")
                return parts[boards_index + 1]
            except (ValueError, IndexError):
                return None
        return None

    @staticmethod
    def _lever_site_name(source_url: str) -> str | None:
        parsed = urlparse(source_url)
        hostname = parsed.hostname or ""
        parts = [part for part in parsed.path.strip("/").split("/") if part]
        if hostname == "jobs.lever.co" and parts:
            return parts[0]
        if hostname == "api.lever.co":
            try:
                postings_index = parts.index("postings")
                return parts[postings_index + 1]
            except (ValueError, IndexError):
                return None
        return None

    @staticmethod
    def _ashby_board_name(source_url: str) -> str | None:
        parsed = urlparse(source_url)
        hostname = parsed.hostname or ""
        parts = [part for part in parsed.path.strip("/").split("/") if part]
        if hostname == "jobs.ashbyhq.com" and parts:
            return parts[0]
        if hostname == "api.ashbyhq.com":
            try:
                board_index = parts.index("job-board")
                return parts[board_index + 1]
            except (ValueError, IndexError):
                return None
        return None


def _clean_text(value: str) -> str:
    return _SPACE_PATTERN.sub(" ", value).strip()


def _html_to_text(value: str) -> str:
    parser = _CareerPageParser()
    parser.feed(value)
    return _clean_text(" ".join(parser.text_parts))
