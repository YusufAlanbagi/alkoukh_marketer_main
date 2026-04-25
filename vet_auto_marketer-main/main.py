"""Vet_Auto_Marketer — main entry point.

Starts:
  1. Logging
  2. Supabase healthcheck (non-fatal)
  3. APScheduler background jobs
  4. FastAPI server with content generation dashboard
"""
from __future__ import annotations

import signal
import sys
from contextlib import asynccontextmanager
from typing import Any, Dict

import uvicorn
from fastapi import FastAPI, Depends, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from loguru import logger

from config.settings import settings
from dashboard import router as dashboard_router
from database.supabase_client import healthcheck as db_healthcheck
from modules import scheduler as sched


# =============================================================
# Logging
# =============================================================
def _setup_logging() -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:<7}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan> | {message}",
    )
    logger.add(
        settings.logs_dir / "app.log",
        level=settings.log_level,
        rotation="20 MB",
        retention="30 days",
        encoding="utf-8",
        enqueue=True,
    )


# =============================================================
# FastAPI app + lifespan (scheduler boot/shutdown tied to it)
# =============================================================
@asynccontextmanager
async def _lifespan(app: FastAPI):
    logger.info("🚀 Vet_Auto_Marketer starting up…")

    if settings.dry_run:
        logger.warning("DRY_RUN=true — content will be generated but not auto-scheduled")

    try:
        db_healthcheck()
    except Exception as e:
        logger.warning("DB healthcheck error (continuing): {}", e)

    try:
        sched.start()
    except Exception as e:
        logger.exception("Scheduler failed to start: {}", e)

    yield

    logger.info("🛑 Shutting down…")
    try:
        sched.shutdown()
    except Exception as e:
        logger.warning("Scheduler shutdown error: {}", e)


app = FastAPI(
    title="Vet_Auto_Marketer",
    description="أداة توليد محتوى لعيادة الكوخ البيطرية — Content Generation Tool",
    version="2.0.0",
    lifespan=_lifespan,
)

security = HTTPBasic()

def _authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    import secrets
    is_user_ok = secrets.compare_digest(credentials.username, settings.admin_username)
    is_pass_ok = secrets.compare_digest(credentials.password, settings.admin_password)
    if not (is_user_ok and is_pass_ok):
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# Staff dashboard (RTL mini app)
# Protected by Basic Auth
app.include_router(
    dashboard_router, 
    prefix="/dashboard",
    dependencies=[Depends(_authenticate)]
)


# =============================================================
# Health / root
# =============================================================
@app.get("/health")
async def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "version": "2.0.0",
        "mode": "content_generation",
        "dry_run": settings.dry_run,
        "clinic": settings.clinic_name,
    }


@app.get("/")
async def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/dashboard/")


# =============================================================
# Entry point
# =============================================================
def _install_signal_handlers() -> None:
    def _graceful(*_):
        logger.info("signal received — shutting down scheduler")
        try:
            sched.shutdown()
        finally:
            sys.exit(0)

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _graceful)
        except (ValueError, OSError):
            # SIGTERM not available on Windows in some contexts — ignore silently
            pass


def main() -> None:
    _setup_logging()
    _install_signal_handlers()
    logger.info("Vet_Auto_Marketer | clinic={} | tz={} | dry_run={}",
                settings.clinic_name, settings.timezone, settings.dry_run)

    uvicorn.run(
        "main:app",
        host=settings.webhook_host,
        port=settings.webhook_port,
        log_level=settings.log_level.lower(),
        reload=False,
    )


if __name__ == "__main__":
    main()
