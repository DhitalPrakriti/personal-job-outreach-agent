"""System and dependency health endpoints."""

from fastapi import APIRouter, HTTPException, status

from app.core.config import get_settings
from app.db.session import check_database

router = APIRouter(prefix="/api/v1/system", tags=["system"])


@router.get("/database")
async def database_health() -> dict[str, str]:
    if not await check_database():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database health check failed",
        )
    return {"status": "ok", "database": "connected"}


@router.get("/readiness")
async def system_readiness() -> dict[str, object]:
    """Report whether external integrations are configured and enabled."""
    settings = get_settings()
    database_connected = await check_database()
    email_provider = settings.email_provider.lower()
    gmail_configured = all(
        (
            settings.google_client_id,
            settings.google_client_secret,
            settings.google_refresh_token,
            settings.google_sender_email,
        )
    )
    outlook_configured = all(
        (
            settings.microsoft_tenant_id,
            settings.microsoft_client_id,
            settings.microsoft_client_secret,
            settings.microsoft_sender_user,
        )
    )
    email_configured = gmail_configured if email_provider == "gmail" else outlook_configured
    return {
        "status": "ready" if database_connected else "degraded",
        "database": {"connected": database_connected},
        "notion": {
            "configured": bool(
                settings.notion_api_key
                and (
                    settings.notion_leads_data_source_id
                    or settings.notion_leads_database_id
                )
            ),
            "writeback_enabled": settings.notion_writeback_enabled,
        },
        "ai": {
            "enabled": settings.ai_drafting_enabled,
            "litellm_configured": bool(settings.litellm_base_url),
            "provider_key_configured": bool(settings.anthropic_api_key),
        },
        "email": {
            "provider": email_provider,
            "configured": email_configured,
            "sending_enabled": settings.email_sending_enabled,
            "reply_sync_enabled": settings.email_reply_sync_enabled,
            "sender_email": (
                settings.google_sender_email
                if email_provider == "gmail"
                else settings.microsoft_sender_user
            ),
            "inbox_email": (
                settings.google_inbox_email
                if email_provider == "gmail"
                else settings.microsoft_inbox_user
            ),
        },
        "gmail": {
            "configured": gmail_configured,
            "sender_configured": bool(settings.google_sender_email),
            "refresh_token_configured": bool(settings.google_refresh_token),
            "sender_email": settings.google_sender_email,
            "inbox_email": settings.google_inbox_email,
        },
        "outlook": {"configured": outlook_configured},
        "job_sources": {
            "remotive_configured": True,
            "remoteok_configured": True,
            "adzuna_configured": bool(settings.adzuna_app_id and settings.adzuna_app_key),
        },
        "automation": {"token_required": bool(settings.automation_api_key)},
        "safety": {
            "human_approval_required": True,
            "live_send_default": False,
        },
    }
