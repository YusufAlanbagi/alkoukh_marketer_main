"""Trend agent — polls Iraqi trends, asks Claude if they're relevant,
and enqueues content for the publisher when they are.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from loguru import logger

from database import content_queue as cq
from modules import ai_generator, trend_tracker


URGENCY_DELAY_MIN = {"High": 2, "Medium": 20, "Low": 60}


def tick() -> None:
    trends = trend_tracker.fetch_iraqi_trends(limit=15)
    if not trends:
        return

    processed = 0
    for trend in trends:
        if cq.trend_recently_handled(trend.topic):
            continue

        skip_reason = trend_tracker.pre_filter(trend)
        if skip_reason:
            cq.log_trend(
                trend_topic=trend.topic,
                trend_volume=trend.volume,
                trend_type=trend.trend_type,
                relevance_score=0,
                relevant=False,
                reason=skip_reason,
            )
            continue

        affinity = trend_tracker.score_pet_affinity(trend)
        if affinity < 30:
            cq.log_trend(
                trend_topic=trend.topic,
                trend_volume=trend.volume,
                trend_type=trend.trend_type,
                relevance_score=affinity,
                relevant=False,
                reason="low pet-affinity score",
            )
            continue

        # Pass to Claude for final decision + caption
        analysis = ai_generator.analyze_trend(
            trend_topic=trend.topic,
            trend_volume=trend.volume,
            trend_type=trend.trend_type,
        )

        if not analysis.relevant or not analysis.caption:
            cq.log_trend(
                trend_topic=trend.topic,
                trend_volume=trend.volume,
                trend_type=trend.trend_type,
                relevance_score=affinity,
                relevant=False,
                reason=analysis.reason or "LLM rejected",
            )
            continue

        # Enqueue
        delay = URGENCY_DELAY_MIN.get(analysis.urgency, 30)
        scheduled = datetime.now(timezone.utc) + timedelta(minutes=delay)
        kind = analysis.content_type.lower()
        if kind not in ("post", "story", "reel"):
            kind = "post"

        queued = cq.enqueue(
            type_=kind,
            content_type="trend",
            caption=analysis.caption,
            scheduled_at=scheduled,
            metadata={
                "trend_topic": trend.topic,
                "urgency": analysis.urgency,
                "reason": analysis.reason,
            },
        )
        cq.log_trend(
            trend_topic=trend.topic,
            trend_volume=trend.volume,
            trend_type=trend.trend_type,
            relevance_score=affinity,
            relevant=True,
            content_created=True,
            queue_id=queued.get("id"),
            reason=analysis.reason,
        )
        processed += 1

    if processed:
        logger.success("trend_agent queued {} new content items", processed)
