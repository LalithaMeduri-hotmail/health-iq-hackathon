"""`MealPlannerAgent` (implementation-plan.md Section 4.2). Owner: D3.

Tools: `search_nutrition_rules`, `get_profile_preferences`. Output: `MealPlan`.
Guardrails: hard-block allergens; no supplement dosing; no calorie prescriptions for minors.
"""

from app.models.profile import MealPlan


async def run(payload: dict) -> MealPlan:
    raise NotImplementedError
