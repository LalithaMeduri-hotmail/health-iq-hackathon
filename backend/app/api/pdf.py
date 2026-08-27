"""POST /api/v1/pdf/generate (implementation-plan.md Section 5.3).

Calls `services/pdf_builder.py` (ReportLab, 6 sections) and `services/blob.py` to persist the
generated PDF into the `generated-pdfs` container.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/pdf", tags=["pdf"])

# TODO: POST /generate - { runId } -> { pdfBlobUrl, shareId, expiresAt }
