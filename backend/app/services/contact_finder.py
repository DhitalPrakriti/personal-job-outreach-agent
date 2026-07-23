"""Find public contact details for a discovered job opportunity."""

from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
import re

import httpx


_EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_SPACE_PATTERN = re.compile(r"\s+")
_BAD_EMAIL_WORDS = ("example", "sentry", "wixpress", "schema", "domain.com", "noreply", "no-reply")
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
_COMPANY_SUFFIX_WORDS = {
    "ai",
    "and",
    "canada",
    "co",
    "company",
    "corp",
    "corporation",
    "group",
    "inc",
    "incorporated",
    "international",
    "limited",
    "llc",
    "ltd",
    "plc",
    "solutions",
    "technologies",
    "technology",
}
_CONTACT_LINK_PATTERN = re.compile(
    r"(contact|career|careers|jobs|people|talent|recruit|hiring|about|team|staff)",
    re.IGNORECASE,
)
_LINKEDIN_PATTERN = re.compile(r"linkedin\.com/(company|in)/[^\"' <>()]+", re.IGNORECASE)


@dataclass
class ContactCandidate:
    contact_name: str | None = None
    contact_email: str | None = None
    contact_role: str | None = None
    contact_type: str | None = None
    source_url: str | None = None
    confidence_score: int = 0
    verification_status: str = "not_found"
    evidence: list[str] = field(default_factory=list)

    @property
    def found(self) -> bool:
        return bool(self.contact_email or self.source_url)


class _PageParser(HTMLParser):
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
            href = dict(attrs).get("href")
            if href:
                self._current_href = href
                self._current_link_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False
        if tag.lower() == "a" and self._current_href:
            text = _clean_text(" ".join(self._current_link_text))
            self.links.append((self._current_href, text))
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


