"""Application configuration using pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    bot_token: str
    database_url: str

    debug: bool = False

    # LLM Configuration
    llm_provider: str = "anthropic"  # "anthropic" or "openai"
    llm_api_key: str | None = None
    llm_base_url: str | None = None  # For local inference (vLLM, etc.)
    llm_model: str = "claude-sonnet-4-20250514"  # Default model


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
