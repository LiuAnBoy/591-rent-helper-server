"""
Object Models.

Pydantic model for 591 rental listing data.
"""

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class Surrounding(BaseModel):
    """Surrounding information (e.g., nearby metro station)."""

    type: Optional[str] = None
    desc: Optional[str] = None
    distance: Optional[str] = None


class RentalObject(BaseModel):
    """591 rental object data model."""

    # Primary key
    id: int

    # Basic info
    kind: Optional[int] = None
    kind_name: Optional[str] = None
    title: str
    url: Optional[str] = None

    # Price
    price: str
    price_unit: Optional[str] = Field(default="元/月")
    price_per: Optional[float] = None

    @field_validator("price_per", mode="before")
    @classmethod
    def parse_price_per(cls, v: Any) -> Optional[float]:
        """Parse price_per, handling comma-separated numbers."""
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            # Remove commas and convert to float
            try:
                return float(v.replace(",", ""))
            except ValueError:
                return None
        return None

    # Space info
    floor_name: Optional[str] = None
    floor: Optional[int] = Field(default=None, description="樓層 (0=頂加, 負數=地下)")
    total_floor: Optional[int] = Field(default=None, description="總樓層數")
    area: Optional[float] = None
    shape: Optional[int] = Field(default=None, description="建物型態 (1=公寓, 2=電梯大樓, 3=透天厝, 4=別墅)")
    layout_str: Optional[str] = Field(default=None, alias="layoutStr")
    bathroom: Optional[int] = Field(default=None, description="衛浴數量")
    fitment: Optional[int] = Field(default=None, description="裝潢代號 (99=新, 3=中檔, 4=高檔)")

    # Location
    address: Optional[str] = None
    region: Optional[int] = Field(default=None, alias="regionid")
    section: Optional[int] = Field(default=None, alias="sectionid")

    # Tags and features
    tags: list[str] = Field(default_factory=list)
    other: list[str] = Field(default_factory=list, description="特色代碼 (near_subway, pet, cook...)")

    # Surrounding
    surrounding: Optional[Surrounding] = None

    # Detail page fields (parsed from detail page)
    is_rooftop: bool = Field(default=False, description="是否頂樓加蓋 (from floor_name)")
    gender: str = Field(default="all", description="性別限制 (boy/girl/all, from service.rule)")
    pet_allowed: Optional[bool] = Field(default=None, description="可否養寵物 (from service.rule)")
    options: list[str] = Field(default_factory=list, description="提供設備 (from service.facility)")

    class Config:
        """Pydantic config."""

        populate_by_name = True

    def price_int(self) -> int:
        """Get price as integer (remove comma)."""
        return int(self.price.replace(",", ""))

    def __str__(self) -> str:
        """String representation for console output."""
        return (
            f"[{self.id}] {self.title}\n"
            f"    💰 {self.price} {self.price_unit or ''}\n"
            f"    📍 {self.address or 'N/A'}\n"
            f"    🏠 {self.kind_name or 'N/A'} | {self.area or 'N/A'}坪 | {self.layout_str or 'N/A'}\n"
            f"    🏷️  {', '.join(self.tags) if self.tags else 'N/A'}"
        )
