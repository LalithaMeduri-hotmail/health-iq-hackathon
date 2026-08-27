"""POST /api/v1/meal-plan/generate (implementation-plan.md Section 5.1).

Calls `MealPlannerAgent`, grounded via `rag/retrieve.py` against `idx-nutrition`. Hard-blocks
allergens before the LLM ever sees the request (see agents.instructions.md guardrails table).
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/meal-plan", tags=["meal-plan"])

# TODO: POST /generate - { reportId, preferences } -> MealPlan (app.models.profile.MealPlan)
