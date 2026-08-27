"""POST /api/v1/prescriptions/analyze, /confirm (implementation-plan.md Section 5.1).

Calls `PrescriptionAnalyzerAgent` (agents/) and `services/ocr.py`, `normalize_medicine.py`.
Keep handlers thin: validate input, call a service/agent, shape the `ApiResponse` envelope.
"""

from fastapi import APIRouter, Depends

from app.deps import CurrentUser, get_current_user

router = APIRouter(prefix="/api/v1/prescriptions", tags=["prescriptions"])

# TODO: POST /analyze - multipart `file` + `consent=true` -> { runId, items[], ocrConfidence,
#       needsConfirmation[], disclaimers[] }
# TODO: POST /confirm - { runId, corrections[] } -> updated items[]


@router.get("/_ping")
async def ping(current_user: CurrentUser = Depends(get_current_user)) -> dict[str, str]:
    """Placeholder route so the router is exercised until the real endpoints land."""
    return {"status": "not-implemented", "userId": current_user.user_id}
