"""Local Google OAuth helpers for Gmail integration setup."""

from pathlib import Path
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.config import get_settings

router = APIRouter(tags=["google-oauth"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
]


@router.get("/auth/google/start")
async def start_google_oauth() -> RedirectResponse:
    """Redirect the operator to Google consent for the configured Gmail account."""
    settings = get_settings()
    _ensure_local_setup(settings.google_client_id, settings.google_client_secret)

    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_oauth_redirect_uri,
        "response_type": "code",
        "scope": " ".join(GMAIL_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
    }
    if settings.google_inbox_email:
        params["login_hint"] = settings.google_inbox_email

    return RedirectResponse(f"{GOOGLE_AUTH_URL}?{urlencode(params)}")


@router.get("/auth/google/callback")
@router.get("/oauth2callback")
async def google_oauth_callback(
    code: str | None = Query(default=None),
    error: str | None = Query(default=None),
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
    _ensure_local_setup(settings.google_client_id, settings.google_client_secret)

    token_payload = {
        "code": code,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": settings.google_oauth_redirect_uri,
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(settings.google_token_url, data=token_payload)

    if response.status_code >= 400:
        return _html_page(
            "Google token exchange failed",
            "Check that the OAuth client allows the exact redirect URI "
            f"{settings.google_oauth_redirect_uri}.",
            success=False,
        )

    tokens = response.json()
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        return _html_page(
            "No refresh token returned",
            "Google did not return a refresh token. Open /auth/google/start again "
            "and make sure you approve the consent screen. If it still happens, "
            "remove this app from Google Account access and retry.",
            success=False,
        )

    _update_env_value("GOOGLE_REFRESH_TOKEN", refresh_token)
    get_settings.cache_clear()
    return _html_page(
        "Gmail OAuth connected",
        "Refresh token saved locally. You can close this tab and refresh the dashboard readiness panel.",
        success=True,
    )


def _ensure_local_setup(client_id: str, client_secret: str) -> None:
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set in .env first.",
        )


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

