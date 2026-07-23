"""Source-aware company research for discovered job opportunities."""

from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
import re

import httpx

from app.db.models import LeadModel


_SPACE_PATTERN = re.compile(r"\s+")
_SKIP_HOST_PARTS = (
    "linkedin.",
    "indeed.",
    "glassdoor.",
    "facebook.",
    "instagram.",
    "x.com",
    "twitter.",
    "google.",
)
_RESEARCH_LINK_PATTERN = re.compile(
    r"(about|company|career|careers|jobs|work|team|engineering|technology|product|contact)",
    re.IGNORECASE,
)
_TECH_KEYWORDS = [
    "Python",
    "FastAPI",
    "Django",
    "Flask",
    "React",
    "Next.js",
    "JavaScript",
    "TypeScript",
    "Node.js",
    "Express",
    "SQL",
    "PostgreSQL",
    "MySQL",
    "MongoDB",
    "Redis",
    "REST",
    "GraphQL",
    "API",
    "Docker",
    "Kubernetes",
    "GCP",
    "Google Cloud",
    "AWS",
    "Azure",
    "LLM",
    "AI",
    "Machine Learning",
    "Automation",
    "CI/CD",
    "Git",
    "Linux",
]


@dataclass(frozen=True)
class CompanyResearchResult:
    company_summary: str
    suggested_context: str
    tech_stack: str | None = None
    role_fit: str | None = None
    source_links: str | None = None
    evidence: list[str] = field(default_factory=list)


class _ResearchPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.description = ""
        self.text_parts: list[str] = []
        self.links: list[tuple[str, str]] = []
        self._in_title = False
        self._current_href: str | None = None
        self._current_link_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_name = tag.lower()
        attrs_dict = {key.lower(): value for key, value in attrs if key and value}
        if tag_name == "title":
            self._in_title = True
        if tag_name == "meta":
            meta_name = (attrs_dict.get("name") or attrs_dict.get("property") or "").lower()
            content = attrs_dict.get("content")
            if content and meta_name in {"description", "og:description", "twitter:description"}:
                self.description = _clean_text(content)
        if tag_name == "a":
            href = attrs_dict.get("href")
            if href:
                self._current_href = href
                self._current_link_text = []

    def handle_endtag(self, tag: str) -> None:
        tag_name = tag.lower()
        if tag_name == "title":
            self._in_title = False
        if tag_name == "a" and self._current_href:
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


