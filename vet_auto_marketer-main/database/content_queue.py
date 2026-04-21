"""content_queue and trends_log — DAO layer."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from loguru import logger

from database.supabase_client import get_client


# =============================================================
# content_queue
# =============================================================
def enqueue(
    type_: str,
    content_type: str,
    *,
    media_url: Optional[str] = None,
    media_path: Optional[str] = None,
    caption: Optional[str] = None,
    hashtags: Optional[str] = None,
    scheduled_at: Optional[datetime] = None,
    status: str = "ready_for_manual_post",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Insert a new row into content_queue and return it."""
    payload = {
        "type": type_,
        "content_type": content_type,
        "status": status,
        "media_url": media_url,
        "media_path": media_path,
        "image_local_path": media_path,
        "caption": caption,
        "hashtags": hashtags,
        "scheduled_at": scheduled_at.isoformat() if scheduled_at else None,
        "metadata": metadata or {},
    }
    try:
        res = get_client().table("content_queue").insert(payload).execute()
        row = (res.data or [None])[0]
        logger.info("Enqueued content #{} ({}/{}) status={}", row.get("id"), type_, content_type, status)
        return row
    except Exception as e:
        logger.exception("enqueue failed: {}", e)
        raise


def list_ready(limit: int = 50) -> List[Dict[str, Any]]:
    """Fetch items ready for manual posting."""
    try:
        res = (
            get_client().table("content_queue")
            .select("*")
            .eq("status", "ready_for_manual_post")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []
    except Exception as e:
        logger.exception("list_ready failed: {}", e)
        return []


def list_posted(limit: int = 50) -> List[Dict[str, Any]]:
    """Fetch items that have been marked as posted."""
    try:
        res = (
            get_client().table("content_queue")
            .select("*")
            .eq("status", "marked_as_posted")
            .order("content_posted_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []
    except Exception as e:
        logger.exception("list_posted failed: {}", e)
        return []


def get_item(queue_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a single content_queue item by ID."""
    try:
        res = (
            get_client().table("content_queue")
            .select("*")
            .eq("id", queue_id)
            .maybe_single()
            .execute()
        )
        return res.data if res else None
    except Exception as e:
        logger.error("get_item failed: {}", e)
        return None


def mark_as_posted(queue_id: int) -> None:
    """Mark content as manually posted by the owner."""
    try:
        get_client().table("content_queue").update({
            "status": "marked_as_posted",
            "content_posted_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", queue_id).execute()
        logger.success("queue #{} marked as posted", queue_id)
    except Exception as e:
        logger.exception("mark_as_posted failed: {}", e)


def delete_item(queue_id: int) -> None:
    """Delete a content_queue item."""
    try:
        get_client().table("content_queue").delete().eq("id", queue_id).execute()
        logger.info("queue #{} deleted", queue_id)
    except Exception as e:
        logger.exception("delete_item failed: {}", e)


def mark_failed(queue_id: int, error_message: str) -> None:
    try:
        get_client().table("content_queue").update({
            "status": "failed",
            "error_message": error_message[:2000],
        }).eq("id", queue_id).execute()
        logger.warning("queue #{} marked failed: {}", queue_id, error_message)
    except Exception as e:
        logger.exception("mark_failed failed: {}", e)


def count_today(type_: Optional[str] = None) -> int:
    """Count items created today (any status)."""
    today = datetime.now(timezone.utc).date().isoformat()
    q = (
        get_client().table("content_queue")
        .select("id", count="exact")
        .gte("created_at", f"{today}T00:00:00Z")
    )
    if type_:
        q = q.eq("type", type_)
    try:
        return q.execute().count or 0
    except Exception as e:
        logger.error("count_today failed: {}", e)
        return 0


def count_by_status(status: str) -> int:
    """Count items by status."""
    try:
        res = (
            get_client().table("content_queue")
            .select("id", count="exact")
            .eq("status", status)
            .execute()
        )
        return res.count or 0
    except Exception as e:
        logger.error("count_by_status failed: {}", e)
        return 0


def count_images_this_week() -> int:
    """Count images generated this week."""
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    try:
        res = (
            get_client().table("content_queue")
            .select("id", count="exact")
            .gte("created_at", week_ago)
            .execute()
        )
        return res.count or 0
    except Exception as e:
        logger.error("count_images_this_week failed: {}", e)
        return 0


# =============================================================
# trends_log
# =============================================================
def log_trend(
    *,
    trend_topic: str,
    trend_volume: Optional[int] = None,
    trend_type: Optional[str] = None,
    relevance_score: Optional[int] = None,
    relevant: Optional[bool] = None,
    content_created: bool = False,
    queue_id: Optional[int] = None,
    reason: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    try:
        res = (
            get_client().table("trends_log")
            .insert({
                "trend_topic": trend_topic,
                "trend_volume": trend_volume,
                "trend_type": trend_type,
                "relevance_score": relevance_score,
                "relevant": relevant,
                "content_created": content_created,
                "queue_id": queue_id,
                "reason": reason,
            })
            .execute()
        )
        return (res.data or [None])[0]
    except Exception as e:
        logger.exception("log_trend failed: {}", e)
        return None


def trend_recently_handled(topic: str, within_hours: int = 12) -> bool:
    """Avoid re-creating content for the same trend within N hours."""
    since = (datetime.now(timezone.utc) - timedelta(hours=within_hours)).isoformat()
    try:
        res = (
            get_client().table("trends_log")
            .select("id")
            .eq("trend_topic", topic)
            .gte("detected_at", since)
            .limit(1)
            .execute()
        )
        return bool(res.data)
    except Exception as e:
        logger.error("trend_recently_handled failed: {}", e)
        return False


def list_trends_today(limit: int = 30) -> List[Dict[str, Any]]:
    """Fetch today's detected trends."""
    today = datetime.now(timezone.utc).date().isoformat()
    try:
        res = (
            get_client().table("trends_log")
            .select("*")
            .gte("detected_at", f"{today}T00:00:00Z")
            .order("detected_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []
    except Exception as e:
        logger.exception("list_trends_today failed: {}", e)
        return []


def count_trends_today() -> int:
    """Count trends detected today."""
    today = datetime.now(timezone.utc).date().isoformat()
    try:
        res = (
            get_client().table("trends_log")
            .select("id", count="exact")
            .gte("detected_at", f"{today}T00:00:00Z")
            .execute()
        )
        return res.count or 0
    except Exception as e:
        logger.error("count_trends_today failed: {}", e)
        return 0
