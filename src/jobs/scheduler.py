"""
Job Scheduler Module.

Manages scheduled tasks for crawling and checking.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from config.settings import get_settings
from src.jobs.checker import Checker

scheduler_log = logger.bind(module="Scheduler")

# Timezone for scheduler
TZ = ZoneInfo("Asia/Taipei")

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


async def run_checker_job(skip_night: bool = False) -> None:
    """
    Scheduled job to check for new objects in active regions.

    Args:
        skip_night: If True, skip execution during night hours (for interval-based daytime job)
    """
    if skip_night:
        settings = get_settings()
        crawler = settings.crawler
        current_hour = datetime.now(TZ).hour
        is_night = crawler.night_start_hour <= current_hour < crawler.night_end_hour

        if is_night:
            scheduler_log.debug(f"Skipping daytime job during night hours (hour={current_hour})")
            return

    try:
        scheduler_log.info("Running scheduled checker job...")
        checker = get_checker()

        # Only check regions with active subscriptions
        results = await checker.check_active_regions()

        if not results:
            scheduler_log.info("No active regions to check")
            return

        for result in results:
            region = result.get("region", "?")
            broadcast = result.get("broadcast", {})
            initialized_subs = result.get("initialized_subs", [])

            scheduler_log.info(
                f"Region {region}: {result.get('new_count', 0)} new, "
                f"{len(result.get('matches', []))} matches, "
                f"{broadcast.get('success', 0)} notified"
            )
            if initialized_subs:
                scheduler_log.info(
                    f"  Initialized {len(initialized_subs)} subscriptions: "
                    f"{initialized_subs}"
                )
    except Exception as e:
        scheduler_log.error(f"Checker job failed: {e}")
    finally:
        # Close fetchers to release resources
        await close_checker()


def setup_jobs() -> None:
    """
    Setup scheduler jobs.

    Daytime (08:00-01:00): Interval-based (every X minutes)
    Nighttime (01:00-08:00): Fixed times (cron-based)
    """
    from functools import partial

    from apscheduler.triggers.interval import IntervalTrigger

    settings = get_settings()
    crawler = settings.crawler

    scheduler_log.info(
        f"Scheduler started: "
        f"{crawler.night_end_hour:02d}:00-{crawler.night_start_hour:02d}:00 every {crawler.interval_minutes}min, "
        f"{crawler.night_start_hour:02d}:00-{crawler.night_end_hour:02d}:00 every {crawler.night_interval_minutes}min"
    )

    # Daytime job: interval-based scheduling (skips during night hours)
    _scheduler.add_job(
        partial(run_checker_job, skip_night=True),
        IntervalTrigger(
            minutes=crawler.interval_minutes,
            timezone="Asia/Taipei",
        ),
        id="checker_job_daytime",
        name=f"Daytime checker (every {crawler.interval_minutes} min)",
        replace_existing=True,
    )

    # Nighttime job: fixed times (cron-based)
    def get_minute_expr(interval: int) -> str:
        if interval >= 60:
            return "0"
        minutes = list(range(0, 60, interval))
        return ",".join(str(m) for m in minutes)

    night_minutes = get_minute_expr(crawler.night_interval_minutes)
    night_hours = list(
        range(crawler.night_start_hour, crawler.night_end_hour)
    )
    night_hours_expr = ",".join(str(h) for h in night_hours)

    _scheduler.add_job(
        run_checker_job,
        CronTrigger(
            minute=night_minutes,
            hour=night_hours_expr,
            timezone="Asia/Taipei",
        ),
        id="checker_job_night",
        name=f"Night checker (every {crawler.night_interval_minutes} min)",
        replace_existing=True,
    )

    # Run immediately on startup
    _scheduler.add_job(
        run_checker_job,
        trigger="date",
        run_date=datetime.now(TZ),
        id="checker_job_startup",
        name="Startup checker",
        replace_existing=True,
    )
    scheduler_log.info("Startup job scheduled to run immediately")


def start() -> None:
    """Start the scheduler."""
    setup_jobs()
    _scheduler.start()
    scheduler_log.info("Scheduler started")


def shutdown() -> None:
    """Shutdown the scheduler."""
    _scheduler.shutdown(wait=False)
    scheduler_log.info("Scheduler stopped")