class CompanyResearchAgent:
    async def research(self, lead: LeadModel) -> CompanyResearchResult:
        pages = await self._fetch_public_pages(lead)
        text_corpus = " ".join(
            [
                lead.opportunity_description or "",
                lead.company_summary or "",
                lead.tech_stack or "",
                lead.role_fit or "",
                *[page["text"] for page in pages],
            ]
        )
        tech_stack = self._detected_tech_stack(text_corpus)
        evidence = self._evidence_from_pages(pages)

        company_summary = self._company_summary(lead, pages)
        role_fit = self._role_fit(lead, tech_stack, pages)
        suggested_context = self._suggested_context(lead, company_summary, tech_stack, role_fit, evidence)
        source_links = self._source_links(lead, pages)

        return CompanyResearchResult(
            company_summary=company_summary,
            suggested_context=suggested_context,
            tech_stack=tech_stack,
            role_fit=role_fit,
            source_links=source_links,
            evidence=evidence,
        )

    async def _fetch_public_pages(self, lead: LeadModel) -> list[dict[str, str]]:
        seed_urls = self._seed_urls(lead)
        if not seed_urls:
            return []

        headers = {
            "User-Agent": (
                "PersonalOutreachAgent/0.1 "
                "(public company research for one user's human-reviewed job search)"
            ),
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
        }
        pages: list[dict[str, str]] = []
        seen_urls: set[str] = set()
        async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=15) as client:
            for url in seed_urls:
                if len(pages) >= 4:
                    break
                page = await self._fetch_page(client, url)
                if not page:
                    continue
                final_url = page["url"]
                if final_url in seen_urls:
                    continue
                seen_urls.add(final_url)
                pages.append(page)

                for link_url in self._research_links(final_url, page["links"]):
                    if len(pages) >= 4:
                        break
                    if link_url in seen_urls:
                        continue
                    linked_page = await self._fetch_page(client, link_url)
                    if linked_page:
                        seen_urls.add(linked_page["url"])
                        pages.append(linked_page)

        return pages

    async def _fetch_page(self, client: httpx.AsyncClient, url: str) -> dict[str, str] | None:
        if not self._allowed_public_url(url):
            return None
        try:
            response = await client.get(url)
            response.raise_for_status()
        except httpx.HTTPError:
            return None
        content_type = response.headers.get("content-type", "")
        if "html" not in content_type and "text" not in content_type:
            return None

        parser = _ResearchPageParser()
        parser.feed(response.text)
        page_text = _clean_text(" ".join(parser.text_parts))
        return {
            "url": str(response.url),
            "title": parser.title[:240],
            "description": parser.description[:500],
            "text": page_text[:3000],
            "links": parser.links,
        }

    @classmethod
    def _seed_urls(cls, lead: LeadModel) -> list[str]:
        urls: list[str] = []
        raw_values = [lead.opportunity_url, lead.linkedin_url, *(lead.source_links or "").splitlines()]
        for value in raw_values:
            clean = (value or "").strip()
            if not clean.startswith(("http://", "https://")):
                continue
            cls._add_url(urls, clean)
            parsed = urlparse(clean)
            if parsed.scheme and parsed.netloc and cls._allowed_public_url(clean):
                root = f"{parsed.scheme}://{parsed.netloc}"
                for suffix in ("", "/about", "/careers", "/jobs", "/engineering", "/contact"):
                    cls._add_url(urls, f"{root}{suffix}")
        return urls[:8]

    @staticmethod
    def _add_url(urls: list[str], url: str) -> None:
        if url not in urls:
            urls.append(url)

    @staticmethod
    def _allowed_public_url(url: str) -> bool:
        host = (urlparse(url).hostname or "").lower()
        if not host:
            return False
        return not any(skip_part in host for skip_part in _SKIP_HOST_PARTS)

    @classmethod
    def _research_links(cls, source_url: str, links: list[tuple[str, str]]) -> list[str]:
        source_host = urlparse(source_url).hostname
        urls: list[str] = []
        for href, link_text in links:
            combined = f"{href} {link_text}"
            if not _RESEARCH_LINK_PATTERN.search(combined):
                continue
            absolute = urljoin(source_url, href)
            if not cls._allowed_public_url(absolute):
                continue
            if urlparse(absolute).hostname != source_host:
                continue
            if absolute not in urls:
                urls.append(absolute)
            if len(urls) >= 3:
                break
        return urls

    @staticmethod
    def _detected_tech_stack(text: str) -> str | None:
        lowered = text.lower()
        found = []
        for keyword in _TECH_KEYWORDS:
            if keyword.lower() in lowered and keyword not in found:
                found.append(keyword)
        return ", ".join(found[:12]) if found else None

    @staticmethod
    def _evidence_from_pages(pages: list[dict[str, str]]) -> list[str]:
        evidence = []
        for page in pages:
            title = page["title"] or "Public page"
            description = page["description"]
            if description:
                evidence.append(f"{title}: {description}")
            else:
                evidence.append(f"{title}: {page['url']}")
        return evidence[:5]

    def _company_summary(self, lead: LeadModel, pages: list[dict[str, str]]) -> str:
        parts = []
        if lead.company:
            parts.append(f"{lead.company} is the company tied to this opportunity.")
        if pages:
            titles = [page["title"] for page in pages if page["title"]]
            descriptions = [page["description"] for page in pages if page["description"]]
            if titles:
                parts.append(f"Public pages reviewed: {'; '.join(titles[:3])}.")
            if descriptions:
                parts.append(f"Company/source signals: {' '.join(descriptions[:2])}")
            else:
                text_snippets = [page["text"][:260] for page in pages if page["text"]]
                if text_snippets:
                    parts.append(f"Public page context: {' '.join(text_snippets[:2])}")
        else:
            parts.extend(self._fallback_summary_parts(lead))
        return " ".join(parts)[:2000] or "Company research source was not available."

    @staticmethod
    def _fallback_summary_parts(lead: LeadModel) -> list[str]:
        parts = []
        if lead.title:
            parts.append(f"Target role: {lead.title}.")
        if lead.opportunity_location:
            parts.append(f"Location signal: {lead.opportunity_location}.")
        if lead.opportunity_url:
            parts.append(f"Primary job/source URL: {lead.opportunity_url}.")
        if lead.opportunity_description:
            parts.append(f"Posting context: {lead.opportunity_description[:500]}")
        return parts

    @staticmethod
    def _role_fit(lead: LeadModel, tech_stack: str | None, pages: list[dict[str, str]]) -> str:
        parts = []
        if lead.title and lead.company:
            parts.append(f"{lead.title} at {lead.company}.")
        if lead.fit_score is not None:
            parts.append(f"Fit score {lead.fit_score}/100.")
        if lead.opportunity_location:
            parts.append(f"Location: {lead.opportunity_location}.")
        if tech_stack:
            parts.append(f"Detected skills/stack: {tech_stack}.")
        if pages:
            parts.append("Research source: public company/job pages.")
        elif lead.opportunity_description:
            parts.append("Research source: pasted or imported job description.")
        return " ".join(parts)[:2000]

    @staticmethod
    def _suggested_context(
        lead: LeadModel,
        company_summary: str,
        tech_stack: str | None,
        role_fit: str,
        evidence: list[str],
    ) -> str:
        context_parts = []
        if lead.title and lead.company:
            context_parts.append(f"{lead.title} at {lead.company}.")
        if lead.fit_score is not None:
            context_parts.append(f"Fit score {lead.fit_score}/100.")
        context_parts.append(f"Company research: {company_summary}")
        if tech_stack:
            context_parts.append(f"Tech stack: {tech_stack}.")
        if role_fit:
            context_parts.append(f"Role fit: {role_fit}")
        if evidence:
            context_parts.append(f"Evidence: {' | '.join(evidence[:3])}")
        return " ".join(context_parts)[:5000]

    @staticmethod
    def _source_links(lead: LeadModel, pages: list[dict[str, str]]) -> str | None:
        links = []
        for value in [lead.source_links, lead.opportunity_url, lead.linkedin_url]:
            for line in (value or "").splitlines():
                clean = line.strip()
                if clean and clean not in links:
                    links.append(clean)
        for page in pages:
            if page["url"] not in links:
                links.append(page["url"])
        return "\n".join(links[:12]) if links else None


def _clean_text(value: str) -> str:
    return _SPACE_PATTERN.sub(" ", value).strip()


__all__ = ["CompanyResearchAgent", "CompanyResearchResult"]
