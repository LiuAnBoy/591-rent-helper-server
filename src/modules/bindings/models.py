"""
Notification Binding Models.

Pydantic models for notification service bindings (Telegram, Line, etc.)
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class NotificationBinding(BaseModel):
    """Notification binding model."""

    id: int
    user_id: int
    service: str = Field(..., description="Service type: telegram, line, discord")
    service_id: Optional[str] = Field(None, description="Service user ID (e.g., chat_id)")
    bind_code: Optional[str] = Field(None, description="Temporary bind code")
    bind_code_expires_at: Optional[datetime] = Field(None, description="Bind code expiry")
    enabled: bool = Field(default=True)
    created_at: datetime
    updated_at: datetime

    @property
    def is_bound(self) -> bool:
        """Check if binding is complete (has service_id)."""
        return self.service_id is not None and self.service_id != ""

    @property
    def is_bind_code_valid(self) -> bool:
        """Check if bind code is valid and not expired."""
        if not self.bind_code or not self.bind_code_expires_at:
            return False
        return datetime.now(self.bind_code_expires_at.tzinfo) < self.bind_code_expires_at


class BindingCreate(BaseModel):
    """Model for creating a binding."""

    service: str = Field(..., description="Service type: telegram")


class BindCodeResponse(BaseModel):
    """Response model for bind code generation."""

    code: str = Field(..., description="10-character alphanumeric bind code")
    expires_in: int = Field(default=600, description="Expiry time in seconds")
    bind_url: Optional[str] = Field(default=None, description="Telegram deep link URL")


class BindingResponse(BaseModel):
    """Response model for binding status."""

    service: str
    is_bound: bool
    service_id: Optional[str] = None
    enabled: bool = True
    created_at: Optional[datetime] = None
