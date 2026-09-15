"""POST /api/v1/prescriptions/analyze, /confirm (implementation-plan.md Section 5.1).

Calls `PrescriptionAnalyzerAgent` (agents/) and `services/ocr.py`, `normalize_medicine.py`.
Keep handlers thin: validate input, call a service/agent, shape the `ApiResponse` envelope.
"""

import json
import statistics
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile

from app.agents import orchestrator, safety_agent
from app.config import get_settings
from app.deps import CurrentUser, get_current_user
from app.errors import LowConfidenceOcrError, ValidationError, WrongDocumentTypeError
from app.models.common import DISCLAIMER_TEXT, ApiResponse, SafetyBlock
from app.models.medicine import (
    ManualMedicineInput,
    MedicineEntity,
    PrescriptionAnalyzeResponse,
    PrescriptionConfirmRequest,
    PrescriptionConfirmResponse,
)
from app.repositories import cosmos_repo
from app.services import blob, deidentify, document_type
from app.services.normalize_medicine import apply_correction
from app.services.ocr import OcrEnvelope, OcrLine
from app.services.ocr import extract as ocr_extract

router = APIRouter(prefix="/api/v1/prescriptions", tags=["prescriptions"])


def _envelope(request: Request, safety: SafetyBlock, data) -> ApiResponse:
    return ApiResponse(
        request_id=getattr(request.state, "request_id", str(uuid.uuid4())),
        generated_at=datetime.now(UTC),
        safety=safety,
        data=data,
    )


@router.post("/analyze")
async def analyze(
    request: Request,
    consent: bool = Form(...),
    file: UploadFile | None = File(default=None),
    manual_medicines: str | None = Form(default=None, alias="manualMedicines"),
    current_user: CurrentUser = Depends(get_current_user),
) -> ApiResponse[PrescriptionAnalyzeResponse]:
    """Multipart `file` (optional) + `consent=true` + `manualMedicines` (optional JSON array).

    Manual entries bypass OCR entirely (NFR1.6 fallback); at least one input source is required.
    """
    if not consent:
        raise ValidationError("consent must be true before any upload is processed")
    if file is None and not manual_medicines:
        raise ValidationError("Provide a prescription file or at least one manual medicine entry")

    manual_lines: list[OcrLine] = []
    unverified_type = False
    if manual_medicines:
        try:
            raw_entries = json.loads(manual_medicines)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"manualMedicines must be valid JSON: {exc}") from exc
        manual_inputs = [ManualMedicineInput.model_validate(entry) for entry in raw_entries]
        manual_lines = [OcrLine(text=entry.raw_text, confidence=1.0, bbox=[]) for entry in manual_inputs]

    blob_path: str | None = None
    file_lines: list[OcrLine] = []
    handwritten_ratio = 0.0
    detected_patient_name: str | None = None
    if file is not None:
        content = await file.read()
        blob_path = await blob.upload_raw(
            current_user.user_id, file.filename or "upload", content, consent_version="1.0"
        )
        file_envelope = await ocr_extract(content, mode="read")

        if file_envelope.was_read:
            kind = document_type.classify(
                document_type.text_of(
                    [line.text for line in file_envelope.lines], file_envelope.tables
                )
            )
            if kind != "prescription":
                raise WrongDocumentTypeError(
                    "This does not look like a prescription. Upload a prescription or tablet strip "
                    "here, and use Report Comparison or Health Profile for a lab report."
                )
        elif not get_settings().demo_mode:
            # Nothing read the bytes, so claiming this is a prescription would be a guess.
            raise WrongDocumentTypeError(
                "This upload could not be read, so we cannot confirm it is a prescription. "
                "Upload a PDF, or enter the medicines manually."
            )
        else:
            unverified_type = True

        file_lines = file_envelope.lines
        handwritten_ratio = file_envelope.handwritten_ratio
        detected_patient_name = deidentify.find_patient_name(
            "\n".join(line.text for line in file_lines)
        )

    combined_envelope = OcrEnvelope(
        pages=1, lines=file_lines + manual_lines, tables=[], handwritten_ratio=handwritten_ratio
    )

    result = await orchestrator.run("prescription", {"ocr_envelope": combined_envelope})
    analysis = result.data

    run_id = f"run-{uuid.uuid4().hex[:12]}"
    await cosmos_repo.record_run(
        current_user.user_id,
        run_id,
        {
            "type": "prescription",
            "blobPath": blob_path,
            "items": [item.model_dump(by_alias=True) for item in analysis.items],
            "toolCalls": ["ocr_extract", "normalize_medicine"],
            "agentVersions": {"prescription": "1.0.0", "safety": "safety-1.0.0"},
            "safety": {"pass": result.safety_pass, "violations": result.safety_notes},
            "createdAt": datetime.now(UTC).isoformat(),
        },
    )

    needs_confirmation = [item for item in analysis.items if item.needs_user_confirmation]
    ocr_confidence = (
        statistics.mean(line.confidence for line in combined_envelope.lines) if combined_envelope.lines else 1.0
    )

    if needs_confirmation:
        errors = [
            {"field": "runId", "issue": run_id},
            {"field": "items", "issue": json.dumps([item.model_dump(by_alias=True) for item in analysis.items])},
        ] + [
            {
                "field": f"items[{idx}].brandName",
                "issue": (
                    f"confidence {item.ocr_confidence:.2f} < gate"
                    if item.ocr_confidence is not None
                    else "low match confidence"
                ),
            }
            for idx, item in enumerate(analysis.items)
            if item.needs_user_confirmation
        ]
        raise LowConfidenceOcrError(
            f"{len(needs_confirmation)} token(s) fell below the confidence gate and require user confirmation.",
            errors=errors,
        )

    data = PrescriptionAnalyzeResponse(
        runId=run_id,
        blobPath=blob_path,
        ocrConfidence=round(ocr_confidence, 4),
        handwrittenRatio=handwritten_ratio,
        items=analysis.items,
        needsConfirmation=[],
        disclaimers=analysis.disclaimers,
        patientName=detected_patient_name,
    )
    notes = list(result.safety_notes)
    if unverified_type:
        notes.append("document-type-unverified")
    safety = SafetyBlock(pass_=result.safety_pass, notes=notes, reviewer_version="safety-1.0.0")
    return _envelope(request, safety, data)


@router.post("/confirm")
async def confirm(
    request: Request,
    body: PrescriptionConfirmRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> ApiResponse[PrescriptionConfirmResponse]:
    """`{ runId, corrections[] }` -> updated `items[]` with recomputed `matchScore`."""
    run_doc = await cosmos_repo.get_run(current_user.user_id, body.run_id)
    items = [MedicineEntity.model_validate(item) for item in run_doc["items"]]
    corrections_by_line = {c.line_id: c for c in body.corrections}

    updated_items = [
        apply_correction(item, corrections_by_line[item.line_id]) if item.line_id in corrections_by_line else item
        for item in items
    ]

    run_doc["items"] = [item.model_dump(by_alias=True) for item in updated_items]
    await cosmos_repo.record_run(current_user.user_id, body.run_id, run_doc)

    verdict = safety_agent.review({"items": run_doc["items"], "disclaimers": [DISCLAIMER_TEXT]})
    safety = SafetyBlock(pass_=verdict.passed, notes=verdict.violations, reviewer_version="safety-1.0.0")
    return _envelope(request, safety, PrescriptionConfirmResponse(items=updated_items))
