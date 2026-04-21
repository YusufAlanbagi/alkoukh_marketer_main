"""Dashboard routes — staff-facing content generation mini app.

The owner uses this dashboard to:
  1. Generate content (tip/story/trend images + AI captions)
  2. Review ready content
  3. Download images & copy captions for manual Instagram posting
  4. Upload custom content
  5. Browse detected trends
"""
from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from loguru import logger

from config.settings import settings
from database import content_queue as cq
from database.supabase_client import get_client
from modules import media_processor


TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(tags=["dashboard"])


# =============================================================
# Helpers
# =============================================================
def _stats() -> Dict[str, Any]:
    """Quick counts for the landing page."""
    return {
        "ready_count": cq.count_by_status("ready_for_manual_post"),
        "posted_count": cq.count_by_status("marked_as_posted"),
        "trends_today": cq.count_trends_today(),
        "images_week": cq.count_images_this_week(),
    }


# =============================================================
# Pages
# =============================================================
@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    stats = _stats()
    recent = cq.list_ready(limit=5)
    posted = cq.list_posted(limit=5)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "stats": stats,
            "recent": recent,
            "posted": posted,
            "clinic": settings.clinic_name,
        },
    )


@router.get("/generate", response_class=HTMLResponse)
async def generate_page(request: Request):
    return templates.TemplateResponse(
        "generate.html",
        {"request": request, "clinic": settings.clinic_name},
    )


@router.post("/generate/tip")
async def generate_tip(request: Request):
    """Generate a tip image + AI caption."""
    from modules.nano_banana import nano_banana, VET_TIP_TOPICS
    from modules import ai_generator
    import random

    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    fmt = body.get("format", "post") if body else "post"
    custom_topic = body.get("topic", "").strip() if body else ""
    topic = custom_topic or random.choice(VET_TIP_TOPICS)

    image_path = nano_banana.generate_tip_image(topic, content_format=fmt)
    if not image_path:
        raise HTTPException(500, nano_banana.last_error or "فشل توليد الصورة.")

    caption = ai_generator.generate_caption(
        content_type=fmt,
        media_description=f"نصيحة بيطرية عن: {topic}",
        goal="نصيحة",
    )

    # Sync to cloud
    public_url = media_processor.sync_local_to_storage(image_path)

    item = cq.enqueue(
        type_=fmt,
        content_type="nano_banana",
        media_path=str(image_path),
        media_url=public_url,
        caption=caption,
        status="ready_for_manual_post",
        metadata={"source": "dashboard_generate", "topic": topic},
    )
    return JSONResponse({
        "ok": True,
        "item": item,
        "image_path": str(image_path),
        "caption": caption,
        "topic": topic,
    })


@router.post("/generate/trend")
async def generate_trend(request: Request):
    """Generate trend-based content."""
    from modules.nano_banana import nano_banana
    from modules import ai_generator

    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    fmt = body.get("format", "post") if body else "post"
    trend = (body.get("trend", "").strip() if body else "")
    if not trend:
        raise HTTPException(400, "يجب تحديد موضوع الترند")

    analysis = ai_generator.analyze_trend(
        trend_topic=trend,
        trend_volume=0,
        trend_type="dashboard",
    )

    caption = analysis.caption if analysis.relevant else ""
    if not caption:
        caption = ai_generator.generate_caption(
            content_type=fmt,
            media_description=f"محتوى مرتبط بترند: {trend}",
            goal="ترفيه",
        )

    image_path = nano_banana.generate_trend_image(trend, caption, content_format=fmt)
    if not image_path:
        raise HTTPException(500, nano_banana.last_error or "فشل توليد صورة الترند.")

    # Sync to cloud
    public_url = media_processor.sync_local_to_storage(image_path)

    item = cq.enqueue(
        type_=fmt,
        content_type="nano_banana",
        media_path=str(image_path),
        media_url=public_url,
        caption=caption,
        status="ready_for_manual_post",
        metadata={"source": "dashboard_generate", "trend": trend},
    )
    return JSONResponse({
        "ok": True,
        "item": item,
        "image_path": str(image_path),
        "caption": caption,
    })


@router.post("/generate/daily")
async def generate_daily(request: Request):
    """Generate daily life / behind-the-scenes content."""
    from modules.nano_banana import nano_banana, DAILY_LIFE_THEMES
    from modules import ai_generator
    import random

    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    fmt = body.get("format", "post") if body else "post"
    custom_theme = body.get("topic", "").strip() if body else ""
    theme = custom_theme or random.choice(DAILY_LIFE_THEMES)

    image_path = nano_banana.generate_daily_life_image(theme, content_format=fmt)
    if not image_path:
        raise HTTPException(500, nano_banana.last_error or "فشل توليد صورة يوميات العيادة.")

    caption = ai_generator.generate_caption(
        content_type=fmt,
        media_description=f"يوميات العيادة: {theme}",
        goal="يوميات",
    )

    public_url = media_processor.sync_local_to_storage(image_path)

    item = cq.enqueue(
        type_=fmt,
        content_type="nano_banana",
        media_path=str(image_path),
        media_url=public_url,
        caption=caption,
        status="ready_for_manual_post",
        metadata={"source": "dashboard_generate", "theme": theme},
    )
    return JSONResponse({
        "ok": True,
        "item": item,
        "image_path": str(image_path),
        "caption": caption,
        "topic": theme,
    })


