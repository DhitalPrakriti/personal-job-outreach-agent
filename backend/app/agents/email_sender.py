"""Email sender with dry-run safety."""

import base64
from dataclasses import dataclass
from email.message import EmailMessage

import httpx

from app.core.config import get_settings
from app.services.gmail_account_service import GmailAccountCredentials


class EmailSendError(RuntimeError):
    pass


@dataclass(frozen=True)
class EmailSendResult:
    provider: str
    message_id: str | None
    thread_id: str | None
    dry_run: bool


class EmailSenderAgent:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def send(
        self,
        to_email: str,
        subject: str,
        body: str,
        gmail_account: GmailAccountCredentials | None = None,
        *,
        force_dry_run: bool = False,
    ) -> EmailSendResult:
        if force_dry_run or not self.settings.email_sending_enabled:
            return EmailSendResult(
                provider=(
                    f"gmail_dry_run:{gmail_account.email}"
                    if gmail_account
                    else f"{self.settings.email_provider.lower()}_dry_run"
                ),
                message_id=None,
                thread_id=None,
                dry_run=True,
            )
        provider = self.settings.email_provider.lower()
        if provider == "gmail":
            return await self._send_gmail(to_email, subject, body, gmail_account)
        if provider != "outlook":
            raise EmailSendError(f"Unsupported live email provider: {self.settings.email_provider}")
        return await self._send_outlook(to_email, subject, body)

    async def _send_gmail(
        self,
        to_email: str,
        subject: str,
        body: str,
        gmail_account: GmailAccountCredentials | None = None,
    ) -> EmailSendResult:
        self._validate_gmail_config(gmail_account)
        token = await self._gmail_access_token(gmail_account)
        message = EmailMessage()
        message["To"] = to_email
        message["From"] = gmail_account.email if gmail_account else self.settings.google_sender_email
        message["Subject"] = subject
        message.set_content(body)
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode().rstrip("=")
        url = f"{self.settings.gmail_api_base_url.rstrip('/')}/users/me/messages/send"
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    url,
                    headers={"Authorization": f"Bearer {token}"},
                    json={"raw": raw},
                )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise EmailSendError("Gmail send request failed.") from exc
        return EmailSendResult(
            provider="gmail",
            message_id=str(payload.get("id") or ""),
            thread_id=str(payload.get("threadId") or "") or None,
            dry_run=False,
        )

    async def _send_outlook(self, to_email: str, subject: str, body: str) -> EmailSendResult:
        self._validate_graph_config()
        token = await self._graph_access_token()
        sender = self.settings.microsoft_sender_user
        url = f"{self.settings.microsoft_graph_base_url.rstrip('/')}/v1.0/users/{sender}/sendMail"
        payload = {
            "message": {
                "subject": subject,
                "body": {"contentType": "Text", "content": body},
                "toRecipients": [{"emailAddress": {"address": to_email}}],
            },
            "saveToSentItems": True,
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    url,
                    headers={"Authorization": f"Bearer {token}"},
                    json=payload,
                )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise EmailSendError("Microsoft Graph sendMail request failed.") from exc
        message_id = response.headers.get("request-id") or response.headers.get("client-request-id")
        return EmailSendResult(provider="outlook", message_id=message_id, thread_id=message_id, dry_run=False)

    def _validate_gmail_config(self, gmail_account: GmailAccountCredentials | None = None) -> None:
        required = (
            self.settings.google_client_id,
            self.settings.google_client_secret,
            gmail_account.refresh_token if gmail_account else self.settings.google_refresh_token,
            gmail_account.email if gmail_account else self.settings.google_sender_email,
        )
        if not all(required):
            raise EmailSendError("Gmail sending credentials are incomplete.")

    async def _gmail_access_token(self, gmail_account: GmailAccountCredentials | None = None) -> str:
        data = {
            "client_id": self.settings.google_client_id,
            "client_secret": self.settings.google_client_secret,
            "refresh_token": gmail_account.refresh_token if gmail_account else self.settings.google_refresh_token,
            "grant_type": "refresh_token",
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(self.settings.google_token_url, data=data)
            response.raise_for_status()
            return str(response.json()["access_token"])
        except httpx.HTTPStatusError as exc:
            reason = self._google_error_reason(exc.response)
            raise EmailSendError(f"Gmail authentication failed: {reason}") from exc
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise EmailSendError("Gmail authentication failed: token refresh request failed.") from exc

    def _google_error_reason(self, response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return f"Google token endpoint returned HTTP {response.status_code}."
        error = str(payload.get("error") or f"HTTP {response.status_code}")
        description = str(payload.get("error_description") or "").strip()
        if description:
            return f"{error} - {description}"
        return error

    def _validate_graph_config(self) -> None:
        required = (
            self.settings.microsoft_tenant_id,
            self.settings.microsoft_client_id,
            self.settings.microsoft_client_secret,
            self.settings.microsoft_sender_user,
        )
        if not all(required):
            raise EmailSendError("Microsoft Graph sending credentials are incomplete.")

    async def _graph_access_token(self) -> str:
        token_url = (
            "https://login.microsoftonline.com/"
            f"{self.settings.microsoft_tenant_id}/oauth2/v2.0/token"
        )
        data = {
            "client_id": self.settings.microsoft_client_id,
            "client_secret": self.settings.microsoft_client_secret,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(token_url, data=data)
            response.raise_for_status()
            return str(response.json()["access_token"])
        except (httpx.HTTPError, KeyError) as exc:
            raise EmailSendError("Microsoft Graph authentication failed.") from exc
