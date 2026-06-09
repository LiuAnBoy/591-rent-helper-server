"""
Shared crawler data contract.

``DBReadyData`` is the source-agnostic boundary type: every source's parser must
produce it, and the core (DB / Redis / matcher) and presentation layers consume
only it. It lives here (not under any one source) so all sources and the core
depend on a single shared definition.
"""

from typing import TypedDict


class DBReadyData(TypedDict):
    """Database-ready data structure matching objects table schema.

    Objects are identified by (source, source_id). The DB-generated UUID primary
    key is NOT part of this contract; it is assigned by PostgreSQL on insert and
    never used by application logic.
    """

    source: str
    source_id: str
    url: str
    title: str
    price: int
    price_unit: str
    region: int
    section: int
    kind: int
    kind_name: str
    address: str
    floor: int | None
    floor_str: str
    total_floor: int | None
    is_rooftop: bool
    layout: int | None
    layout_str: str
    bathroom: int | None
    area: float | None
    shape: int | None
    fitment: int | None
    gender: str
    pet_allowed: bool
    options: list[str]
    other: list[str]
    tags: list[str]
    surrounding_type: str | None
    surrounding_desc: str | None
    surrounding_distance: int | None
    has_detail: bool
