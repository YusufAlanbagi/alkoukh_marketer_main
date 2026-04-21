"""Supabase client — single shared instance."""
from __future__ import annotations

from typing import Optional

from loguru import logger
from supabase import Client, create_client

from config.settings import settings


_client: Optional[Client] = None


def get_client() -> Client:
    """Return the shared Supabase client, creating it on first access."""
    global _client
    if _client is None:
        if not settings.supabase_url or not settings.supabase_key:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_KEY must be set in .env before using the DB."
            )
        _client = create_client(settings.supabase_url, settings.supabase_key)
        logger.info("Supabase client initialized ({})", settings.supabase_url)
    return _client


# Convenience proxy — lazy-resolved on attribute access.
class _SupabaseProxy:
    def __getattr__(self, item):
        return getattr(get_client(), item)


supabase = _SupabaseProxy()


def healthcheck() -> bool:
    """Quick connectivity probe — returns True if the client reaches Supabase."""
    try:
        get_client().table("content_queue").select("id").limit(1).execute()
        logger.success("Supabase connection OK")
        return True
    except Exception as e:
        logger.error("Supabase healthcheck failed: {}", e)
        return False


if __name__ == "__main__":
    healthcheck()
