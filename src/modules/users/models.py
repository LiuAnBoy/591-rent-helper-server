"""
User Models.

Pydantic models for user authentication and profile.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, EmailStr


class User(BaseModel):
    """User model from database."""

    id: int
    email: str
    role: str = "user"
    enabled: bool = True
    created_at: datetime
    updated_at: datetime


class UserCreate(BaseModel):
    """Model for user registration."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=6, description="Password (min 6 characters)")


class UserLogin(BaseModel):
    """Model for user login."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="Password")


class TokenResponse(BaseModel):
    """Response model for authentication tokens."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Token expiry in seconds")


class UserResponse(BaseModel):
    """Response model for user data (without password)."""

    id: int
    email: str
    role: str
    enabled: bool
    created_at: datetime
    updated_at: datetime


class UserWithBindings(BaseModel):
    """User response with bindings data."""

    id: int
    email: str
    role: str
    enabled: bool
    created_at: datetime
    updated_at: datetime
    bindings: list[dict] = Field(default_factory=list)
    subscription_count: int = 0
    max_subscriptions: int = 3
