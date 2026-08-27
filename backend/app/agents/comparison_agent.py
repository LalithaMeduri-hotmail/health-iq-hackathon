"""`ComparisonAgent` (implementation-plan.md Section 4.2). Owner: D3.

Tools: `load_report`, `align_parameters`, `classify_change` (deterministic, `services/comparison.py`).
Output: `ComparisonResult`. The LLM writes only the narrative; classification is pure Python.
"""

from app.models.report import ComparisonResult


async def run(payload: dict) -> ComparisonResult:
    raise NotImplementedError
