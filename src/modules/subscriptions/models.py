"""
Subscription Models.

Pydantic models for subscription CRUD operations.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, computed_field, field_validator


def parse_floor_ranges(floor_list: list[str] | None) -> tuple[int | None, int | None]:
    """
    Parse floor range codes to min/max integers.

    Args:
        floor_list: List of floor range codes like ['2_6', '7_12']

    Returns:
        (floor_min, floor_max) tuple

    Examples:
        ['1_1']           -> (1, 1)
        ['2_6']           -> (2, 6)
        ['2_6', '7_12']   -> (2, 12)
        ['12_']           -> (12, None)
    """
    if not floor_list:
        return None, None

    floor_min: int | None = None
    floor_max: int | None = None

    for code in floor_list:
        parts = code.split("_")
        if len(parts) == 2:
            low_str, high_str = parts
            low = int(low_str) if low_str else None
            high = int(high_str) if high_str else None

            if low is not None:
                if floor_min is None or low < floor_min:
                    floor_min = low
            if high is not None:
                if floor_max is None or high > floor_max:
                    floor_max = high
            elif low is not None and high_str == "":
                # Format like '12_' means 12+, so no max limit
                floor_max = None

    return floor_min, floor_max


def floor_to_range_codes(
    floor_min: int | None, floor_max: int | None
) -> list[str] | None:
    """
    Convert floor min/max to range codes.

    Args:
        floor_min: Minimum floor
        floor_max: Maximum floor

    Returns:
        List with single range code, or None if no floor filter

    Examples:
        (1, 1)    -> ['1_1']
        (2, 6)    -> ['2_6']
        (12, None) -> ['12_']
        (None, None) -> None
    """
    if floor_min is None and floor_max is None:
        return None

    if floor_min is not None and floor_max is not None:
        return [f"{floor_min}_{floor_max}"]
    elif floor_min is not None:
        return [f"{floor_min}_"]
    else:
        return [f"_{floor_max}"]


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

    # Floor (存 floor_min/floor_max)
    floor_min: Optional[int] = Field(None, description="最低樓層 (0=頂加, 負數=地下)")
    floor_max: Optional[int] = Field(None, description="最高樓層")

    # Bathroom
    bathroom: Optional[list[int]] = Field(None, description="衛浴數量 (1, 2, 3, 4=4+)")

    # Other (features)
    other: Optional[list[str]] = Field(
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

    # 前端傳 floor 陣列，API 轉成 floor_min/floor_max 存
    floor: Optional[list[str]] = Field(None, description="樓層 (1, 2_6, 6_12, 12_)")


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
    bathroom: Optional[list[int]] = None
    other: Optional[list[str]] = None
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

    @computed_field
    @property
    def floor(self) -> list[str] | None:
        """Computed floor range codes from floor_min/floor_max for API compatibility."""
        return floor_to_range_codes(self.floor_min, self.floor_max)

    class Config:
        from_attributes = True


class SubscriptionListResponse(BaseModel):
    """Model for object subscriptions."""

    total: int
    items: list[SubscriptionResponse]
