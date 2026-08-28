"""Unit tests for `services/blob.py` upload validation (backend.instructions.md upload safety)."""

import pytest

from app.errors import PayloadTooLargeError, UnsupportedMediaTypeError, ValidationError
from app.services.blob import MAX_UPLOAD_BYTES, upload_raw

_PDF_MAGIC = b"%PDF-1.4\n%demo content"


async def test_upload_raw_rejects_disallowed_extension() -> None:
    with pytest.raises(UnsupportedMediaTypeError):
        await upload_raw("user-1", "malware.exe", b"anything", consent_version="1.0")


async def test_upload_raw_rejects_magic_byte_mismatch() -> None:
    with pytest.raises(UnsupportedMediaTypeError):
        await upload_raw("user-1", "fake.pdf", b"not-a-real-pdf", consent_version="1.0")


async def test_upload_raw_rejects_oversized_file() -> None:
    oversized = _PDF_MAGIC + b"0" * (MAX_UPLOAD_BYTES + 1)
    with pytest.raises(PayloadTooLargeError):
        await upload_raw("user-1", "big.pdf", oversized, consent_version="1.0")


async def test_upload_raw_rejects_empty_file() -> None:
    with pytest.raises(ValidationError):
        await upload_raw("user-1", "empty.pdf", b"", consent_version="1.0")


async def test_upload_raw_accepts_valid_pdf_in_demo_mode(tmp_path, monkeypatch) -> None:
    import app.services.blob as blob_module

    monkeypatch.setattr(blob_module, "_LOCAL_STORE_ROOT", tmp_path)

    blob_path = await upload_raw("user-1", "prescription.pdf", _PDF_MAGIC, consent_version="1.0")

    assert blob_path.startswith("raw-uploads/user-1/")
    assert (tmp_path / blob_path).exists()
