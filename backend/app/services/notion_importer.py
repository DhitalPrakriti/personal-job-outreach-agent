"""Read-only Notion importer for contact source data."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import get_settings
from app.schemas.pipeline import LeadCreate


class NotionConfigurationError(RuntimeError):
    """Raised when Notion import settings are incomplete."""


class NotionImportError(RuntimeError):
    """Raised when Notion returns an unexpected response."""


class NotionLeadImporter:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def fetch_leads(
        self,
        database_id: str | None = None,
        data_source_id: str | None = None,
        max_pages: int = 100,
    ) -> list[LeadCreate]:
        resolved_data_source_id = await self._resolve_data_source_id(
            database_id=database_id,
            data_source_id=data_source_id,
        )
        pages = await self._query_data_source(resolved_data_source_id, max_pages=max_pages)
        leads: list[LeadCreate] = []
        for page in pages:
            lead = self._page_to_lead(page)
            if lead is not None:
                leads.append(lead)
        return leads

    async def update_lead_page(
        self,
        page_id: str,
        outreach_status: str | None = None,
        note: str | None = None,
    ) -> dict[str, Any]:
        page = await self._request("GET", f"/pages/{page_id}")
        current_properties = page.get("properties") or {}
        if not isinstance(current_properties, dict):
            raise NotionImportError("Notion page did not include editable properties.")

        properties: dict[str, Any] = {}
        skipped: list[str] = []

        if outreach_status:
            status_update = self._status_property_update(
                current_properties,
                self.settings.notion_outreach_status_property_name,
                outreach_status,
            )
            if status_update is None:
                skipped.append(self.settings.notion_outreach_status_property_name)
            else:
                property_name, value = status_update
                properties[property_name] = value

        if note:
            note_update = self._note_property_update(
                current_properties,
                self.settings.notion_notes_property_name,
                note,
            )
            if note_update is None:
                skipped.append(self.settings.notion_notes_property_name)
            else:
                property_name, value = note_update
                properties[property_name] = value

        if not properties:
            return {"updated": False, "skipped": skipped}

        await self._request("PATCH", f"/pages/{page_id}", json={"properties": properties})
        return {"updated": True, "skipped": skipped}

    async def _resolve_data_source_id(
        self,
        database_id: str | None,
        data_source_id: str | None,
    ) -> str:
        configured_data_source_id = data_source_id or self.settings.notion_leads_data_source_id
        if configured_data_source_id:
            return configured_data_source_id

        configured_database_id = database_id or self.settings.notion_leads_database_id
        if not self.settings.notion_api_key or not configured_database_id:
            raise NotionConfigurationError(
                "Set NOTION_API_KEY and either NOTION_LEADS_DATA_SOURCE_ID or "
                "NOTION_LEADS_DATABASE_ID before importing Notion leads."
            )

        database = await self._request("GET", f"/databases/{configured_database_id}")
        data_sources = database.get("data_sources") or []
        if data_sources:
            first_data_source = data_sources[0]
            if isinstance(first_data_source, dict) and first_data_source.get("id"):
                return str(first_data_source["id"])

        # Some Notion workspaces still expose the queried object with the same ID.
        return configured_database_id

    async def _query_data_source(self, data_source_id: str, max_pages: int) -> list[dict[str, Any]]:
        pages: list[dict[str, Any]] = []
        cursor: str | None = None

        while len(pages) < max_pages:
            page_size = min(100, max_pages - len(pages))
            body: dict[str, Any] = {"page_size": page_size}
            if cursor:
                body["start_cursor"] = cursor

            response = await self._request("POST", f"/data_sources/{data_source_id}/query", json=body)
            pages.extend(
                page for page in response.get("results", []) if isinstance(page, dict)
            )
            if not response.get("has_more") or not response.get("next_cursor"):
                break
            cursor = str(response["next_cursor"])

        return pages[:max_pages]

    async def _request(
        self,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.settings.notion_api_key:
            raise NotionConfigurationError("Set NOTION_API_KEY before importing Notion leads.")

        headers = {
            "Authorization": f"Bearer {self.settings.notion_api_key}",
            "Notion-Version": self.settings.notion_version,
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(base_url="https://api.notion.com/v1", timeout=30) as client:
            response = await client.request(method, path, headers=headers, json=json)

        if response.status_code >= 400:
            raise NotionImportError(
                f"Notion request failed with status {response.status_code}: {response.text}"
            )
        return response.json()

    @classmethod
    def _page_to_lead(cls, page: dict[str, Any]) -> LeadCreate | None:
        properties = page.get("properties")
        if not isinstance(properties, dict):
            return None

        name = cls._property_text(properties, "Name")
        first_name = cls._property_text(properties, "First Name")
        last_name = cls._property_text(properties, "Last Name")
        if not first_name:
            first_name, last_name_from_name = cls._split_name(name)
            last_name = last_name or last_name_from_name

        if not first_name:
            return None

        return LeadCreate(
            email=cls._property_text(properties, "Email", "Email Address") or None,
            first_name=first_name,
            last_name=last_name,
            company=cls._property_text(properties, "Company", "company") or None,
            title=cls._property_text(properties, "Title") or None,
            source="notion_contact_source",
            notes=cls._property_text(properties, "Notes", "notes") or None,
            notion_page_id=str(page.get("id") or ""),
            linkedin_url=cls._property_text(properties, "LinkedIn URL", "LinkedIn") or None,
            lead_grade=cls._property_text(properties, "Lead Grade", "Lead Gr...") or None,
            outreach_status=cls._property_text(properties, "Outreach Status") or None,
            suggested_first_message=cls._property_text(properties, "Suggested First Message") or None,
        )

    @classmethod
    def _property_text(cls, properties: dict[str, Any], *names: str) -> str:
        for name in names:
            property_value = cls._find_property(properties, name)
            if property_value:
                value = cls._extract_text(property_value)
                if value:
                    return value
        return ""

    @staticmethod
    def _find_property(properties: dict[str, Any], name: str) -> dict[str, Any] | None:
        found = NotionLeadImporter._find_property_entry(properties, name)
        return found[1] if found else None

    @staticmethod
    def _find_property_entry(
        properties: dict[str, Any],
        name: str,
    ) -> tuple[str, dict[str, Any]] | None:
        if name in properties and isinstance(properties[name], dict):
            return name, properties[name]

        lowered = name.lower()
        for property_name, property_value in properties.items():
            if property_name.lower() == lowered and isinstance(property_value, dict):
                return property_name, property_value
        return None

    @classmethod
    def _status_property_update(
        cls,
        properties: dict[str, Any],
        name: str,
        status_name: str,
    ) -> tuple[str, dict[str, Any]] | None:
        found = cls._find_property_entry(properties, name)
        if found is None:
            return None

        property_name, property_value = found
        property_type = property_value.get("type")
        if property_type == "status":
            return property_name, {"status": {"name": status_name}}
        if property_type == "select":
            return property_name, {"select": {"name": status_name}}
        return None

    @classmethod
    def _note_property_update(
        cls,
        properties: dict[str, Any],
        name: str,
        note: str,
    ) -> tuple[str, dict[str, Any]] | None:
        found = cls._find_property_entry(properties, name)
        if found is None:
            return None

        property_name, property_value = found
        if property_value.get("type") != "rich_text":
            return None

        existing_note = cls._extract_text(property_value)
        updated_note = f"{existing_note}\n\n{note}".strip() if existing_note else note
        # Notion rich text objects have a per-object content limit, so keep the latest context.
        updated_note = updated_note[-1900:]
        return property_name, {"rich_text": [{"text": {"content": updated_note}}]}

    @classmethod
    def _extract_text(cls, property_value: dict[str, Any]) -> str:
        property_type = property_value.get("type")
        if property_type in {"title", "rich_text"}:
            return cls._join_rich_text(property_value.get(property_type) or [])
        if property_type in {"select", "status"}:
            option = property_value.get(property_type) or {}
            return str(option.get("name") or "")
        if property_type in {"url", "email", "phone_number"}:
            return str(property_value.get(property_type) or "")
        if property_type == "number" and property_value.get("number") is not None:
            return str(property_value["number"])
        return ""

    @staticmethod
    def _join_rich_text(items: list[dict[str, Any]]) -> str:
        return "".join(str(item.get("plain_text") or "") for item in items).strip()

    @staticmethod
    def _split_name(name: str) -> tuple[str, str | None]:
        parts = name.split()
        if not parts:
            return "", None
        if len(parts) == 1:
            return parts[0], None
        return parts[0], " ".join(parts[1:])
