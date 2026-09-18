"""`ReportAnalysisAgent` (implementation-plan.md Section 4.2). Owner: D3.

Tools: `ocr_layout`, `normalize_lab`, `lookup_reference_range`, `search_reference_explanations`.
Output: `ReportSummary`. Guardrails: use "possible concern"; never name a disease.
"""

from app.errors import NotFoundError
from app.models.report import LabParameter, ReportSummary, SystemCard
from app.services.health_score import health_score, is_abnormal, score_breakdown
from app.services.reference_ranges import get_reference_range, get_source

__all__ = ["build_narrative", "build_system_cards", "health_score", "run", "score_breakdown"]

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

_GROUNDED_NOTE_LIMIT = 3
_OTHER_SYSTEM = "Other results"


def build_system_cards(parameters: list[LabParameter]) -> list[SystemCard]:
    by_key = {parameter.canonical_key: parameter for parameter in parameters}
    grouped_keys = {key for keys in SYSTEM_GROUPS.values() for key in keys}
    groups = {system: [by_key[key] for key in keys if key in by_key] for system, keys in SYSTEM_GROUPS.items()}
    groups[_OTHER_SYSTEM] = [p for p in parameters if p.canonical_key not in grouped_keys]

    cards = []
    for system, measured in groups.items():
        if not measured:
            continue
        abnormal = [parameter for parameter in measured if is_abnormal(parameter)]
        risk_level = "typical" if not abnormal else ("watch" if len(abnormal) == 1 else "discuss")
        noun = "value" if len(measured) == 1 else "values"
        summary = (
            f"All {len(measured)} {noun} sit inside the typical range."
            if not abnormal
            else f"{len(abnormal)} of {len(measured)} {noun} sit outside the typical range: "
            + ", ".join(f"{parameter.display_name} ({parameter.status})" for parameter in abnormal)
            + "."
        )
        cards.append(
            SystemCard(
                system=system,
                riskLevel=risk_level,
                summary=summary,
                parameters=[parameter.canonical_key for parameter in measured],
            )
        )
    return cards


def _with_meaning(parameter: LabParameter) -> LabParameter:
    """Attach the seeded plain-language description so clients never invent their own wording."""
    try:
        reference = get_reference_range(parameter.canonical_key)
    except NotFoundError:
        return parameter
    return parameter.model_copy(update={"meaning": reference["plainLanguage"]})


def build_narrative(parameters: list[LabParameter], abnormal: list[LabParameter], score: float) -> str:
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
    parameters = [_with_meaning(parameter) for parameter in parameters]
    abnormal = [parameter for parameter in parameters if is_abnormal(parameter)]
    score = health_score(parameters)

    return ReportSummary(
        parameters=parameters,
        abnormal=abnormal,
        systemCards=build_system_cards(parameters),
        healthScore=score,
        narrative=build_narrative(parameters, abnormal, score),
    )
