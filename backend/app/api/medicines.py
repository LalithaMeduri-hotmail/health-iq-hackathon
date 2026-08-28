"""POST /api/v1/medicines/alternatives (implementation-plan.md Section 5.1).

Calls `services/normalize_medicine.py` alternative-matching rules (Section 2.3) grounded via
`rag/retrieve.py` against `idx-medicines`.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request

from app.agents import safety_agent
from app.deps import CurrentUser, get_current_user
from app.models.common import ApiResponse, SafetyBlock
from app.models.medicine import MedicineEntity, MedicinesAlternativesRequest, MedicinesAlternativesResponse
from app.services.normalize_medicine import find_alternatives

router = APIRouter(prefix="/api/v1/medicines", tags=["medicines"])


@router.post("/alternatives")
async def alternatives(
    request: Request,
    body: MedicinesAlternativesRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> ApiResponse[MedicinesAlternativesResponse]:
    """`{ items[] }` -> `{ alternatives[], unmatched[] }`. Pure function of `items[]` (idempotent)."""
    alternatives_found: list[dict] = []
    unmatched: list[str] = []

    for query in body.items:
        probe = MedicineEntity(
            lineId="probe",
            rawText="",
            brandName=query.brand_name,
            activeIngredient=query.active_ingredient,
            strengthValue=query.strength_value,
            strengthUnit=query.strength_unit,
            dosageForm=query.dosage_form,
        )
        matches = find_alternatives(probe)
        if matches:
            alternatives_found.extend(matches)
        else:
            unmatched.append(f"{query.brand_name or query.active_ingredient} {query.strength_value}{query.strength_unit}")

    data = MedicinesAlternativesResponse(alternatives=alternatives_found, unmatched=unmatched)
    verdict = safety_agent.review(data.model_dump(by_alias=True))
    safety = SafetyBlock(pass_=verdict.passed, notes=verdict.violations, reviewer_version="safety-1.0.0")

    return ApiResponse(
        request_id=getattr(request.state, "request_id", str(uuid.uuid4())),
        generated_at=datetime.now(UTC),
        safety=safety,
        data=data,
    )
