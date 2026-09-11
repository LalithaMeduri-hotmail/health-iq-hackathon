"""Deterministic report-parameter to neutral nutrition-tag mapping."""

from app.models.report import ABNORMAL_STATUSES, LabParameter

_PARAMETER_TAGS: dict[str, str] = {
    "glucose_fasting": "elevated-glucose",
    "glucose_pp": "elevated-glucose",
    "hba1c": "elevated-glucose",
    "ldl": "elevated-ldl",
    "total_cholesterol": "elevated-ldl",
    "triglycerides": "elevated-ldl",
    "vitamin_d": "low-vitamin-d",
}
_TAG_ORDER = ("elevated-glucose", "elevated-ldl", "low-vitamin-d", "general-wellness")


def derive_condition_tags(parameters: list[LabParameter]) -> list[str]:
    """Return neutral tags for abnormal measurements; never infer or name a diagnosis."""
    tags = {
        _PARAMETER_TAGS[parameter.canonical_key]
        for parameter in parameters
        if parameter.status in ABNORMAL_STATUSES and parameter.canonical_key in _PARAMETER_TAGS
    }
    if not tags:
        tags.add("general-wellness")
    return [tag for tag in _TAG_ORDER if tag in tags]