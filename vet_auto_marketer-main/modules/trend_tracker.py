"""Iraqi trend tracker.

Priority of sources:
  1. Twitter/X API (if TWITTER_BEARER_TOKEN is set)
  2. Scraping trends24.in/iraq/ (public, no auth)
  3. Seasonal vet-topic fallback (hardcoded) so the trend agent never starves
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

import requests
from bs4 import BeautifulSoup
from loguru import logger

from config.settings import settings


@dataclass
class Trend:
    topic: str
    volume: int
    source: str  # "twitter" | "trends24" | "seasonal"
    trend_type: str = "general"


# -------------------------------------------------------------
# Public entry point
# -------------------------------------------------------------
def fetch_iraqi_trends(limit: int = 15) -> List[Trend]:
    """Return best available Iraqi trends. Never raises — always returns a list."""

    # 1. Twitter
    if settings.twitter_bearer_token:
        trends = _fetch_twitter(limit)
        if trends:
            return trends

    # 2. Scraper
    trends = _scrape_trends24(limit)
    if trends:
        return trends

    # 3. Seasonal fallback
    logger.debug("falling back to seasonal vet topics")
    return _seasonal_topics(limit)


# -------------------------------------------------------------
# Source 1 — Twitter
# -------------------------------------------------------------
def _fetch_twitter(limit: int) -> List[Trend]:
    try:
        import tweepy
        auth = tweepy.OAuth2BearerHandler(settings.twitter_bearer_token)
        api = tweepy.API(auth)
        raw = api.get_place_trends(id=settings.trend_woeid)
        trends: List[Trend] = []
        for item in raw[0].get("trends", [])[:limit]:
            trends.append(Trend(
                topic=item.get("name") or "",
                volume=item.get("tweet_volume") or 0,
                source="twitter",
                trend_type="hashtag" if item.get("name", "").startswith("#") else "phrase",
            ))
        logger.info("fetched {} Iraqi trends from twitter", len(trends))
        return trends
    except Exception as e:
        logger.warning("twitter trend fetch failed: {}", e)
        return []


# -------------------------------------------------------------
# Source 2 — trends24.in scraper
# -------------------------------------------------------------
def _scrape_trends24(limit: int) -> List[Trend]:
    url = "https://trends24.in/iraq/"
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Vet_Auto_Marketer)"},
            timeout=15,
        )
        if resp.status_code != 200:
            logger.warning("trends24 returned {}", resp.status_code)
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
        trends: List[Trend] = []
        # trends24 uses .trend-card__list a for trend items
        for a in soup.select(".trend-card__list a")[:limit]:
            name = a.get_text(strip=True)
            if not name:
                continue
            volume = 0
            count_attr = a.get("data-tweet-count") or a.get_text()
            try:
                # Sometimes the link text contains "1.2K" — extract digits
                digits = "".join(c for c in str(count_attr) if c.isdigit())
                volume = int(digits) if digits else 0
            except ValueError:
                volume = 0
            trends.append(Trend(
                topic=name,
                volume=volume,
                source="trends24",
                trend_type="hashtag" if name.startswith("#") else "phrase",
            ))
            if len(trends) >= limit:
                break
        if trends:
            logger.info("scraped {} Iraqi trends from trends24", len(trends))
        return trends
    except Exception as e:
        logger.warning("trends24 scrape failed: {}", e)
        return []


# -------------------------------------------------------------
# Source 3 — seasonal vet topics (always-available)
# -------------------------------------------------------------
SEASONAL_VET_TOPICS = {
    # month -> list of topics
    1:  ["التدفئة للحيوانات بالشتاء", "تغذية الكلاب بالبرد"],
    2:  ["موسم تزاوج القطط", "العناية بالفراء بالشتاء"],
    3:  ["فحص الربيع السنوي", "تطعيمات الربيع"],
    4:  ["البراغيث والقراد بالربيع", "حساسية الربيع عند الكلاب"],
    5:  ["ضربة الشمس", "المشي الصباحي للكلاب"],
    6:  ["الجفاف عند الحيوانات", "تبريد الحيوانات بالصيف"],
    7:  ["الحرّ الشديد", "رعاية القطط بالصيف"],
    8:  ["الحرّ والجفاف", "السفر مع الحيوان"],
    9:  ["استعداد الحيوانات للخريف", "تساقط الشعر الموسمي"],
    10: ["موسم البرد والانفلونزا الحيوانية", "تطعيمات الخريف"],
    11: ["العناية بالجراء", "تغذية الشتاء"],
    12: ["نصائح العطل", "سلامة الحيوان خلال الأعياد"],
}
ALWAYS_ON_TOPICS = [
    "تطعيم الحيوانات الأليفة",
    "نصائح تغذية سليمة للقطط",
    "نصائح تغذية سليمة للكلاب",
    "علامات المرض المبكرة",
    "العناية بأسنان الحيوان",
    "تعقيم وخصي الحيوانات",
]


def _seasonal_topics(limit: int) -> List[Trend]:
    month = datetime.now().month
    topics = SEASONAL_VET_TOPICS.get(month, []) + ALWAYS_ON_TOPICS
    return [
        Trend(topic=t, volume=0, source="seasonal", trend_type="vet")
        for t in topics[:limit]
    ]


# -------------------------------------------------------------
# Filtering helpers (used by trend_agent)
# -------------------------------------------------------------
BLOCKED_KEYWORDS = {
    "سياس", "حزب", "انتخاب", "حرب", "طائف", "صدام", "مقتدى",
    "إسرائيل", "غزة", "ترامب", "بايدن",
}
PET_RELEVANT_KEYWORDS = {
    "قط", "قطط", "كلب", "كلاب", "حيوان", "حيوانات", "طيور",
    "أسد", "نمر", "خيل", "طير", "حشر", "بيطر",
    "pet", "cat", "dog", "animal", "vet",
}


def pre_filter(trend: Trend) -> Optional[str]:
    """Return a skip-reason or None."""
    t = trend.topic.lower()
    if any(b in t for b in BLOCKED_KEYWORDS):
        return "blocked_keyword"
    if len(trend.topic) < 3:
        return "too_short"
    return None


def score_pet_affinity(trend: Trend) -> int:
    """0-100 heuristic. Seasonal vet topics start high, others start low."""
    if trend.source == "seasonal":
        return 95
    t = trend.topic.lower()
    if any(k in t for k in PET_RELEVANT_KEYWORDS):
        return 90
    if trend.volume and trend.volume > 10_000:
        return 30
    return 10
