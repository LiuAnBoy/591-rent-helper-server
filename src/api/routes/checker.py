"""Checker routes."""

from fastapi import APIRouter
from loguru import logger

from src.jobs import scheduler

checker_log = logger.bind(module="Checker")

router = APIRouter(prefix="/checker", tags=["Checker"])


@router.post("/run")
async def trigger_checker() -> dict:
    """Manually trigger checker job."""
    checker_log.info("Manually triggering checker job...")
    checker = scheduler.get_checker()
    results = await checker.check_active_regions()
    return {
        "status": True,
        "results": [
            {
                "region": r.get("region"),
                "fetched": r["fetched"],
                "new_count": r["new_count"],
                "matches": len(r["matches"]),
                "broadcast": r.get("broadcast", {}),
            }
            for r in results
        ],
    }
