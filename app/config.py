"""Application configuration using pydantic-settings."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    default_model: str = "gpt-4o-mini"
    daily_send_time: str = "08:00"
    database_url: str = "sqlite:///./data/sefaria_daily.db"
    debug: bool = False
    app_title: str = "Sefaria Daily AI"


def get_settings() -> Settings:
    """Return application settings singleton."""
    return Settings()
