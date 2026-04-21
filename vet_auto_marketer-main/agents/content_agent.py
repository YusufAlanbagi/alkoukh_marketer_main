"""Content agent — picks media from the right folder, generates caption,
and saves it as ready_for_manual_post for the owner to download and publish.

Sources:
  - owner       → content/uploads/
  - nano_banana → content/nano_banana/
  - generated   → content/generated/ (populated by external pipelines)
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from loguru import logger

from config.settings import settings
from database import content_queue as cq
from modules import ai_generator, media_processor


# =============================================================
# Daily planner — seeds the queue with tomorrow's slot assignments
# =============================================================
def plan_today() -> None:
    logger.info("content_agent.plan_today running")
    # Placeholder — the scheduler already fires slots individually via fire_slot.
    # This hook is reserved for pre-generating AI captions ahead of time.


# =============================================================
# Called by APScheduler at each configured slot time
# =============================================================
def fire_slot(kind: str, source: str) -> None:
    """Build one piece of content and save it as ready_for_manual_post.

    kind:   "post" | "story" | "reel"
    source: "owner" | "nano_banana" | "trend" | "auto"
    """
    logger.info("fire_slot({}, {})", kind, source)

    # Stop early if we've already hit the daily cap for this type
    if kind == "post" and cq.count_today("post") >= settings.max_posts_per_day:
        logger.info("max posts for today already reached — skipping")
        return

    media_path = _pick_media(source)
    if not media_path:
        logger.warning("no media available in source={}", source)
        return

    # Generate AI caption for posts/reels; stories can go without
    caption = ""
    if kind in ("post", "reel"):
        description = _describe_media(media_path)
        goal = _goal_for(source)
        caption = ai_generator.generate_caption(
            content_type=kind,
            media_description=description,
            goal=goal,
        ) or ""

    # Upload to cloud (Supabase Storage) so it's accessible on the dashboard
    public_url = media_processor.sync_local_to_storage(media_path)

    # Save as ready_for_manual_post — owner will see it on the dashboard
    cq.enqueue(
        type_=kind,
        content_type=("owner" if source == "owner" else source),
        media_path=str(media_path),
        media_url=public_url,
        caption=caption,
        scheduled_at=datetime.now(timezone.utc),
        status="ready_for_manual_post",
        metadata={"source": source},
    )
    logger.success("Content saved as ready_for_manual_post ({}/{})", kind, source)


# =============================================================
# Helpers
# =============================================================
SUPPORTED = {".jpg", ".jpeg", ".png", ".mp4", ".mov"}


def _pick_media(source: str) -> Optional[Path]:
    """Pick the oldest unused media file from the source folder.
    If source is nano_banana and no files available, auto-generate one.
    """
    folder = _folder_for(source)
    if not folder.exists():
        folder.mkdir(parents=True, exist_ok=True)

    candidates: List[Path] = sorted(
        [p for p in folder.iterdir() if p.suffix.lower() in SUPPORTED and p.is_file()],
        key=lambda p: p.stat().st_mtime,
    )

    # If nano_banana and no files, generate one on the fly
    if not candidates and source == "nano_banana":
        logger.info("No nano_banana files — generating varied content on the fly")
        from modules.nano_banana import nano_banana
        path = nano_banana.generate_varied_content()
        if path:
            return path
        return None

    if not candidates:
        return None

    # Move it to a "used/" subfolder to avoid re-picking
    used = folder / "used"
    used.mkdir(exist_ok=True)
    chosen = candidates[0]
    new_path = used / chosen.name
    try:
        chosen.rename(new_path)
    except OSError:
        new_path = chosen  # fall back to original if rename fails (e.g. cross-device)
    return new_path


def _folder_for(source: str) -> Path:
    if source == "owner":
        return settings.uploads_dir
    if source == "nano_banana":
        return settings.nano_banana_dir
    return settings.generated_dir


def _goal_for(source: str) -> str:
    return {
        "owner":       "توعية",
        "nano_banana": "نصيحة",
        "trend":       "ترفيه",
    }.get(source, "توعية")


def _describe_media(local_path: Path) -> str:
    """Simple heuristic description for AI caption context."""
    hint = local_path.stem.replace("_", " ").replace("-", " ")
    ext = local_path.suffix.lower()
    if ext in {".jpg", ".jpeg", ".png"}:
        return f"صورة {hint}"
    return f"فيديو {hint}"
