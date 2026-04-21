"""Centralized settings loaded from environment variables.

All other modules should import `settings` from here.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = PROJECT_ROOT / "content"
LOGS_DIR = PROJECT_ROOT / "logs"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------- Anthropic ----------
    anthropic_api_key: str = Field("", alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field("claude-sonnet-4-5-20250929", alias="ANTHROPIC_MODEL")

    # ---------- Gemini ----------
    gemini_api_key: str = Field("", alias="GEMINI_API_KEY")
    gemini_model: str = Field("gemini-2.0-flash", alias="GEMINI_MODEL")

    # ---------- Groq ----------
    groq_api_key: str = Field("", alias="GROQ_API_KEY")
    groq_model: str = Field("llama-3.3-70b-versatile", alias="GROQ_MODEL")

    # ---------- Nano Banana ----------
    nano_banana_api_key: str = Field("", alias="NANO_BANANA_API_KEY")
    nano_banana_base_url: str = Field("https://api.nanobananaapi.ai", alias="NANO_BANANA_BASE_URL")

    # ---------- Supabase ----------
    supabase_url: str = Field("", alias="SUPABASE_URL")
    supabase_key: str = Field("", alias="SUPABASE_KEY")

    # ---------- Clinic ----------
    clinic_name: str = Field("الكوخ", alias="CLINIC_NAME")
    clinic_name_en: str = Field("ALKOUKH", alias="CLINIC_NAME_EN")
    clinic_phone: str = Field("", alias="CLINIC_PHONE")
    clinic_address: str = Field("بغداد - العراق", alias="CLINIC_ADDRESS")
    clinic_instagram: str = Field("@alkoukh.vet", alias="CLINIC_INSTAGRAM")
    clinic_working_hours: str = Field("10:00 - 22:00", alias="CLINIC_WORKING_HOURS")

    # ---------- Scheduling ----------
    timezone: str = Field("Asia/Baghdad", alias="TIMEZONE")
    post_times: str = Field("09:00,20:00", alias="POST_TIMES")
    story_times: str = Field("09:00,14:00,20:00", alias="STORY_TIMES")
    min_stories_per_day: int = Field(3, alias="MIN_STORIES_PER_DAY")
    max_posts_per_day: int = Field(3, alias="MAX_POSTS_PER_DAY")

    # ---------- Trends ----------
    twitter_bearer_token: str = Field("", alias="TWITTER_BEARER_TOKEN")
    trend_country: str = Field("Iraq", alias="TREND_COUNTRY")
    trend_woeid: int = Field(23424855, alias="TREND_WOEID")

    # ---------- Webhook ----------
    webhook_host: str = Field("0.0.0.0", alias="WEBHOOK_HOST")
    webhook_port: int = Field(8000, alias="WEBHOOK_PORT")

    # ---------- Admin / Security ----------
    admin_username: str = Field("admin", alias="ADMIN_USERNAME")
    admin_password: str = Field("alkoukh2026", alias="ADMIN_PASSWORD")

    # ---------- Flags ----------
    dry_run: bool = Field(False, alias="DRY_RUN")
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    # ---------- Derived / Paths ----------
    project_root: Path = PROJECT_ROOT
    content_dir: Path = CONTENT_DIR
    uploads_dir: Path = CONTENT_DIR / "uploads"
    nano_banana_dir: Path = CONTENT_DIR / "nano_banana"
    generated_dir: Path = CONTENT_DIR / "generated"
    logs_dir: Path = LOGS_DIR

    @field_validator("post_times", "story_times")
    @classmethod
    def _strip_times(cls, v: str) -> str:
        return ",".join(t.strip() for t in v.split(",") if t.strip())

    @property
    def post_times_list(self) -> List[str]:
        return [t for t in self.post_times.split(",") if t]

    @property
    def story_times_list(self) -> List[str]:
        return [t for t in self.story_times.split(",") if t]

    def ensure_dirs(self) -> None:
        for d in (self.content_dir, self.uploads_dir, self.nano_banana_dir,
                  self.generated_dir, self.logs_dir):
            d.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
