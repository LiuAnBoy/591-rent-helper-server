"""
Subscription Models.

Pydantic models for subscription CRUD operations.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class SubscriptionBase(BaseModel):
    """Base subscription model with common fields."""

    name: str = Field(..., min_length=1, max_length=200, description="訂閱名稱")

    # Location
    region: int = Field(..., description="縣市代碼 (1=台北市, 3=新北市)")
    section: Optional[list[int]] = Field(None, description="區域代碼 (可多選)")

    # Property type
    kind: Optional[list[int]] = Field(None, description="物件類型 (1=整層, 2=獨立套房, 3=分租套房, 4=雅房)")

    # Price range
    price_min: Optional[int] = Field(None, ge=0, description="最低租金")
    price_max: Optional[int] = Field(None, ge=0, description="最高租金")

    # Layout
    layout: Optional[list[int]] = Field(None, description="格局 (1=1房, 2=2房, 3=3房, 4=4房以上)")

    # Building type
    shape: Optional[list[int]] = Field(None, description="建物型態 (1=公寓, 2=電梯大樓, 3=透天厝, 4=別墅)")

    # Area range
    area_min: Optional[Decimal] = Field(None, ge=0, description="最小坪數")
    area_max: Optional[Decimal] = Field(None, ge=0, description="最大坪數")

    # Floor
    floor: Optional[list[str]] = Field(None, description="樓層 (1_1=1樓, 2_6=2-6層, 6_12=6-12層, 13_=12樓以上)")

    # Bathroom
    bathroom: Optional[list[str]] = Field(None, description="衛浴數量 (1, 2, 3, 4_)")

    # Features
    features: Optional[list[str]] = Field(
        None,
        description="特色 (newPost, near_subway, pet, cook, cartplace, lift, balcony_1, lease...)"
    )

    # Options/Equipment
    options: Optional[list[str]] = Field(
        None,
        description="設備 (cold, washer, icebox, hotwater, naturalgas, broadband, bed)"
    )

    # Fitment
    fitment: Optional[list[int]] = Field(None, description="裝潢 (99=新裝潢, 3=中檔, 4=高檔)")

    # Notice fields (replaced from notice: list[str])
    exclude_rooftop: bool = Field(False, description="排除頂樓加蓋")
    gender: Optional[str] = Field(None, description="性別限制 (boy=限男, girl=限女, None=不限)")
    pet_required: bool = Field(False, description="需要可養寵物")

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v: Optional[str]) -> Optional[str]:
        """Validate gender field only allows 'boy', 'girl', or None."""
        if v is not None and v not in ["boy", "girl"]:
            raise ValueError("gender must be 'boy', 'girl', or None")
        return v


class SubscriptionCreate(SubscriptionBase):
    """Model for creating a subscription."""

    pass


class SubscriptionUpdate(BaseModel):
    """Model for updating a subscription (all fields optional)."""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    region: Optional[int] = None
    section: Optional[list[int]] = None
    kind: Optional[list[int]] = None
    price_min: Optional[int] = Field(None, ge=0)
    price_max: Optional[int] = Field(None, ge=0)
    layout: Optional[list[int]] = None
    shape: Optional[list[int]] = None
    area_min: Optional[Decimal] = Field(None, ge=0)
    area_max: Optional[Decimal] = Field(None, ge=0)
    floor: Optional[list[str]] = None
    bathroom: Optional[list[str]] = None
    features: Optional[list[str]] = None
    options: Optional[list[str]] = None
    fitment: Optional[list[int]] = None
    exclude_rooftop: Optional[bool] = None
    gender: Optional[str] = None
    pet_required: Optional[bool] = None
    # Note: `enabled` is not allowed here. Use PATCH .../toggle instead.


class SubscriptionResponse(SubscriptionBase):
    """Model for subscription response."""

    id: int
    user_id: int
    enabled: bool = True
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SubscriptionListResponse(BaseModel):
    """Model for listing subscriptions."""

    total: int
    items: list[SubscriptionResponse]
