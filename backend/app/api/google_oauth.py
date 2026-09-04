"""Local Google OAuth helpers for Gmail integration setup."""

from pathlib import Path
from uuid import UUID
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import GmailAccountModel
from app.db.session import get_db
from app.services.gmail_account_service import GmailAccountService

router = APIRouter(tags=["google-oauth"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
]


class GmailAccountRead(BaseModel):
    id: UUID
    email: str
    display_name: str | None
    purpose: str
    is_default: bool
    send_enabled: bool
    reply_sync_enabled: bool
    status: str

    @classmethod
    def from_model(cls, account: GmailAccountModel) -> "GmailAccountRead":
        return cls(
            id=account.id,
            email=account.email,
            display_name=account.display_name,
            purpose=account.purpose,
            is_default=account.is_default,
            send_enabled=account.send_enabled,
            reply_sync_enabled=account.reply_sync_enabled,
            status=account.status,
        )


class GmailAccountUpdate(BaseModel):
    purpose: str | None = None
    send_enabled: bool | None = None
    reply_sync_enabled: bool | None = None
    status: str | None = None


@router.get("/auth/google/start")
async def start_google_oauth(
    request: Request,
    email: str | None = Query(default=None),
) -> RedirectResponse:
    """Redirect the operator to Google consent for a Gmail account."""
    settings = get_settings()
    client_id, client_secret = _oauth_credentials(settings.google_client_id, settings.google_client_secret)
    redirect_uri = _oauth_redirect_uri(settings.google_oauth_redirect_uri, request)

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(GMAIL_SCOPES),
        "access_type": "offline",
        "prompt": "consent select_account",
        "include_granted_scopes": "true",
    }
    login_hint = email or settings.app_allowed_email
    if login_hint:
        params["login_hint"] = login_hint.lower().strip()

    return RedirectResponse(f"{GOOGLE_AUTH_URL}?{urlencode(params)}")


