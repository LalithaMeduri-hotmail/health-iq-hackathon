"""POST /api/v1/meal-plan/generate (implementation-plan.md Section 5.1).

Calls `MealPlannerAgent`, grounded via `rag/retrieve.py` against `idx-nutrition`. Hard-blocks
allergens before the LLM ever sees the request (see agents.instructions.md guardrails table).
"""

import hashlib
import json
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request

from app.agents import orchestrator
from app.deps import CurrentUser, get_current_user
from app.errors import SafetyViolationError
from app.models.common import ApiResponse, SafetyBlock
from app.models.mealplan import MealPlan, MealPlanRequest
from app.repositories import cosmos_repo

router = APIRouter(prefix="/api/v1/meal-plan", tags=["meal-plan"])


@router.post("/generate")
async def generate(
	request: Request,
	body: MealPlanRequest,
	current_user: CurrentUser = Depends(get_current_user),  # noqa: B008
) -> ApiResponse[MealPlan]:
	"""Build a grounded meal plan for one caller-owned report."""
	profile = await cosmos_repo.get_profile(current_user.user_id)
	report = await cosmos_repo.get_report(current_user.user_id, body.report_id)
	allergies = sorted(set(profile.preferences.allergies) | set(body.preferences.allergies))

	result = await orchestrator.run(
		"meal-plan",
		{"report": report, "preferences": body.preferences, "allergies": allergies},
	)
	if not result.safety_pass:
		raise SafetyViolationError(
			"Safety review blocked this meal plan",
			errors=[{"field": "safety", "issue": note} for note in result.safety_notes],
		)

	input_hash = hashlib.sha256(
		json.dumps(body.model_dump(by_alias=True), sort_keys=True).encode("utf-8")
	).hexdigest()
	await cosmos_repo.record_run(
		current_user.user_id,
		f"run-{uuid.uuid4().hex[:12]}",
		{
			"type": "meal-plan-generate",
			"reportId": report.id,
			"inputHash": input_hash,
			"toolCalls": ["load_profile", "load_report", "search_nutrition_rules"],
			"agentVersions": {"mealPlan": "1.0.0", "safety": "safety-1.0.0"},
			"safety": {"pass": result.safety_pass, "violations": result.safety_notes},
			"createdAt": datetime.now(UTC).isoformat(),
		},
	)

	return ApiResponse[MealPlan].model_validate(
		{
			"requestId": getattr(request.state, "request_id", str(uuid.uuid4())),
			"generatedAt": datetime.now(UTC),
			"safety": SafetyBlock.model_validate(
				{
					"pass": result.safety_pass,
					"notes": result.safety_notes,
					"reviewerVersion": "safety-1.0.0",
				}
			),
			"data": result.data,
		}
	)