@router.post("/generate/emotional")
async def generate_emotional(request: Request):
    """Generate emotional/heartwarming content."""
    from modules.nano_banana import nano_banana, EMOTIONAL_THEMES
    from modules import ai_generator
    import random

    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    fmt = body.get("format", "post") if body else "post"
    custom_theme = body.get("topic", "").strip() if body else ""
    theme = custom_theme or random.choice(EMOTIONAL_THEMES)

    image_path = nano_banana.generate_emotional_image(theme, content_format=fmt)
    if not image_path:
        raise HTTPException(500, nano_banana.last_error or "فشل توليد الصورة العاطفية.")

    caption = ai_generator.generate_caption(
        content_type=fmt,
        media_description=f"محتوى عاطفي: {theme}",
        goal="عاطفي",
    )

    public_url = media_processor.sync_local_to_storage(image_path)

    item = cq.enqueue(
        type_=fmt,
        content_type="nano_banana",
        media_path=str(image_path),
        media_url=public_url,
        caption=caption,
        status="ready_for_manual_post",
        metadata={"source": "dashboard_generate", "theme": theme},
    )
    return JSONResponse({
        "ok": True,
        "item": item,
        "image_path": str(image_path),
        "caption": caption,
        "topic": theme,
    })


@router.post("/generate/service")
async def generate_service(request: Request):
    """Generate service showcase content."""
    from modules.nano_banana import nano_banana, SERVICE_TOPICS
    from modules import ai_generator
    import random

    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    fmt = body.get("format", "post") if body else "post"
    custom_service = body.get("topic", "").strip() if body else ""
    service = custom_service or random.choice(SERVICE_TOPICS)

    image_path = nano_banana.generate_service_image(service, content_format=fmt)
    if not image_path:
        raise HTTPException(500, nano_banana.last_error or "فشل توليد صورة الخدمة.")

    caption = ai_generator.generate_caption(
        content_type=fmt,
        media_description=f"عرض خدمة بيطرية: {service}",
        goal="خدمة",
    )

    public_url = media_processor.sync_local_to_storage(image_path)

    item = cq.enqueue(
        type_=fmt,
        content_type="nano_banana",
        media_path=str(image_path),
        media_url=public_url,
        caption=caption,
        status="ready_for_manual_post",
        metadata={"source": "dashboard_generate", "service": service},
    )
    return JSONResponse({
        "ok": True,
        "item": item,
        "image_path": str(image_path),
        "caption": caption,
        "topic": service,
    })


@router.get("/ready", response_class=HTMLResponse)
async def ready_page(request: Request):
    items = cq.list_ready(limit=50)
    return templates.TemplateResponse(
        "ready.html",
        {"request": request, "items": items, "clinic": settings.clinic_name},
    )


@router.get("/download/{item_id}")
async def download_item(item_id: int):
    """Download the image file for a content item."""
    item = cq.get_item(item_id)
    if not item:
        raise HTTPException(404, "محتوى غير موجود")

    path_str = item.get("media_path") or item.get("image_local_path")
    if not path_str:
        raise HTTPException(404, "لا يوجد ملف للتحميل")

    path = Path(path_str)
    if not path.exists():
        raise HTTPException(404, f"الملف غير موجود: {path.name}")

    return FileResponse(
        path=str(path),
        filename=path.name,
        media_type="image/jpeg" if path.suffix.lower() in {".jpg", ".jpeg"} else "image/png",
    )


@router.get("/caption/{item_id}")
async def get_caption(item_id: int):
    """Return the caption for clipboard copy."""
    item = cq.get_item(item_id)
    if not item:
        raise HTTPException(404, "محتوى غير موجود")
    return JSONResponse({"caption": item.get("caption", "")})


@router.post("/queue/{item_id}/posted")
async def mark_posted(item_id: int):
    """Mark content as manually posted."""
    cq.mark_as_posted(item_id)
    return {"ok": True, "id": item_id}


@router.delete("/queue/{item_id}")
async def delete_queue_item(item_id: int):
    """Delete a content item from the queue."""
    cq.delete_item(item_id)
    return {"ok": True, "id": item_id}


@router.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request):
    return templates.TemplateResponse(
        "upload.html",
        {"request": request, "clinic": settings.clinic_name},
    )


