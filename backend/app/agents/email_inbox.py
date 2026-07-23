"""Email inbox reader."""

import base64
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx

from app.agents.email_sender import EmailSendError, EmailSenderAgent
from app.core.config import get_settings


class EmailInboxError(RuntimeError):
    pass


@dataclass(frozen=True)
class InboxMessage:
    provider_message_id: str
    provider_thread_id: str | None
    from_email: str
    subject: str
    body: str
    received_at: datetime | None


class EmailInboxAgent:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def fetch_recent(self) -> list[InboxMessage]:
        if not self.settings.email_reply_sync_enabled:
            return []
        provider = self.settings.email_provider.lower()
        if provider == "gmail":
            return await self._fetch_gmail_recent()
        if provider != "outlook":
            raise EmailInboxError(f"Unsupported reply sync provider: {self.settings.email_provider}")
        return await self._fetch_outlook_recent()

    async def _fetch_gmail_recent(self) -> list[InboxMessage]:
        inbox = self.settings.google_inbox_email or self.settings.google_sender_email
        if not inbox:
            raise EmailInboxError("Gmail inbox user is not configured.")
        try:
            token = await EmailSenderAgent()._gmail_access_token()
        except EmailSendError as exc:
            raise EmailInboxError(str(exc)) from exc

        after_unix = int(
            (datetime.now(UTC) - timedelta(hours=self.settings.email_reply_lookback_hours)).timestamp()
        )
        params = {
            "maxResults": str(self.settings.email_reply_max_messages),
            "q": f"in:inbox after:{after_unix}",
        }
        base_url = self.settings.gmail_api_base_url.rstrip("/")
        headers = {"Authorization": f"Bearer {token}"}
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(f"{base_url}/users/me/messages", params=params, headers=headers)
                response.raise_for_status()
                message_refs = response.json().get("messages", [])
                messages: list[InboxMessage] = []
                for item in message_refs:
                    message_id = str(item.get("id") or "")
                    if not message_id:
                        continue
                    detail_response = await client.get(
                        f"{base_url}/users/me/messages/{message_id}",
                        params={"format": "full"},
                        headers=headers,
                    )
                    detail_response.raise_for_status()
                    parsed = self._parse_gmail_message(detail_response.json())
                    if parsed:
                        messages.append(parsed)
        except (httpx.HTTPError, ValueError) as exc:
            raise EmailInboxError("Gmail inbox request failed.") from exc
        return messages

    def _parse_gmail_message(self, payload: dict) -> InboxMessage | None:
        message_id = str(payload.get("id") or "")
        headers = {
            str(item.get("name") or "").lower(): str(item.get("value") or "")
            for item in ((payload.get("payload") or {}).get("headers") or [])
        }
        from_email = self._extract_email(headers.get("from", ""))
        if not message_id or not from_email:
            return None
        received_at = None
        if payload.get("internalDate"):
            received_at = datetime.fromtimestamp(int(payload["internalDate"]) / 1000, tz=UTC)
        return InboxMessage(
            provider_message_id=message_id,
            provider_thread_id=str(payload.get("threadId") or "") or None,
            from_email=from_email,
            subject=headers.get("subject", ""),
            body=self._gmail_body(payload.get("payload") or {}),
            received_at=received_at,
        )

    def _gmail_body(self, payload: dict) -> str:
        body_data = (payload.get("body") or {}).get("data")
        if body_data:
            return self._decode_gmail_body(str(body_data))
        for part in payload.get("parts") or []:
            mime_type = str(part.get("mimeType") or "")
            if mime_type == "text/plain":
                data = ((part.get("body") or {}).get("data") or "")
                return self._decode_gmail_body(str(data))
        for part in payload.get("parts") or []:
            mime_type = str(part.get("mimeType") or "")
            if mime_type == "text/html":
                data = ((part.get("body") or {}).get("data") or "")
                html = self._decode_gmail_body(str(data))
                return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()
        return ""

    def _decode_gmail_body(self, data: str) -> str:
        padding = "=" * (-len(data) % 4)
        return base64.urlsafe_b64decode(f"{data}{padding}").decode("utf-8", errors="replace")

    def _extract_email(self, value: str) -> str:
        match = re.search(r"<([^>]+)>", value)
        return (match.group(1) if match else value).strip()

    async def _fetch_outlook_recent(self) -> list[InboxMessage]:
        inbox = self.settings.microsoft_inbox_user or self.settings.microsoft_sender_user
        if not inbox:
            raise EmailInboxError("Microsoft inbox user is not configured.")
        try:
            token = await EmailSenderAgent()._graph_access_token()
        except EmailSendError as exc:
            raise EmailInboxError(str(exc)) from exc

        since = datetime.now(UTC) - timedelta(hours=self.settings.email_reply_lookback_hours)
        params = {
            "$top": str(self.settings.email_reply_max_messages),
            "$select": "id,subject,from,body,receivedDateTime",
            "$orderby": "receivedDateTime desc",
            "$filter": f"receivedDateTime ge {since.isoformat().replace('+00:00', 'Z')}",
        }
        url = f"{self.settings.microsoft_graph_base_url.rstrip('/')}/v1.0/users/{inbox}/mailFolders/inbox/messages"
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url, params=params, headers={"Authorization": f"Bearer {token}"})
            response.raise_for_status()
            values = response.json().get("value", [])
        except (httpx.HTTPError, ValueError) as exc:
            raise EmailInboxError("Microsoft Graph inbox request failed.") from exc

        messages: list[InboxMessage] = []
        for item in values:
            address = (((item.get("from") or {}).get("emailAddress") or {}).get("address") or "").strip()
            if not address or not item.get("id"):
                continue
            body_data = item.get("body") or {}
            body = str(body_data.get("content") or "")
            if str(body_data.get("contentType") or "").lower() == "html":
                body = re.sub(r"<[^>]+>", " ", body)
                body = re.sub(r"\s+", " ", body).strip()
            received_at = None
            if item.get("receivedDateTime"):
                received_at = datetime.fromisoformat(str(item["receivedDateTime"]).replace("Z", "+00:00"))
            messages.append(
                InboxMessage(
                    provider_message_id=str(item["id"]),
                    provider_thread_id=str(item["id"]),
                    from_email=address,
                    subject=str(item.get("subject") or ""),
                    body=body,
                    received_at=received_at,
                )
            )
        return messages
