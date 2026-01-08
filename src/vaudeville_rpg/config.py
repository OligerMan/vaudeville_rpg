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

    # LLM Logging Configuration
    llm_log_dir: str = "llm_logs"  # Directory for LLM interaction logs
    llm_max_retries: int = 3  # Maximum retry attempts for LLM generation
    llm_retry_delay: float = 1.0  # Delay between retries in seconds
    llm_log_rotation_count: int = 50  # Keep last N log files

    # Admin Configuration
    admin_user_ids: str | None = None  # Comma-separated list of Telegram user IDs

    def get_admin_user_ids(self) -> list[int]:
        """Parse admin user IDs from comma-separated string."""
        if not self.admin_user_ids:
            return []
        return [int(uid.strip()) for uid in self.admin_user_ids.split(",") if uid.strip()]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
