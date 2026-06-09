"""
Application settings module.

Manages all configuration via environment variables using pydantic-settings.
"""

from functools import lru_cache

from pydantic import BaseModel
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

    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="REDIS_", extra="ignore"
    )

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

    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="TELEGRAM_", extra="ignore"
    )

    bot_token: str = ""
    webhook_url: str = ""  # TELEGRAM_WEBHOOK_URL
    admin_id: str | None = None  # Admin ID for error notifications


class CrawlerSettings(BaseSettings):
    """Crawler settings."""

    default_region: int = 1  # Taipei

    # Crawl interval in minutes
    interval_minutes: int = 10  # Daytime (8:00-01:00): every 10 min
    night_interval_minutes: int = 120  # Night (01:00-08:00): every 2 hours

    # Night hours (24h format)
    night_start_hour: int = 1  # 01:00
    night_end_hour: int = 8  # 08:00

    model_config = SettingsConfigDict(env_prefix="CRAWLER_")


class SourceConfig(BaseModel):
    """Per-source crawl config (keyed by ``Source.key`` in ``Settings.sources``).

    Crawl behaviour that differs per origin lives here with the source, not as a
    global flag. Add one block per new source.
    """

    # fetch_all=True  -> fetch the detail page for EVERY new object (complete DB,
    #                    no missed notifications). 591's current form.
    # fetch_all=False -> only fetch detail for objects a subscription might match
    #                    (legacy pre-filter, via src/matching/pre_filter.py).
    fetch_all: bool = True


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Deployment environment. "development" runs the crawler on a single
    # 24h interval (no day/night split); "production" keeps day/night scheduling.
    environment: str = "production"

    log_level: str = "INFO"
    jwt_secret: str = "change_me_in_production_591_crawler_jwt_secret"

    @property
    def is_development(self) -> bool:
        """True when running in the development environment."""
        return self.environment.lower() in ("development", "dev", "local")

    postgres: PostgresSettings = PostgresSettings()
    redis: RedisSettings = RedisSettings()
    telegram: TelegramSettings = TelegramSettings()
    crawler: CrawlerSettings = CrawlerSettings()

    # Per-source crawl config, keyed by Source.key (e.g. "591", matching
    # DBReadyData["source"] — note: the source key is "591", not the folder
    # name "x591"). Future sources add their own entry, e.g.:
    #   sources={"591": SourceConfig(fetch_all=True),
    #            "ddroom": SourceConfig(fetch_all=False)}
    sources: dict[str, SourceConfig] = {"591": SourceConfig(fetch_all=True)}

    def source_config(self, key: str) -> SourceConfig:
        """Config for a source key, falling back to defaults if not listed."""
        return self.sources.get(key, SourceConfig())


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
