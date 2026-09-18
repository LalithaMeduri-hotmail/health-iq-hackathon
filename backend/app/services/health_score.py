"""Deterministic health-score arithmetic (LLD Section 2, NFR2.5).

Lives in `services/` because the score is ordinary Python that several callers need - the report
agent, the report detail route, and the patient-profile summary. Keeping it here stops a service
from having to reach upward into `agents/`, which the layering rules forbid. No LLM contributes
to any number produced in this module.
"""

from app.models.report import (
    ABNORMAL_STATUSES,
    HealthScoreBreakdown,
    LabParameter,
    ScorePenalty,
)

BASE_SCORE = 100.0
ABNORMAL_PENALTY = 8.0
CRITICAL_PENALTY = 15.0

SCORE_METHOD = (
    f"Every report starts at {BASE_SCORE:.0f}. Each value outside its typical range subtracts "
    f"{ABNORMAL_PENALTY:.0f} points, and each critically flagged value subtracts "
    f"{CRITICAL_PENALTY:.0f}. Values with no reference range on file are not counted. "
    "This is an educational indicator, not a diagnosis."
)


def is_abnormal(parameter: LabParameter) -> bool:
    return parameter.status in ABNORMAL_STATUSES


def score_breakdown(parameters: list[LabParameter]) -> HealthScoreBreakdown:
    """Deterministic 0-100 score plus the per-parameter deductions that produced it (NFR2.5)."""
    penalties = [
        ScorePenalty(
            canonicalKey=parameter.canonical_key,
            displayName=parameter.display_name,
            status=parameter.status,
            penalty=CRITICAL_PENALTY if parameter.status == "critical_flag" else ABNORMAL_PENALTY,
        )
        for parameter in parameters
        if is_abnormal(parameter)
    ]
    total_penalty = sum(penalty.penalty for penalty in penalties)

    return HealthScoreBreakdown(
        baseScore=BASE_SCORE,
        penalties=penalties,
        totalPenalty=total_penalty,
        healthScore=round(max(0.0, BASE_SCORE - total_penalty), 1),
        method=SCORE_METHOD,
    )


def health_score(parameters: list[LabParameter]) -> float:
    """Deterministic 0-100 score: every out-of-range value costs a fixed, explainable amount."""
    return score_breakdown(parameters).health_score
