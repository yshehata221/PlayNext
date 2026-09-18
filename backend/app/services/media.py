"""
Cover images uploaded by the scanner (Xbox package logos etc.) live on disk
under backend/media/covers and are served at /media. Swap for S3 or similar
if this ever runs on more than one box.
"""
import base64
import binascii
import os
from pathlib import Path

from ..config import settings

# overridable, because the packaged desktop app can't write next to its .exe
MEDIA_DIR = Path(os.environ.get("MEDIA_DIR") or Path(__file__).resolve().parents[2] / "media")
COVERS = MEDIA_DIR / "covers"
EXT = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}


def save_cover(slug: str, b64: str, mime: str | None) -> str | None:
    ext = EXT.get(mime or "", None)
    if ext is None:
        return None
    try:
        data = base64.b64decode(b64, validate=True)
    except binascii.Error:
        return None
    COVERS.mkdir(parents=True, exist_ok=True)
    (COVERS / f"{slug}.{ext}").write_bytes(data)
    return f"{settings.public_api_url}/media/covers/{slug}.{ext}"
