"""
Application settings module.

Manages all configuration via environment variables using pydantic-settings.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class PostgresSettings(BaseSettings):
    """PostgreSQL connection settings."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="PG_", extra="ignore")

    host: str = "localhost"
    port: int = 5432
    user: str = "admin"
    password: str = "1234"
    database: str = "rent591_dev"
    pool_max: int = 10

    @property
    def dsn(self) -> str:
        """Generate PostgreSQL DSN."""
        return (
            f"postgresql+asyncpg://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )


class RedisSettings(BaseSettings):
    """Redis connection settings."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="REDIS_", extra="ignore")

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str = ""

    @property
    def url(self) -> str:
        """Generate Redis URL."""
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


class TelegramSettings(BaseSettings):
    """Telegram bot settings."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="TELEGRAM_", extra="ignore")

    bot_token: str = ""
    webhook_url: str = ""  # TELEGRAM_WEBHOOK_URL


class CrawlerSettings(BaseSettings):
    """Crawler settings."""

    default_region: int = 1  # Taipei

    # Crawl interval in minutes
    interval_minutes: int = 15        # Daytime (8:00-01:00): every 15 min
    night_interval_minutes: int = 120  # Night (01:00-08:00): every 2 hours

    # Night hours (24h format)
    night_start_hour: int = 1   # 01:00
    night_end_hour: int = 8     # 08:00

    model_config = SettingsConfigDict(env_prefix="CRAWLER_")


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    log_level: str = "INFO"
    jwt_secret: str = "change_me_in_production_591_crawler_jwt_secret"

    postgres: PostgresSettings = PostgresSettings()
    redis: RedisSettings = RedisSettings()
    telegram: TelegramSettings = TelegramSettings()
    crawler: CrawlerSettings = CrawlerSettings()


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
