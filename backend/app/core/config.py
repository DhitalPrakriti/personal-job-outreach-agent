"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    app_env: str = "development"
    app_port: int = 8000
    app_secret_key: str = "change-me"
    api_base_url: str = "http://localhost:8000"

    # Database
    database_url: str = "postgresql+asyncpg://agent:changeme@localhost:5432/email_agent"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"

    # LLM
    litellm_base_url: str = "http://localhost:4000"
    primary_model: str = "claude-sonnet"
    fast_model: str = "claude-haiku"
    monthly_llm_budget_usd: float = 200.0

    # Email Sending (SES)
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"
    ses_sender_email: str = ""

    # Email Receiving (IMAP)
    imap_host: str = ""
    imap_port: int = 993
    imap_user: str = ""
    imap_password: str = ""

    # Notion
    notion_api_key: str = ""
    notion_leads_database_id: str = ""

    # Slack
    slack_webhook_url: str = ""

    # Dify
    dify_base_url: str = "http://localhost:3100/v1"
    dify_api_key: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
