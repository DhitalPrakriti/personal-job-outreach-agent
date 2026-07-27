"""Lightweight API authentication helpers."""

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Header, HTTPException, Request, status
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def verify_automation_token(
    x_automation_token: str | None = Header(default=None, alias="X-Automation-Token"),
) -> None:
    """Require the configured token for machine-triggered automation routes."""
    expected_token = get_settings().automation_api_key
    if not expected_token:
        return
    if x_automation_token != expected_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid automation token",
        )


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def session_secret() -> str:
    settings = get_settings()
    return settings.app_auth_secret_key or settings.automation_api_key


def create_session_token(user_id: str, email: str) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": user_id,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.app_session_ttl_minutes)).timestamp()),
        "scope": "app_session",
    }
    secret = session_secret()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="APP_AUTH_SECRET_KEY must be set when app auth is enabled.",
        )
    return jwt.encode(payload, secret, algorithm="HS256")


def verify_session_token(token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    secret = session_secret()
    if not secret:
        return None
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except JWTError:
        return None
    if payload.get("scope") != "app_session":
        return None
    return payload


def current_session(request: Request) -> dict[str, Any] | None:
    settings = get_settings()
    token = request.cookies.get(settings.app_session_cookie_name)
    return verify_session_token(token)
