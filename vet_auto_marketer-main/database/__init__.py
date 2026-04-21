"""Database package — Supabase-backed persistence layer."""
from database.supabase_client import get_client, supabase
from database import content_queue, analytics

__all__ = ["get_client", "supabase", "content_queue", "analytics"]
