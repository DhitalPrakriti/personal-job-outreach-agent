"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    automation_api_key: str = ""

    # Database
    database_url: str = "postgresql+asyncpg://agent:changeme@localhost:5432/email_agent"

    # LLM
    litellm_base_url: str = "http://localhost:4000"
    litellm_master_key: str = ""
    anthropic_api_key: str = ""
    primary_model: str = "claude-sonnet"
    fast_model: str = "claude-haiku"
    ai_drafting_enabled: bool = False

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
    google_oauth_redirect_uri: str = "http://localhost:8000/auth/google/callback"
    email_reply_sync_enabled: bool = False
    email_reply_lookback_hours: int = 72
    email_reply_max_messages: int = 50

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache()
def get_settings() -> Settings:
    return Settings()



