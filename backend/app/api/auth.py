"""Lightweight API authentication helpers."""

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


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
