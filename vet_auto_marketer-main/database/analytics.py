"""analytics table helpers + weekly report builder."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from loguru import logger

from database.supabase_client import get_client


def record_post_metrics(
    *,
    instagram_post_id: str,
    queue_id: Optional[int],
    likes: int = 0,
    comments: int = 0,
    shares: int = 0,
    saves: int = 0,
    reach: int = 0,
    impressions: int = 0,
    dm_responses: int = 0,
) -> None:
    total_interactions = likes + comments + shares + saves
    response_rate = (dm_responses / reach * 100) if reach else 0
    payload = {
        "date": date.today().isoformat(),
        "instagram_post_id": instagram_post_id,
        "queue_id": queue_id,
        "likes": likes,
        "comments": comments,
        "shares": shares,
        "saves": saves,
        "reach": reach,
        "impressions": impressions,
        "dm_responses": dm_responses,
        "response_rate": round(response_rate, 2),
    }
    try:
        get_client().table("analytics").insert(payload).execute()
        logger.info("analytics recorded for IG post {} (interactions={})",
                    instagram_post_id, total_interactions)
    except Exception as e:
        logger.exception("record_post_metrics failed: {}", e)


def weekly_summary() -> Dict[str, Any]:
    """Return aggregated metrics for the last 7 days."""
    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    try:
        res = (
            get_client().table("analytics")
            .select("*")
            .gte("captured_at", since)
            .execute()
        )
        rows: List[Dict[str, Any]] = res.data or []
    except Exception as e:
        logger.exception("weekly_summary failed: {}", e)
        return {}

    if not rows:
        return {"posts": 0, "note": "No data yet."}

    totals = {k: 0 for k in ("likes", "comments", "shares", "saves",
                              "reach", "impressions", "dm_responses")}
    for r in rows:
        for k in totals:
            totals[k] += r.get(k) or 0

    top = max(rows, key=lambda r: (r.get("likes", 0) + r.get("comments", 0)))
    return {
        "posts": len(rows),
        "totals": totals,
        "avg_likes_per_post": round(totals["likes"] / len(rows), 1),
        "top_post_id": top.get("instagram_post_id"),
        "top_post_interactions": top.get("likes", 0) + top.get("comments", 0),
    }
