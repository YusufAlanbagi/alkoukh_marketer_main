"""Media processing — validate/normalize images & videos before IG upload.

IG Graph API needs an HTTPS-accessible URL for the media. Local files must be
uploaded to a public bucket (e.g. Supabase Storage) first — see `upload_to_public_url`.
"""
from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from loguru import logger
from PIL import Image

from config.settings import settings
from database.supabase_client import get_client


# -------------------------------------------------------------
# Validation
# -------------------------------------------------------------
MAX_IMAGE_MB = 8
MAX_VIDEO_MB = 100
SUPPORTED_IMAGE = {".jpg", ".jpeg", ".png"}
SUPPORTED_VIDEO = {".mp4", ".mov"}


@dataclass
class MediaInfo:
    path: Path
    kind: str     # "image" | "video"
    width: int
    height: int
    size_mb: float


def inspect(path: str | Path) -> MediaInfo:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)

    size_mb = p.stat().st_size / (1024 * 1024)
    ext = p.suffix.lower()

    if ext in SUPPORTED_IMAGE:
        with Image.open(p) as im:
            w, h = im.size
        if size_mb > MAX_IMAGE_MB:
            raise ValueError(f"Image {p.name} is {size_mb:.1f}MB (max {MAX_IMAGE_MB}MB)")
        return MediaInfo(p, "image", w, h, size_mb)

    if ext in SUPPORTED_VIDEO:
        if size_mb > MAX_VIDEO_MB:
            raise ValueError(f"Video {p.name} is {size_mb:.1f}MB (max {MAX_VIDEO_MB}MB)")
        return MediaInfo(p, "video", 0, 0, size_mb)

    raise ValueError(f"Unsupported media type: {ext}")


# -------------------------------------------------------------
# Normalization — resize / recompress images for IG
# -------------------------------------------------------------
def normalize_image(src: str | Path, *, target: str = "post") -> Path:
    """Normalize image dimensions for the given IG target.

    target:
      - "post"  → 1080x1080 (1:1)
      - "story" → 1080x1920 (9:16)
      - "reel_cover" → 1080x1920
    """
    src_path = Path(src)
    if src_path.suffix.lower() not in SUPPORTED_IMAGE:
        raise ValueError("normalize_image only supports jpg/png")

    dims = {"post": (1080, 1080), "story": (1080, 1920), "reel_cover": (1080, 1920)}
    if target not in dims:
        raise ValueError(f"unknown target: {target}")
    target_w, target_h = dims[target]

    out_dir = settings.generated_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{src_path.stem}_{target}.jpg"

    with Image.open(src_path) as im:
        im = im.convert("RGB")
        im = _smart_fit(im, target_w, target_h)
        im.save(out_path, format="JPEG", quality=90, optimize=True)

    logger.info("normalized {} -> {} ({}x{})", src_path.name, out_path.name, target_w, target_h)
    return out_path


def _smart_fit(im: Image.Image, tw: int, th: int) -> Image.Image:
    """Fit image into (tw,th) canvas, centered, padded with white (brand background)."""
    im.thumbnail((tw, th), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (tw, th), (255, 255, 255))
    x = (tw - im.width) // 2
    y = (th - im.height) // 2
    canvas.paste(im, (x, y))
    return canvas


# -------------------------------------------------------------
# Upload local file → public URL (Supabase Storage bucket "media")
# -------------------------------------------------------------
def upload_to_public_url(local_path: str | Path, *, bucket: str = "media") -> str:
    """Upload a file to Supabase Storage and return its public URL."""
    p = Path(local_path)
    if not p.exists():
        raise FileNotFoundError(f"Local file not found: {p}")

    client = get_client()
    storage = client.storage.from_(bucket)
    
    # Create a unique remote name to avoid collisions
    timestamp = int(p.stat().st_mtime)
    remote_name = f"{p.stem}_{timestamp}{p.suffix}"

    mime, _ = mimetypes.guess_type(str(p))
    mime = mime or "application/octet-stream"

    logger.info("Uploading to Supabase: {} (bucket={})", p.name, bucket)
    try:
        with open(p, "rb") as f:
            # We use upsert=True to overwrite if needed, though name is unique
            storage.upload(
                path=remote_name,
                file=f,
                file_options={"content-type": mime, "upsert": "true"},
            )
    except Exception as e:
        logger.error("Supabase storage upload failed for {}: {}", p.name, e)
        # If it fails, we keep going but log it -- might be network or bucket config
        raise

    # Note: supabase-py's get_public_url is usually a simple string concatenation
    # ensuring it's public requires the bucket to be public in Supabase dashboard.
    public_url = storage.get_public_url(remote_name)
    logger.success("Uploaded successfully: {}", public_url)
    return public_url


def sync_local_to_storage(local_path: str | Path) -> Optional[str]:
    """Helper to sync a local file and return the public URL, with error handling."""
    try:
        return upload_to_public_url(local_path)
    except Exception as e:
        logger.warning("Auto-sync to cloud failed: {}", e)
        return None


# -------------------------------------------------------------
# Convenience: given a local file, prepare it for publishing.
# Returns a public URL usable by Instagram.
# -------------------------------------------------------------
def prepare_for_publish(local_path: str | Path, *, kind: str = "post") -> str:
    info = inspect(local_path)
    if info.kind == "image" and kind in ("post", "story", "reel_cover"):
        normalized = normalize_image(local_path, target=kind)
        return upload_to_public_url(normalized)
    
    return upload_to_public_url(local_path)


def describe_media_for_ai(local_path: str | Path) -> str:
    """Tiny heuristic description used when the AI writes a caption.

    Real deployments should plug in a vision model. For now we return a
    filename-based hint so captions have some context.
    """
    p = Path(local_path)
    hint = p.stem.replace("_", " ").replace("-", " ")
    info = inspect(p)
    if info.kind == "image":
        return f"صورة {hint} (بعرض {info.width}×{info.height})"
    return f"فيديو {hint}"
