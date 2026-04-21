"""Posting schedule configuration.

Owned by the `modules.scheduler` which reads these constants/helpers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from config.settings import settings


@dataclass(frozen=True)
class PostingSlot:
    time_hhmm: str          # "09:00"
    kind: str               # "post" | "story" | "reel"
    content_source: str     # "owner" | "nano_banana" | "trend" | "auto"


def daily_slots() -> List[PostingSlot]:
    """Build today's posting plan from settings.

    Morning  → 1 story + 1 post (owner or nano_banana)
    Noon     → 1 story (nano_banana tip)
    Evening  → 1 story + 1 post (owner or reel)
    """
    slots: List[PostingSlot] = []

    story_times = settings.story_times_list
    post_times = settings.post_times_list

    # Stories — one per configured story time
    for i, t in enumerate(story_times):
        source = "owner" if i == 0 else "nano_banana"
        slots.append(PostingSlot(time_hhmm=t, kind="story", content_source=source))

    # Posts — alternate owner / nano_banana
    for i, t in enumerate(post_times):
        source = "owner" if i % 2 == 0 else "nano_banana"
        slots.append(PostingSlot(time_hhmm=t, kind="post", content_source=source))

    return sorted(slots, key=lambda s: s.time_hhmm)


# Job cadence (seconds)
CADENCE = {
    "reply_loop":   30,        # DMs + comments polling
    "trend_loop":   60 * 60,   # every hour
    "publish_loop": 60,        # scheduler tick
    "analytics":    60 * 60 * 24,  # daily
    "weekly_report": 60 * 60 * 24 * 7,
}
