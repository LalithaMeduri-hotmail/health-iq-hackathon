"""Blob upload/download (implementation-plan.md Section 1.1). Owner: D1.

Path convention `userId/{yyyy-mm}/{uuid}{ext}`. Enforce extension + MIME + magic-byte checks,
10 MB cap, allowlist `.jpg/.jpeg/.png/.pdf/.heic`; reject archives/SVG. Containers:
`raw-uploads`, `generated-pdfs`, `thumbnails` (see infra/modules/storage.bicep).

Demo/dev fallback: when `Settings.demo_mode` is true or no storage account is configured, files
are written under `<repo>/.local-blob-store/<container>/...` instead of Azure Blob Storage, so
the upload path stays exercisable without deployed infra.
"""

import uuid
from datetime import UTC, datetime
from pathlib import Path

from app.config import get_settings
from app.errors import PayloadTooLargeError, UnsupportedMediaTypeError, ValidationError

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf", ".heic"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
RAW_UPLOADS_CONTAINER = "raw-uploads"

_MAGIC_BYTE_CHECKS: dict[str, tuple[bytes, ...]] = {
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".pdf": (b"%PDF",),
}

_LOCAL_STORE_ROOT = Path(__file__).resolve().parents[3] / ".local-blob-store"


def _validate(filename: str, content: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise UnsupportedMediaTypeError(f"Extension {ext!r} is not allowed; allowed: {sorted(ALLOWED_EXTENSIONS)}")
    if len(content) > MAX_UPLOAD_BYTES:
        raise PayloadTooLargeError(f"Upload is {len(content)} bytes; cap is {MAX_UPLOAD_BYTES} bytes")
    if len(content) == 0:
        raise ValidationError("Uploaded file is empty")

    if ext == ".heic":
        # HEIC is an ISO-BMFF container: bytes[4:8] == b"ftyp" identifies the box, regardless of brand.
        if len(content) < 12 or content[4:8] != b"ftyp":
            raise UnsupportedMediaTypeError("File does not look like a valid HEIC container")
    else:
        signatures = _MAGIC_BYTE_CHECKS[ext]
        if not any(content.startswith(sig) for sig in signatures):
            raise UnsupportedMediaTypeError(f"File content does not match declared extension {ext!r}")
    return ext


async def upload_raw(user_id: str, filename: str, content: bytes, *, consent_version: str) -> str:
    """Validate and upload to `raw-uploads`, persisting consent metadata on the blob.

    Returns the blob path (`userId/{yyyy-mm}/{uuid}{ext}`).
    """
    ext = _validate(filename, content)
    yyyy_mm = datetime.now(UTC).strftime("%Y-%m")
    blob_name = f"{user_id}/{yyyy_mm}/{uuid.uuid4().hex}{ext}"
    metadata = {"consentVersion": consent_version}

    settings = get_settings()
    if settings.demo_mode or not settings.azure_storage_account_name:
        target = _LOCAL_STORE_ROOT / RAW_UPLOADS_CONTAINER / blob_name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return f"{RAW_UPLOADS_CONTAINER}/{blob_name}"

    from app.deps import get_blob_service_client

    client = get_blob_service_client()
    container = client.get_container_client(RAW_UPLOADS_CONTAINER)
    blob = container.get_blob_client(blob_name)
    await blob.upload_blob(content, overwrite=False, metadata=metadata)
    return f"{RAW_UPLOADS_CONTAINER}/{blob_name}"