@router.post("/upload")
async def upload_submit(
    request: Request,
    file: UploadFile = File(...),
    kind: str = Form("post"),
    caption: str = Form(""),
    generate_caption: bool = Form(False),
):
    if kind not in ("post", "story", "reel"):
        raise HTTPException(400, "kind must be post/story/reel")

    # 1. Save locally
    uploads = settings.uploads_dir
    uploads.mkdir(parents=True, exist_ok=True)
    safe_name = f"{int(datetime.now(timezone.utc).timestamp())}_{Path(file.filename or 'upload').name}"
    local_path = uploads / safe_name
    with open(local_path, "wb") as f:
        f.write(await file.read())

    # 2. Optionally generate AI caption
    final_caption = caption
    if generate_caption or not caption.strip():
        from modules import ai_generator
        final_caption = ai_generator.generate_caption(
            content_type=kind,
            media_description=f"صورة مرفوعة يدوياً: {Path(file.filename or '').stem}",
            goal="توعية",
        ) or caption

    # Sync to cloud
    public_url = media_processor.sync_local_to_storage(local_path)

    # 3. Enqueue as ready_for_manual_post
    cq.enqueue(
        type_=kind,
        content_type="owner",
        media_path=str(local_path),
        media_url=public_url,
        caption=final_caption or None,
        status="ready_for_manual_post",
        metadata={"source": "dashboard_upload"},
    )
    return RedirectResponse(url="/dashboard/ready", status_code=303)


@router.get("/edit", response_class=HTMLResponse)
async def edit_page(request: Request):
    return templates.TemplateResponse(
        "edit.html",
        {"request": request, "clinic": settings.clinic_name},
    )


@router.post("/edit")
async def edit_submit(
    request: Request,
    file: UploadFile = File(...),
    instruction: str = Form(...),
    kind: str = Form("post"),
):
    """Upload an image + Arabic instruction. Claude translates it to a pro
    English prompt, then Nano Banana edits the image (image-to-image).
    """
    from modules.nano_banana import nano_banana
    from modules import ai_generator

    if not instruction.strip():
        raise HTTPException(400, "اكتب تعليمات التعديل أولاً")

    if kind not in ("post", "story", "reel"):
        kind = "post"
    aspect = "9:16" if kind == "story" else "1:1"

    # 1. Save uploaded image locally
    uploads = settings.uploads_dir
    uploads.mkdir(parents=True, exist_ok=True)
    safe_name = f"edit_src_{int(datetime.now(timezone.utc).timestamp())}_{Path(file.filename or 'upload').name}"
    local_src = uploads / safe_name
    with open(local_src, "wb") as f:
        f.write(await file.read())

    # 2. Upload to public storage so Nano Banana can access it
    public_url = media_processor.sync_local_to_storage(local_src)
    if not public_url:
        raise HTTPException(500, "فشل رفع الصورة للتخزين السحابي — تأكد من إعداد Supabase Storage bucket 'media' (public)")

    # 3. Claude: Arabic instruction → professional English prompt
    try:
        english_prompt = ai_generator.translate_edit_instruction(instruction.strip())
        logger.info("Edit prompt translated: {}", english_prompt[:120])
    except Exception as e:
        logger.exception("prompt translation failed: {}", e)
        english_prompt = instruction.strip()

    # 4. Send to Nano Banana for image-to-image edit
    edited_path = nano_banana.edit_image(public_url, english_prompt, aspect_ratio=aspect)
    if not edited_path:
        raise HTTPException(500, nano_banana.last_error or "فشل تعديل الصورة")

    # 5. Upload edited image + enqueue
    edited_public_url = media_processor.sync_local_to_storage(edited_path)
    item = cq.enqueue(
        type_=kind,
        content_type="edited",
        media_path=str(edited_path),
        media_url=edited_public_url,
        caption=None,
        status="ready_for_manual_post",
        metadata={
            "source": "dashboard_edit",
            "instruction_ar": instruction.strip(),
            "prompt_en": english_prompt,
            "source_image": public_url,
        },
    )
    return JSONResponse({
        "ok": True,
        "item": item,
        "english_prompt": english_prompt,
        "image_path": str(edited_path),
    })


@router.get("/trends", response_class=HTMLResponse)
async def trends_page(request: Request):
    trends = cq.list_trends_today(limit=30)
    return templates.TemplateResponse(
        "trends.html",
        {"request": request, "trends": trends, "clinic": settings.clinic_name},
    )


# =============================================================
# JSON endpoints
# =============================================================
@router.get("/api/stats")
async def stats_json() -> JSONResponse:
    return JSONResponse(_stats())


# =============================================================
# Serve generated images (for preview in dashboard)
# =============================================================
@router.get("/media/{filename:path}")
async def serve_media(filename: str):
    """Serve images from content directories for dashboard preview."""
    # Check nano_banana dir first, then uploads, then generated
    for base_dir in [settings.nano_banana_dir, settings.uploads_dir, settings.generated_dir]:
        path = base_dir / filename
        if path.exists() and path.is_file():
            suffix = path.suffix.lower()
            media_type = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".mp4": "video/mp4",
                ".mov": "video/quicktime",
            }.get(suffix, "application/octet-stream")
            return FileResponse(str(path), media_type=media_type)

    # Also check "used" subdirectories
    for base_dir in [settings.nano_banana_dir, settings.uploads_dir, settings.generated_dir]:
        used_path = base_dir / "used" / filename
        if used_path.exists() and used_path.is_file():
            suffix = used_path.suffix.lower()
            media_type = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
            }.get(suffix, "application/octet-stream")
            return FileResponse(str(used_path), media_type=media_type)

    raise HTTPException(404, "ملف غير موجود")
