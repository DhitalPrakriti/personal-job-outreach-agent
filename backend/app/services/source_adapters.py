"""Production-safe source adapters for manual job trackers.

These adapters intentionally do not scrape LinkedIn or Indeed. They normalize
user-provided URLs, pasted descriptions, and CSV rows into the shared
JobDiscoveryItem shape so official APIs can be added later behind the same
adapter boundary.
"""

from abc import ABC, abstractmethod
from csv import DictReader
from io import StringIO
from urllib.parse import urlparse

from app.schemas.pipeline import (
    JobDiscoveryItem,
    SourceOpportunityCreate,
    SourceTrackerCsvImportRequest,
    SourceTrackerImportRequest,
)


class SourceAdapterError(ValueError):
    """Raised when a source tracker import cannot be normalized safely."""


class SourceAdapter(ABC):
    source_name: str
    source_label: str
    allowed_hosts: tuple[str, ...] = ()

    def opportunities_from_request(self, payload: SourceTrackerImportRequest) -> list[JobDiscoveryItem]:
        return [self._item_from_opportunity(opportunity, payload) for opportunity in payload.opportunities]

    def opportunities_from_csv(self, payload: SourceTrackerCsvImportRequest) -> list[JobDiscoveryItem]:
        rows = list(DictReader(StringIO(payload.csv_rows.strip())))
        if not rows:
            raise SourceAdapterError("CSV must include a header and at least one row")
        opportunities = []
        for row in rows:
            skills = row.get("required_skills") or row.get("skills") or ""
            opportunities.append(
                SourceOpportunityCreate(
                    source_url=row.get("source_url") or row.get("url") or None,
                    company_name=row.get("company_name") or row.get("company") or "Unknown Company",
                    job_title=row.get("job_title") or row.get("title") or "Open role",
                    location=row.get("location") or None,
                    description=row.get("description") or row.get("job_description") or None,
                    required_skills=[skill.strip() for skill in skills.replace("|", ",").split(",") if skill.strip()],
                    recruiter_profile_url=row.get("recruiter_profile_url") or row.get("contact_url") or None,
                    recruiter_name=row.get("recruiter_name") or row.get("contact_name") or None,
                    contact_email=row.get("contact_email") or row.get("email") or None,
                    notes=row.get("notes") or None,
                )
            )
        return self.opportunities_from_request(
            SourceTrackerImportRequest(
                target_roles=payload.target_roles,
                target_locations=payload.target_locations,
                target_skills=payload.target_skills,
                opportunities=opportunities,
            )
        )

    def _item_from_opportunity(
        self,
        opportunity: SourceOpportunityCreate,
        payload: SourceTrackerImportRequest,
    ) -> JobDiscoveryItem:
        self._validate_url(opportunity.source_url, "source_url")
        self._validate_url(opportunity.recruiter_profile_url, "recruiter_profile_url")
        required_skills = ", ".join(opportunity.required_skills)
        role_fit = self._role_fit(opportunity, payload)
        source_links = "\n".join(
            link
            for link in (opportunity.source_url, opportunity.recruiter_profile_url)
            if link
        )
        contact_url = opportunity.recruiter_profile_url or opportunity.source_url
        return JobDiscoveryItem(
            company=opportunity.company_name,
            title=opportunity.job_title,
            location=opportunity.location,
            url=opportunity.source_url,
            description=opportunity.description,
            company_summary=(
                f"{opportunity.company_name} opportunity imported from {self.source_label}. "
                "No scraping was performed; analysis is based on user-provided source data."
            ),
            tech_stack=required_skills or None,
            role_fit=role_fit,
            source_links=source_links or None,
            contact_email=opportunity.contact_email,
            contact_name=opportunity.recruiter_name,
            contact_url=contact_url,
            notes=opportunity.notes,
            source=self.source_name,
        )

    def _validate_url(self, value: str | None, field_name: str) -> None:
        if not value:
            return
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise SourceAdapterError(f"{field_name} must be a valid http(s) URL")
        if self.allowed_hosts and not any(host in (parsed.hostname or "") for host in self.allowed_hosts):
            allowed = ", ".join(self.allowed_hosts)
            raise SourceAdapterError(f"{field_name} must be from: {allowed}")

    @abstractmethod
    def _role_fit(self, opportunity: SourceOpportunityCreate, payload: SourceTrackerImportRequest) -> str:
        raise NotImplementedError

    @staticmethod
    def _matched_parts(opportunity: SourceOpportunityCreate, payload: SourceTrackerImportRequest) -> list[str]:
        text = _text_for(opportunity)
        parts = []
        matched_roles = _matches(text, payload.target_roles)
        matched_locations = _matches(text, payload.target_locations)
        matched_skills = _matches(text, payload.target_skills)
        if matched_roles:
            parts.append(f"Matched roles: {', '.join(matched_roles)}.")
        if matched_locations:
            parts.append(f"Matched locations: {', '.join(matched_locations)}.")
        if matched_skills:
            parts.append(f"Matched skills: {', '.join(matched_skills)}.")
        if not parts:
            parts.append("Needs review against target role, location, and skill preferences.")
        return parts


class LinkedInManualAdapter(SourceAdapter):
    source_name = "LINKEDIN"
    source_label = "LinkedIn Tracker"
    allowed_hosts = ("linkedin.com",)

    def _role_fit(self, opportunity: SourceOpportunityCreate, payload: SourceTrackerImportRequest) -> str:
        parts = self._matched_parts(opportunity, payload)
        parts.append("LinkedIn source is manual URL/description tracking only; no LinkedIn automation.")
        if opportunity.recruiter_profile_url:
            parts.append("Recruiter/hiring manager profile URL tracked for manual review.")
        return " ".join(parts)


class IndeedManualAdapter(SourceAdapter):
    source_name = "INDEED"
    source_label = "Indeed Tracker"
    allowed_hosts = ("indeed.",)

    def _role_fit(self, opportunity: SourceOpportunityCreate, payload: SourceTrackerImportRequest) -> str:
        parts = self._matched_parts(opportunity, payload)
        parts.append("Indeed source is manual URL/description tracking only; no scraping was performed.")
        return " ".join(parts)


def adapter_for(source: str) -> SourceAdapter:
    normalized = source.strip().lower()
    if normalized == "linkedin":
        return LinkedInManualAdapter()
    if normalized == "indeed":
        return IndeedManualAdapter()
    raise SourceAdapterError(f"Unsupported manual source adapter: {source}")


def _text_for(opportunity: SourceOpportunityCreate) -> str:
    return " ".join(
        part
        for part in (
            opportunity.company_name,
            opportunity.job_title,
            opportunity.location,
            opportunity.description,
            " ".join(opportunity.required_skills),
            opportunity.notes,
        )
        if part
    ).lower()


def _matches(text: str, terms: list[str]) -> list[str]:
    return [term for term in terms if term and term.lower() in text]
