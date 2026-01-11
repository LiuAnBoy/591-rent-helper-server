"""User Provider models for multi-platform authentication."""

from datetime import datetime
from typing import Optional

import json

from pydantic import BaseModel, Field, field_validator


class UserProvider(BaseModel):
    """User provider binding model."""

    id: int
    user_id: int
    provider: str = Field(..., description="Provider type: telegram, line, discord")
    provider_id: str = Field(..., description="Provider user ID")
    provider_data: dict = Field(default_factory=dict, description="Extra provider data")
    notify_enabled: bool = Field(default=True, description="Whether to receive notifications")
    created_at: datetime
    updated_at: datetime

    @field_validator("provider_data", mode="before")
    @classmethod
    def parse_provider_data(cls, v):
        """Parse provider_data from JSON string if needed."""
        if isinstance(v, str):
            return json.loads(v)
        return v or {}

    @property
    def is_telegram(self) -> bool:
        """Check if this is a Telegram provider."""
        return self.provider == "telegram"

    @property
    def is_line(self) -> bool:
        """Check if this is a LINE provider."""
        return self.provider == "line"


class TelegramUser(BaseModel):
    """Telegram user data from Web App initData."""

    id: int = Field(..., description="Telegram user ID")
    first_name: str = Field(..., description="User's first name")
    last_name: Optional[str] = Field(None, description="User's last name")
    username: Optional[str] = Field(None, description="Telegram username")
    language_code: Optional[str] = Field(None, description="User's language code")
    photo_url: Optional[str] = Field(None, description="User's profile photo URL")
    is_premium: Optional[bool] = Field(None, description="Is Telegram Premium user")

    @property
    def display_name(self) -> str:
        """Get display name for user."""
        if self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name


class TelegramAuthData(BaseModel):
    """Parsed Telegram Web App initData."""

    user: TelegramUser
    auth_date: int = Field(..., description="Unix timestamp of authentication")
    hash: str = Field(..., description="Hash for verification")
    query_id: Optional[str] = Field(None, description="Query ID for inline mode")
    chat_type: Optional[str] = Field(None, description="Chat type")
    chat_instance: Optional[str] = Field(None, description="Chat instance")

    def is_expired(self, max_age_seconds: int = 3600) -> bool:
        """
        Check if auth data is expired.

        Args:
            max_age_seconds: Maximum age in seconds (default: 1 hour)

        Returns:
            True if expired
        """
        now = int(datetime.now().timestamp())
        return (now - self.auth_date) > max_age_seconds


class UserProviderCreate(BaseModel):
    """Request model for creating a user provider."""

    provider: str
    provider_id: str
    provider_data: dict = Field(default_factory=dict)
    notify_enabled: bool = True


class UserProviderResponse(BaseModel):
    """Response model for user provider."""

    id: int
    provider: str
    provider_id: str
    provider_data: dict
    notify_enabled: bool
    created_at: datetime
