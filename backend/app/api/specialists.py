"""POST /api/v1/specialists/suggest (docs/lld/3-low-level-design-*.md Section 2.3.4).

Calls `SpecialistAdvisorAgent` over the abnormal parameters of an already-stored report, so the
suggestion is a pure function of that report and carries no new PHI.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request

from app.agents import orchestrator
from app.deps import CurrentUser, get_current_user
from app.models.common import ApiResponse, SafetyBlock
from app.models.profile import SpecialistGuidance, SpecialistSuggestRequest
from app.models.report import ABNORMAL_STATUSES
from app.repositories import cosmos_repo

router = APIRouter(prefix="/api/v1/specialists", tags=["specialists"])


@router.post("/suggest")
async def suggest(
    request: Request,
    body: SpecialistSuggestRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> ApiResponse[SpecialistGuidance]:
    """`{ reportId }` -> specialty categories, grounded rationale, and public/demo doctor links."""
    report = await cosmos_repo.get_report(current_user.user_id, body.report_id)

    result = await orchestrator.run("specialist", {"parameters": report.parameters})
    abnormal_count = sum(
        1 for parameter in report.parameters if parameter.status in ABNORMAL_STATUSES
    )

    notes = list(result.safety_notes)
    if abnormal_count == 0:
        notes.append("no-abnormal-parameters-general-physician-guidance")

    await cosmos_repo.record_run(
        current_user.user_id,
        f"run-{uuid.uuid4().hex[:12]}",
        {
            "type": "specialist-suggest",
            "reportId": report.id,
            "abnormalCount": abnormal_count,
            "toolCalls": ["load_report", "search_specialist_mapping", "get_doctor_links"],
            "agentVersions": {"specialist": "1.0.0", "safety": "safety-1.0.0"},
            "safety": {"pass": result.safety_pass, "violations": result.safety_notes},
            "createdAt": datetime.now(UTC).isoformat(),
        },
    )

    safety = SafetyBlock(pass_=result.safety_pass, notes=notes, reviewer_version="safety-1.0.0")
    return ApiResponse(
        request_id=getattr(request.state, "request_id", str(uuid.uuid4())),
        generated_at=datetime.now(UTC),
        safety=safety,
        data=result.data,
    )
