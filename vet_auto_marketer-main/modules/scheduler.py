"""APScheduler wiring — runs all recurring jobs in the background."""
from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger
from pytz import timezone as pytz_timezone

from config import schedule as sched_cfg
from config.settings import settings


_scheduler: BackgroundScheduler | None = None


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(timezone=pytz_timezone(settings.timezone))
    return _scheduler


def register_jobs() -> None:
    """Import agents lazily to avoid circular imports at module load."""
    from agents import trend_agent, content_agent

    sch = get_scheduler()

    # ---- Trend tracker — hourly ----
    sch.add_job(
        trend_agent.tick,
        IntervalTrigger(seconds=sched_cfg.CADENCE["trend_loop"]),
        id="trend_loop",
        replace_existing=True,
        max_instances=1,
    )

    # ---- Daily content planner — seeds the queue at 07:00 ----
    sch.add_job(
        content_agent.plan_today,
        CronTrigger(hour=7, minute=0),
        id="daily_plan",
        replace_existing=True,
    )

    # ---- Schedule story/post slots as jobs ----
    for slot in sched_cfg.daily_slots():
        hh, mm = slot.time_hhmm.split(":")
        sch.add_job(
            content_agent.fire_slot,
            CronTrigger(hour=int(hh), minute=int(mm)),
            args=[slot.kind, slot.content_source],
            id=f"slot_{slot.kind}_{slot.time_hhmm}_{slot.content_source}",
            replace_existing=True,
        )

    # ---- Nano Banana daily tip generation (07:00) ----
    from modules.nano_banana import generate_daily_tips
    sch.add_job(
        generate_daily_tips,
        CronTrigger(hour=7, minute=0),
        kwargs={"count": 5},
        id="nano_banana_daily_tips",
        replace_existing=True,
        max_instances=1,
    )

    logger.success("Scheduler jobs registered ({} jobs)", len(sch.get_jobs()))


def start() -> None:
    sch = get_scheduler()
    if not sch.running:
        register_jobs()
        sch.start()
        logger.success("APScheduler started (tz={})", settings.timezone)


def shutdown() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")
