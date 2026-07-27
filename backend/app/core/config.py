"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    automation_api_key: str = ""
    app_auth_enabled: bool = False
    app_auth_secret_key: str = ""
    app_signup_enabled: bool = False
    app_signup_invite_code: str = ""
    app_allowed_email: str = ""
    app_session_cookie_name: str = "personal_outreach_session"
    app_session_ttl_minutes: int = 720

    # Database
    database_url: str = "postgresql+asyncpg://agent:changeme@localhost:5432/email_agent"

    # LLM
    litellm_base_url: str = "http://localhost:4000"
    litellm_master_key: str = ""
    llm_provider: str = "gemini"
    llm_api_key: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""
    primary_model: str = "gemini-flash"
    fast_model: str = "gemini-flash-lite"
    monthly_llm_budget_cad: float = 20.0
    monthly_llm_budget_usd: float = 14.0
    ai_drafting_enabled: bool = False
    max_jobs_per_source: int = 10
    max_jobs_per_search_run: int = 30
    max_llm_calls_per_day: int = 50
    max_ai_drafts_per_run: int = 5
    max_followups_per_run: int = 5
    max_pipeline_batch_size: int = 10

    # Job discovery
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    adzuna_country: str = "ca"

    # Email sending and reply sync
    email_sending_enabled: bool = False
    email_provider: str = "gmail"
    microsoft_tenant_id: str = ""
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    microsoft_sender_user: str = ""
    microsoft_inbox_user: str = ""
    microsoft_graph_base_url: str = "https://graph.microsoft.com"
    google_client_id: str = ""
    google_client_secret: str = ""
    google_refresh_token: str = ""
    google_sender_email: str = ""
    google_inbox_email: str = ""
    google_token_url: str = "https://oauth2.googleapis.com/token"
    gmail_api_base_url: str = "https://gmail.googleapis.com/gmail/v1"
    google_oauth_redirect_uri: str = "http://localhost:8001/auth/google/callback"
    gmail_token_encryption_key: str = ""
    email_reply_sync_enabled: bool = False
    email_reply_lookback_hours: int = 72
    email_reply_max_messages: int = 50

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