@router.get("/auth/google/callback")
@router.get("/oauth2callback")
async def google_oauth_callback(
    request: Request,
    code: str | None = Query(default=None),
    error: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Exchange a Google OAuth code for a refresh token and save it locally."""
    if error:
        return _html_page(
            "Google OAuth was not completed",
            f"Google returned this error: {error}",
            success=False,
        )
    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Google OAuth code.",
        )

    settings = get_settings()
    client_id, client_secret = _oauth_credentials(settings.google_client_id, settings.google_client_secret)
    redirect_uri = _oauth_redirect_uri(settings.google_oauth_redirect_uri, request)

    token_payload = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(settings.google_token_url, data=token_payload)
    except httpx.HTTPError as exc:
        return _html_page(
            "Google token exchange failed",
            "Google OAuth succeeded, but the backend could not reach Google's token service. "
            f"Backend network error: {type(exc).__name__}: {exc}",
            success=False,
        )

    if response.status_code >= 400:
        return _html_page(
            "Google token exchange failed",
            "Check that the OAuth client allows the exact redirect URI "
            f"{redirect_uri}.",
            success=False,
        )

    tokens = response.json()
    refresh_token = tokens.get("refresh_token")
    access_token = tokens.get("access_token")
    if not refresh_token:
        return _html_page(
            "No refresh token returned",
            "Google did not return a refresh token. Open /auth/google/start again "
            "and make sure you approve the consent screen. If it still happens, "
            "remove this app from Google Account access and retry.",
            success=False,
        )

    email = await _gmail_profile_email(str(access_token or ""))
    if not email:
        return _html_page(
            "Gmail profile lookup failed",
            "Google OAuth succeeded, but the app could not confirm which Gmail account was connected.",
            success=False,
        )

    try:
        should_make_default = (
            bool(settings.app_allowed_email)
            and email.lower().strip() == settings.app_allowed_email.lower().strip()
        )
        account = await GmailAccountService(db, settings).upsert_connected_account(
            email=email,
            refresh_token=refresh_token,
            scopes=GMAIL_SCOPES,
            make_default=should_make_default if settings.app_allowed_email else None,
        )
        if should_make_default:
            _update_env_value_if_present("GOOGLE_REFRESH_TOKEN", refresh_token)
            _update_env_value_if_present("GOOGLE_SENDER_EMAIL", account.email)
            _update_env_value_if_present("GOOGLE_INBOX_EMAIL", account.email)
        elif not settings.google_sender_email and not settings.google_inbox_email:
            _update_env_value_if_present("GOOGLE_REFRESH_TOKEN", refresh_token)
            _update_env_value_if_present("GOOGLE_SENDER_EMAIL", account.email)
            _update_env_value_if_present("GOOGLE_INBOX_EMAIL", account.email)
        get_settings.cache_clear()
    except Exception as exc:
        return _html_page(
            "Gmail account save failed",
            "Google OAuth succeeded, but the local app could not save the Gmail account. "
            f"Backend error: {type(exc).__name__}: {exc}",
            success=False,
        )
    return _html_page(
        "Gmail OAuth connected",
        f"{account.email} was saved as a connected Gmail account. You can close this tab and refresh Settings.",
        success=True,
    )


@router.get("/api/v1/gmail/accounts")
async def list_gmail_accounts(db: AsyncSession = Depends(get_db)) -> list[GmailAccountRead]:
    accounts = await GmailAccountService(db).list_accounts()
    return [GmailAccountRead.from_model(account) for account in accounts]


@router.post("/api/v1/gmail/accounts/{account_id}/default")
async def set_default_gmail_account(account_id: UUID, db: AsyncSession = Depends(get_db)) -> GmailAccountRead:
    account = await GmailAccountService(db).set_default(account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gmail account not found.")
    return GmailAccountRead.from_model(account)


@router.patch("/api/v1/gmail/accounts/{account_id}")
async def update_gmail_account(
    account_id: UUID,
    payload: GmailAccountUpdate,
    db: AsyncSession = Depends(get_db),
) -> GmailAccountRead:
    account = await GmailAccountService(db).update_account(
        account_id,
        **payload.model_dump(exclude_unset=True),
    )
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gmail account not found.")
    return GmailAccountRead.from_model(account)


@router.delete("/api/v1/gmail/accounts/{account_id}")
async def delete_gmail_account(account_id: UUID, db: AsyncSession = Depends(get_db)) -> GmailAccountRead:
    try:
        account = await GmailAccountService(db).delete_account(account_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gmail account not found.")
    return GmailAccountRead.from_model(account)


def _oauth_credentials(client_id: str, client_secret: str) -> tuple[str, str]:
    normalized_client_id = _clean_oauth_value(client_id)
    normalized_client_secret = _clean_oauth_value(client_secret)
    _ensure_local_setup(normalized_client_id, normalized_client_secret)
    return normalized_client_id, normalized_client_secret


def _clean_oauth_value(value: str) -> str:
    return value.strip().lstrip("\ufeff")


def _ensure_local_setup(client_id: str, client_secret: str) -> None:
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set in .env first.",
        )


def _oauth_redirect_uri(configured_uri: str, request: Request) -> str:
    configured = (configured_uri or "").strip()
    forwarded_proto = request.headers.get("x-forwarded-proto")
    forwarded_host = request.headers.get("x-forwarded-host")
    host = forwarded_host or request.headers.get("host") or request.url.netloc
    scheme = forwarded_proto or request.url.scheme
    dynamic_uri = f"{scheme}://{host}/auth/google/callback"

    if configured and "localhost" not in configured and "127.0.0.1" not in configured:
        return configured
    return dynamic_uri


def _update_env_value(key: str, value: str) -> None:
    env_path = Path(".env")
    if not env_path.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=".env file was not found.",
        )

    lines = env_path.read_text(encoding="utf-8").splitlines()
    updated = False
    for index, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[index] = f"{key}={value}"
            updated = True
            break
    if not updated:
        lines.append(f"{key}={value}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _update_env_value_if_present(key: str, value: str) -> None:
    if Path(".env").exists():
        _update_env_value(key, value)


async def _gmail_profile_email(access_token: str) -> str | None:
    if not access_token:
        return None
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                "https://gmail.googleapis.com/gmail/v1/users/me/profile",
                headers={"Authorization": f"Bearer {access_token}"},
            )
        response.raise_for_status()
        return str(response.json().get("emailAddress") or "").lower() or None
    except (httpx.HTTPError, ValueError):
        return None


def _html_page(title: str, message: str, success: bool) -> HTMLResponse:
    color = "#0f766e" if success else "#b91c1c"
    html = f"""
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <title>{title}</title>
        <style>
          body {{
            font-family: Arial, sans-serif;
            margin: 0;
            min-height: 100vh;
            display: grid;
            place-items: center;
            background: #f8fafc;
            color: #0f172a;
          }}
          main {{
            max-width: 560px;
            background: white;
            border: 1px solid #d8e0ea;
            border-radius: 8px;
            padding: 32px;
            box-shadow: 0 12px 30px rgba(15, 23, 42, 0.08);
          }}
          h1 {{ color: {color}; margin-top: 0; }}
          p {{ line-height: 1.5; }}
          code {{ background: #eef2f7; padding: 2px 6px; border-radius: 4px; }}
        </style>
      </head>
      <body>
        <main>
          <h1>{title}</h1>
          <p>{message}</p>
          <p>Next: open <code>http://localhost:3000</code> and check readiness.</p>
        </main>
      </body>
    </html>
    """
    return HTMLResponse(html)

