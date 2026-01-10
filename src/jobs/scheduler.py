"""
Job Scheduler Module.

Manages scheduled tasks for crawling and checking.
"""

from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from config.settings import get_settings
from src.jobs.checker import Checker


# Scheduler instance
_scheduler = AsyncIOScheduler(timezone="Asia/Taipei")

# Checker instance (lazy initialized)
_checker: Checker | None = None


def get_checker() -> Checker:
    """Get or create checker instance."""
    global _checker
    if _checker is None:
        _checker = Checker()
    return _checker


async def close_checker() -> None:
    """Close checker resources."""
    global _checker
    if _checker is not None:
        await _checker.close()
        _checker = None


def _is_night_time() -> bool:
    """Check if current time is in night period."""
    settings = get_settings()
    crawler = settings.crawler
    current_hour = datetime.now().hour

    # Night: 01:00 - 06:00
    return crawler.night_start_hour <= current_hour < crawler.night_end_hour


def _get_current_interval() -> int:
    """Get current interval based on time of day."""
    settings = get_settings()
    crawler = settings.crawler

    if _is_night_time():
        return crawler.night_interval_minutes
    return crawler.interval_minutes


def _schedule_next_job() -> None:
    """Schedule next checker job based on current time."""
    interval = _get_current_interval()
    next_run = datetime.now() + timedelta(minutes=interval)

    # Remove existing job if any
    if _scheduler.get_job("checker_job_next"):
        _scheduler.remove_job("checker_job_next")

    _scheduler.add_job(
        run_checker_job,
        trigger="date",
        run_date=next_run,
        id="checker_job_next",
        name=f"Next checker (in {interval} min)",
        replace_existing=True,
    )

    time_period = "night" if _is_night_time() else "daytime"
    logger.info(f"Next job scheduled in {interval} minutes ({time_period})")


async def run_checker_job() -> None:
    """Scheduled job to check for new listings in active regions."""
    try:
        logger.info("Running scheduled checker job...")
        checker = get_checker()

        # Only check regions with active subscriptions
        results = await checker.check_active_regions()

        if not results:
            logger.info("No active regions to check")
            return

        for result in results:
            region = result.get("region", "?")
            broadcast = result.get("broadcast", {})
            initialized_subs = result.get("initialized_subs", [])

            logger.info(
                f"Region {region}: {result.get('new_count', 0)} new, "
                f"{len(result.get('matches', []))} matches, "
                f"{broadcast.get('success', 0)} notified"
            )
            if initialized_subs:
                logger.info(
                    f"  Initialized {len(initialized_subs)} subscriptions: "
                    f"{initialized_subs}"
                )
    except Exception as e:
        logger.error(f"Checker job failed: {e}")
    finally:
        # Close browser to release memory
        await close_checker()
        logger.info("Browser closed, memory released")

        # Schedule next job
        _schedule_next_job()


def setup_jobs() -> None:
    """Setup scheduler jobs."""
    settings = get_settings()
    crawler = settings.crawler

    logger.info(
        f"Scheduler config: daytime={crawler.interval_minutes}min, "
        f"night={crawler.night_interval_minutes}min "
        f"(night: {crawler.night_start_hour}:00-{crawler.night_end_hour}:00)"
    )

    # Run immediately on startup
    _scheduler.add_job(
        run_checker_job,
        trigger="date",
        run_date=datetime.now(),
        id="checker_job_startup",
        name="Startup checker",
        replace_existing=True,
    )
    logger.info("Startup job scheduled to run immediately")


def start() -> None:
    """Start the scheduler."""
    setup_jobs()
    _scheduler.start()
    logger.info("Scheduler started")


def shutdown() -> None:
    """Shutdown the scheduler."""
    _scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")
