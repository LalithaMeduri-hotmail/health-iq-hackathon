"""`SpecialistAdvisorAgent` (implementation-plan.md Section 4.2). Owner: D3.

Tools: `search_specialist_mapping`, `get_doctor_links`. Output: `SpecialistGuidance`.
Guardrails: category only; no named-doctor endorsement; links flagged public/demo data.
"""

from app.models.profile import SpecialistGuidance


async def run(payload: dict) -> SpecialistGuidance:
    raise NotImplementedError
