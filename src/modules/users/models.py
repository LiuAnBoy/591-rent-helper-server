"""
User Models.

Pydantic models for user authentication and profile.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class User(BaseModel):
    """User model from database."""

    id: int
    name: str | None = None
    email: str | None = None
    role: str = "user"
    enabled: bool = True
    created_at: datetime
    updated_at: datetime


class UserWithBindings(BaseModel):
    """User response with bindings data."""

    id: int
    email: str = ""
    name: str | None = None
    role: str
    enabled: bool
    created_at: datetime
    updated_at: datetime
    bindings: list[dict] = Field(default_factory=list)
    subscription_count: int = 0
    max_subscriptions: int = 3
