"""Blob upload/download (implementation-plan.md Section 1.1). Owner: D1.

Path convention `userId/{yyyy-mm}/{uuid}{ext}`. Enforce extension + MIME + magic-byte checks,
10 MB cap, allowlist `.jpg/.jpeg/.png/.pdf/.heic`; reject archives/SVG. Containers:
`raw-uploads`, `generated-pdfs`, `thumbnails` (see infra/modules/storage.bicep).
"""

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf", ".heic"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


async def upload_raw(user_id: str, filename: str, content: bytes, *, consent_version: str) -> str:
    """Validate and upload to `raw-uploads`, persisting consent metadata on the blob.

    Returns the blob path (`userId/{yyyy-mm}/{uuid}{ext}`).
    """
    raise NotImplementedError
