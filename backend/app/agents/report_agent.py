"""`ReportAnalysisAgent` (implementation-plan.md Section 4.2). Owner: D3.

Tools: `ocr_layout`, `normalize_lab`, `lookup_reference_range`, `search_reference_explanations`.
Output: `ReportSummary`. Guardrails: use "possible concern"; never name a disease.
"""

from app.errors import NotFoundError
from app.models.report import (
    ABNORMAL_STATUSES,
    HealthScoreBreakdown,
    LabParameter,
    ReportSummary,
    ScorePenalty,
    SystemCard,
)
from app.services.reference_ranges import get_reference_range, get_source

# Organ/system grouping for the Health Profile cards (LLD Section 2).
SYSTEM_GROUPS: dict[str, tuple[str, ...]] = {
    "Blood sugar": ("glucose_fasting", "glucose_pp", "hba1c"),
    "Heart and lipids": ("ldl", "hdl", "triglycerides", "total_cholesterol"),
    "Kidney": ("creatinine", "urea"),
    "Liver": ("sgpt_alt", "sgot_ast"),
    "Thyroid": ("tsh",),
    "Blood count": ("hemoglobin", "wbc", "platelets"),
    "Vitamins": ("vitamin_d", "vitamin_b12"),
}

_BASE_SCORE = 100.0
_ABNORMAL_PENALTY = 8.0
_CRITICAL_PENALTY = 15.0
_GROUNDED_NOTE_LIMIT = 3
_OTHER_SYSTEM = "Other results"

_SCORE_METHOD = (
    f"Every report starts at {_BASE_SCORE:.0f}. Each value outside its typical range subtracts "
    f"{_ABNORMAL_PENALTY:.0f} points, and each critically flagged value subtracts "
    f"{_CRITICAL_PENALTY:.0f}. Values with no reference range on file are not counted. "
    "This is an educational indicator, not a diagnosis."
)


def _is_abnormal(parameter: LabParameter) -> bool:
    return parameter.status in ABNORMAL_STATUSES


def score_breakdown(parameters: list[LabParameter]) -> HealthScoreBreakdown:
    """Deterministic 0-100 score plus the per-parameter deductions that produced it (NFR2.5)."""
    penalties = [
        ScorePenalty(
            canonicalKey=parameter.canonical_key,
            displayName=parameter.display_name,
            status=parameter.status,
            penalty=_CRITICAL_PENALTY if parameter.status == "critical_flag" else _ABNORMAL_PENALTY,
        )
        for parameter in parameters
        if _is_abnormal(parameter)
    ]
    total_penalty = sum(penalty.penalty for penalty in penalties)

    return HealthScoreBreakdown(
        baseScore=_BASE_SCORE,
        penalties=penalties,
        totalPenalty=total_penalty,
        healthScore=round(max(0.0, _BASE_SCORE - total_penalty), 1),
        method=_SCORE_METHOD,
    )


def health_score(parameters: list[LabParameter]) -> float:
    """Deterministic 0-100 score: every out-of-range value costs a fixed, explainable amount."""
    return score_breakdown(parameters).health_score


def build_system_cards(parameters: list[LabParameter]) -> list[SystemCard]:
    by_key = {parameter.canonical_key: parameter for parameter in parameters}
    grouped_keys = {key for keys in SYSTEM_GROUPS.values() for key in keys}
    groups = {system: [by_key[key] for key in keys if key in by_key] for system, keys in SYSTEM_GROUPS.items()}
    groups[_OTHER_SYSTEM] = [p for p in parameters if p.canonical_key not in grouped_keys]

    cards = []
    for system, measured in groups.items():
        if not measured:
            continue
        abnormal = [parameter for parameter in measured if _is_abnormal(parameter)]
        risk_level = "typical" if not abnormal else ("watch" if len(abnormal) == 1 else "discuss")
        summary = (
            f"All {len(measured)} value(s) sit inside the typical range."
            if not abnormal
            else f"{len(abnormal)} of {len(measured)} value(s) sit outside the typical range: "
            + ", ".join(f"{parameter.display_name} ({parameter.status})" for parameter in abnormal)
            + "."
        )
        cards.append(SystemCard(system=system, riskLevel=risk_level, summary=summary))
    return cards


def build_narrative(parameters: list[LabParameter], abnormal: list[LabParameter], score: float) -> str:
    """Deterministic, source-grounded summary - every claim carries provenance (safety rule R2)."""
    sentences = [
        f"This report covers {len(parameters)} parameter(s); {len(abnormal)} sit outside the typical "
        f"range. Overall indicator score: {score}/100."
    ]
    for parameter in abnormal[:_GROUNDED_NOTE_LIMIT]:
        try:
            reference = get_reference_range(parameter.canonical_key)
            source = get_source(parameter.canonical_key)
        except NotFoundError:
            continue
        sentences.append(
            f"{parameter.display_name} is {parameter.value} {parameter.unit} against a typical range of "
            f"{reference['refLow']}-{reference['refHigh']} {reference['unit']}. {reference['plainLanguage']} "
            f"(source: {source.source_name}, {source.source_date})."
        )
    sentences.append("Please review this report with a qualified doctor before changing anything.")
    return " ".join(sentences)


async def run(payload: dict) -> ReportSummary:
    """`payload` is `{"parameters": list[LabParameter]}` - already normalized by `normalize_lab.py`.

    All numbers (status, score, cards) stay deterministic; no LLM is required for this contract.
    """
    parameters: list[LabParameter] = payload["parameters"]
    abnormal = [parameter for parameter in parameters if _is_abnormal(parameter)]
    score = health_score(parameters)

    return ReportSummary(
        parameters=parameters,
        abnormal=abnormal,
        systemCards=build_system_cards(parameters),
        healthScore=score,
        narrative=build_narrative(parameters, abnormal, score),
    )
