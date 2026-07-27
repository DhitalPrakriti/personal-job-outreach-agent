"""System and dependency health endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import check_database
from app.db.session import get_db
from app.services.gmail_account_service import GmailAccountService

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
async def system_readiness(db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    """Report whether external integrations are configured and enabled."""
    settings = get_settings()
    database_connected = await check_database()
    email_provider = settings.email_provider.lower()
    gmail_service = GmailAccountService(db, settings)
    gmail_accounts = await gmail_service.list_accounts()
    default_gmail_account = next(
        (account for account in gmail_accounts if account.is_default),
        gmail_accounts[0] if gmail_accounts else None,
    )
    active_gmail_account = gmail_service.select_effective_account(gmail_accounts)
    expected_gmail_email = gmail_service.preferred_email
    env_sender_email = (settings.google_sender_email or "").lower().strip()
    env_gmail_allowed = not expected_gmail_email or env_sender_email == expected_gmail_email
    env_gmail_configured = all(
        (
            settings.google_client_id,
            settings.google_client_secret,
            settings.google_refresh_token,
            env_sender_email,
            env_gmail_allowed,
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
    gmail_account_configured = bool(active_gmail_account)
    gmail_configured = env_gmail_configured or gmail_account_configured
    email_configured = gmail_configured if email_provider == "gmail" else outlook_configured
    gmail_sender_email = active_gmail_account.email if active_gmail_account else env_sender_email if env_gmail_configured else ""
    gmail_inbox_email = (
        active_gmail_account.email
        if active_gmail_account
        else (settings.google_inbox_email or env_sender_email).lower().strip()
        if env_gmail_configured
        else ""
    )
    resolved_primary_model = settings.primary_model.lower()
    gateway_key_configured = bool(settings.llm_api_key)
    gemini_key_configured = bool(settings.gemini_api_key)
    openai_key_configured = bool(settings.openai_api_key)
    anthropic_key_configured = bool(settings.anthropic_api_key)
    if "gemini" in resolved_primary_model:
        primary_model_key_configured = gateway_key_configured or gemini_key_configured
        provider_label = "gemini"
    elif "openai" in resolved_primary_model or resolved_primary_model.startswith("gpt-"):
        primary_model_key_configured = gateway_key_configured or openai_key_configured
        provider_label = "openai"
    elif "anthropic" in resolved_primary_model or "claude" in resolved_primary_model:
        primary_model_key_configured = gateway_key_configured or anthropic_key_configured
        provider_label = "anthropic"
    elif "local-" in resolved_primary_model or "ollama" in resolved_primary_model:
        primary_model_key_configured = True
        provider_label = "local"
    else:
        primary_model_key_configured = (
            gateway_key_configured
            or gemini_key_configured
            or openai_key_configured
            or anthropic_key_configured
        )
        provider_label = settings.llm_provider or "auto"
    return {
        "status": "ready" if database_connected else "degraded",
        "database": {"connected": database_connected},
        "ai": {
            "enabled": settings.ai_drafting_enabled,
            "litellm_configured": bool(settings.litellm_base_url),
            "provider": provider_label,
            "provider_key_configured": primary_model_key_configured,
            "gateway_key_configured": gateway_key_configured,
            "gemini_key_configured": gemini_key_configured,
            "openai_key_configured": openai_key_configured,
            "anthropic_key_configured": anthropic_key_configured,
            "primary_model": settings.primary_model,
            "fast_model": settings.fast_model,
            "monthly_budget_cad": settings.monthly_llm_budget_cad,
            "monthly_budget_usd": settings.monthly_llm_budget_usd,
            "max_llm_calls_per_day": settings.max_llm_calls_per_day,
            "max_ai_drafts_per_run": settings.max_ai_drafts_per_run,
            "max_followups_per_run": settings.max_followups_per_run,
        },
        "email": {
            "provider": email_provider,
            "configured": email_configured,
            "sending_enabled": settings.email_sending_enabled,
            "reply_sync_enabled": settings.email_reply_sync_enabled,
            "sender_email": (
                gmail_sender_email
                if email_provider == "gmail"
                else settings.microsoft_sender_user
            ),
            "inbox_email": (
                gmail_inbox_email
                if email_provider == "gmail"
                else settings.microsoft_inbox_user
            ),
        },
        "gmail": {
            "configured": gmail_configured,
            "sender_configured": bool(gmail_sender_email),
            "refresh_token_configured": bool(active_gmail_account or (settings.google_refresh_token and env_gmail_allowed)),
            "sender_email": gmail_sender_email,
            "inbox_email": gmail_inbox_email,
            "connected_accounts": len(gmail_accounts),
            "default_account_email": default_gmail_account.email if default_gmail_account else None,
            "active_account_email": active_gmail_account.email if active_gmail_account else None,
            "expected_account_email": expected_gmail_email or None,
            "expected_account_connected": bool(
                expected_gmail_email
                and any(account.email == expected_gmail_email for account in gmail_accounts)
            ),
            "default_matches_expected": bool(
                expected_gmail_email
                and default_gmail_account
                and default_gmail_account.email == expected_gmail_email
            ),
        },
        "outlook": {"configured": outlook_configured},
        "job_sources": {
            "remotive_configured": True,
            "remoteok_configured": True,
            "adzuna_configured": bool(settings.adzuna_app_id and settings.adzuna_app_key),
            "max_jobs_per_source": settings.max_jobs_per_source,
            "max_jobs_per_search_run": settings.max_jobs_per_search_run,
        },
        "automation": {"token_required": bool(settings.automation_api_key)},
        "access": {
            "auth_enabled": settings.app_auth_enabled,
            "signup_enabled": settings.app_signup_enabled,
            "signup_requires_invite": bool(settings.app_signup_invite_code),
            "allowed_email_set": bool(settings.app_allowed_email),
        },
        "safety": {
            "human_approval_required": True,
            "live_send_default": False,
            "max_pipeline_batch_size": settings.max_pipeline_batch_size,
        },
    }
