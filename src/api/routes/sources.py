"""Source catalog routes."""

from fastapi import APIRouter

from src.crawler import registry

router = APIRouter(prefix="/sources", tags=["Sources"])


@router.get("")
async def list_sources() -> dict:
    """List registered crawl sources (key + display name) for UI / label use."""
    return {"items": registry.source_catalog()}