class ContactFinderService:
    async def find_for_opportunity(
        self,
        *,
        company: str | None,
        job_url: str | None,
        source_links: str | None,
    ) -> ContactCandidate:
        urls = self._seed_urls(company, job_url, source_links)
        if not urls:
            return ContactCandidate(
                contact_name="Hiring Team",
                contact_type="fallback",
                confidence_score=20,
                verification_status="no_public_source",
                evidence=["No job or company source URL was available."],
            )

        headers = {
            "User-Agent": (
                "PersonalOutreachAgent/0.1 "
                "(public contact lookup for one user's human-reviewed outreach)"
            ),
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
        }
        pages: list[tuple[str, _PageParser, str]] = []
        async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=20) as client:
            for url in self._bounded_lookup_urls(urls):
                try:
                    response = await client.get(url)
                    response.raise_for_status()
                except httpx.HTTPError:
                    continue
                content_type = response.headers.get("content-type", "")
                if "html" not in content_type and "text" not in content_type:
                    continue
                parser = _PageParser()
                parser.feed(response.text)
                page_text = _clean_text(" ".join(parser.text_parts))
                pages.append((str(response.url), parser, page_text))

                candidate = self._candidate_from_page(str(response.url), parser, page_text, company)
                if candidate.contact_email:
                    return candidate

                for contact_url in self._contact_urls(str(response.url), parser):
                    try:
                        contact_response = await client.get(contact_url)
                        contact_response.raise_for_status()
                    except httpx.HTTPError:
                        continue
                    contact_parser = _PageParser()
                    contact_parser.feed(contact_response.text)
                    contact_text = _clean_text(" ".join(contact_parser.text_parts))
                    pages.append((str(contact_response.url), contact_parser, contact_text))
                    candidate = self._candidate_from_page(str(contact_response.url), contact_parser, contact_text, company)
                    if candidate.contact_email:
                        return candidate

        link_candidate = self._best_link_candidate(company, pages)
        if link_candidate.found:
            return link_candidate

        return ContactCandidate(
            contact_name="Hiring Team",
            contact_role="Recruiting / Hiring",
            contact_type="fallback",
            source_url=urls[0],
            confidence_score=35,
            verification_status="fallback_to_source_url",
            evidence=["No public contact email found; using the job/source URL for context."],
        )

    def _candidate_from_page(
        self,
        url: str,
        parser: _PageParser,
        page_text: str,
        company: str | None,
    ) -> ContactCandidate:
        if company and self._looks_like_guessed_company_domain(url, company) and not self._page_mentions_company(page_text, company):
            return ContactCandidate(
                source_url=url,
                confidence_score=10,
                verification_status="company_domain_unverified",
                evidence=[f"Checked {url}, but the page did not clearly match {company}."],
            )

        emails = self._ranked_emails(page_text, parser.links)
        if emails:
            for email in emails:
                if company and not self._email_matches_company_context(email, url, page_text, company):
                    continue
                return ContactCandidate(
                    contact_name="Recruiting Team",
                    contact_email=email,
                    contact_role="Recruiting / Hiring",
                    contact_type=self._contact_type(email),
                    source_url=url,
                    confidence_score=self._email_confidence(email, url),
                    verification_status="public_email_found",
                    evidence=[f"Public email found on {url}: {email}"],
                )

        linkedin_urls = self._linkedin_urls(page_text, parser, url)
        if linkedin_urls:
            return ContactCandidate(
                contact_name="Recruiting Team",
                contact_role="Recruiting / Hiring",
                contact_type="linkedin_or_company_profile",
                source_url=linkedin_urls[0],
                confidence_score=45,
                verification_status="public_profile_link_found",
                evidence=[f"Public LinkedIn/contact URL found: {linkedin_urls[0]}"],
            )

        return ContactCandidate()

    def _best_link_candidate(
        self,
        company: str | None,
        pages: list[tuple[str, _PageParser, str]],
    ) -> ContactCandidate:
        for page_url, parser, page_text in pages:
            for href, link_text in parser.links:
                combined = f"{href} {link_text}"
                if not _CONTACT_LINK_PATTERN.search(combined):
                    continue
                absolute = urljoin(page_url, href)
                if not self._allowed_public_url(absolute):
                    continue
                if company and company.lower() in combined.lower():
                    score = 58
                elif any(word in combined.lower() for word in ("career", "jobs", "talent", "recruit", "hiring")):
                    score = 55
                else:
                    score = 48
                return ContactCandidate(
                    contact_name="Hiring Team",
                    contact_role="Recruiting / Hiring",
                    contact_type="contact_page",
                    source_url=absolute,
                    confidence_score=score,
                    verification_status="public_contact_url_found",
                    evidence=[f"Public contact/careers URL found: {absolute}"],
                )

            linkedin_urls = self._linkedin_urls(page_text, parser, page_url)
            if linkedin_urls:
                return ContactCandidate(
                    contact_name="Recruiting Team",
                    contact_role="Recruiting / Hiring",
                    contact_type="linkedin_or_company_profile",
                    source_url=linkedin_urls[0],
                    confidence_score=45,
                    verification_status="public_profile_link_found",
                    evidence=[f"Public LinkedIn/contact URL found on company/source page: {linkedin_urls[0]}"],
                )

        return ContactCandidate()

    @staticmethod
    def _seed_urls(company: str | None, job_url: str | None, source_links: str | None) -> list[str]:
        urls: list[str] = []
        for candidate in ContactFinderService._company_url_guesses(company):
            if candidate not in urls:
                urls.append(candidate)

        for value in [job_url, *(source_links or "").splitlines()]:
            clean = (value or "").strip()
            if not clean or not clean.startswith(("http://", "https://")):
                continue
            if not ContactFinderService._allowed_public_url(clean):
                continue
            if clean not in urls:
                urls.append(clean)

            parsed = urlparse(clean)
            if parsed.scheme and parsed.netloc:
                root = f"{parsed.scheme}://{parsed.netloc}"
                for suffix in ("", "/careers", "/jobs", "/contact", "/about", "/team", "/people"):
                    candidate = f"{root}{suffix}"
                    if candidate not in urls:
                        urls.append(candidate)
        return urls[:20]

    @staticmethod
    def _company_url_guesses(company: str | None) -> list[str]:
        if not company:
            return []
        words = [
            word
            for word in re.findall(r"[a-z0-9]+", company.lower().replace("&", " and "))
            if word not in _COMPANY_SUFFIX_WORDS
        ]
        if not words:
            return []
        slugs = []
        for slug in ("-".join(words), "".join(words)):
            if slug and slug not in slugs:
                slugs.append(slug)
        urls: list[str] = []
        for slug in slugs[:2]:
            for tld in ("com", "ca", "io", "ai", "co"):
                root = f"https://www.{slug}.{tld}"
                for suffix in ("", "/careers", "/jobs", "/contact", "/about"):
                    urls.append(f"{root}{suffix}")
        return urls[:18]

    @staticmethod
    def _allowed_public_url(url: str) -> bool:
        host = (urlparse(url).hostname or "").lower()
        if not host:
            return False
        return not any(skip_part in host for skip_part in _SKIP_HOST_PARTS)

    @staticmethod
    def _looks_like_guessed_company_domain(url: str, company: str) -> bool:
        host = (urlparse(url).hostname or "").lower().removeprefix("www.")
        company_tokens = [
            token
            for token in re.findall(r"[a-z0-9]+", company.lower())
            if token not in _COMPANY_SUFFIX_WORDS
        ]
        return bool(company_tokens and any(token in host for token in company_tokens))

    @staticmethod
    def _page_mentions_company(page_text: str, company: str) -> bool:
        text = page_text.lower()
        tokens = [
            token
            for token in re.findall(r"[a-z0-9]+", company.lower())
            if token not in _COMPANY_SUFFIX_WORDS
        ]
        if not tokens:
            return False
        return any(token in text for token in tokens)

    @staticmethod
    def _email_matches_company_context(email: str, url: str, page_text: str, company: str) -> bool:
        tokens = [
            token
            for token in re.findall(r"[a-z0-9]+", company.lower())
            if token not in _COMPANY_SUFFIX_WORDS
        ]
        if not tokens:
            return False
        host = (urlparse(url).hostname or "").lower()
        domain = email.split("@", maxsplit=1)[1].lower()
        local_part = email.split("@", maxsplit=1)[0].lower()
        company_on_page = ContactFinderService._page_mentions_company(page_text, company)
        domain_or_host_match = any(token in host or token in domain for token in tokens)
        recruiting_email = any(
            word in local_part
            for word in ("career", "jobs", "talent", "recruit", "hiring", "hr", "people")
        )
        return domain_or_host_match or (company_on_page and recruiting_email)

    @staticmethod
    def _bounded_lookup_urls(urls: list[str]) -> list[str]:
        return urls[:12]

    @staticmethod
    def _contact_urls(source_url: str, parser: _PageParser) -> list[str]:
        urls: list[str] = []
        source_host = urlparse(source_url).hostname
        for href, link_text in parser.links:
            combined = f"{href} {link_text}"
            if not _CONTACT_LINK_PATTERN.search(combined):
                continue
            absolute = urljoin(source_url, href)
            if not ContactFinderService._allowed_public_url(absolute):
                continue
            if urlparse(absolute).hostname != source_host:
                continue
            if absolute not in urls:
                urls.append(absolute)
            if len(urls) >= 4:
                break
        return urls

    @staticmethod
    def _ranked_emails(text: str, links: list[tuple[str, str]] | None = None) -> list[str]:
        linked_text = " ".join(
            href.replace("mailto:", " ")
            for href, _link_text in (links or [])
            if href.lower().startswith("mailto:")
        )
        emails = sorted({email.lower() for email in _EMAIL_PATTERN.findall(f"{text} {linked_text}")})
        emails = [
            email
            for email in emails
            if not any(bad_word in email for bad_word in _BAD_EMAIL_WORDS)
        ]
        priority_words = ("careers", "career", "jobs", "recruit", "talent", "hr", "people", "hiring")
        prioritized = [
            email for email in emails if any(word in email.split("@", maxsplit=1)[0] for word in priority_words)
        ]
        return [*prioritized, *[email for email in emails if email not in prioritized]]

    @staticmethod
    def _linkedin_urls(page_text: str, parser: _PageParser, source_url: str) -> list[str]:
        urls = {match.group(0).rstrip(".,)") for match in _LINKEDIN_PATTERN.finditer(page_text)}
        for href, _ in parser.links:
            if "linkedin.com/" in href:
                urls.add(href)
        normalized = []
        for url in sorted(urls):
            clean = url if url.startswith("http") else f"https://{url.lstrip('/')}"
            if clean not in normalized:
                normalized.append(urljoin(source_url, clean))
        return normalized

    @staticmethod
    def _contact_type(email: str) -> str:
        local_part = email.split("@", maxsplit=1)[0]
        if any(word in local_part for word in ("career", "jobs", "talent", "recruit", "hiring")):
            return "careers_or_recruiting_email"
        if any(word in local_part for word in ("hr", "people")):
            return "hr_email"
        return "public_company_email"

    @staticmethod
    def _email_confidence(email: str, url: str) -> int:
        local_part = email.split("@", maxsplit=1)[0]
        score = 68
        if any(word in local_part for word in ("career", "jobs", "talent", "recruit", "hiring")):
            score += 20
        if any(word in local_part for word in ("hr", "people")):
            score += 12
        if any(word in url.lower() for word in ("career", "jobs", "contact")):
            score += 10
        return min(score, 95)


def _clean_text(value: str) -> str:
    return _SPACE_PATTERN.sub(" ", value).strip()
