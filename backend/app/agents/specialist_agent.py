"""`SpecialistAdvisorAgent` (implementation-plan.md Section 4.2). Owner: D3.

Tools: `search_reference_ranges`, `search_specialist_guidance`. Output: `SpecialistGuidance`.
Guardrails: category only; no named-doctor endorsement; links flagged public/demo data.

Which specialty a group maps to stays pure Python - a wrong specialty sends someone to the wrong
clinic, and the mapping is curated for exactly that reason. The *rationale* is written by a
tool-calling agent that retrieves reference ranges and specialist guidance from Search and cites
them, so the explanation is grounded rather than templated. `build_rationale()` remains the
fallback whenever the model or retrieval is unavailable.
"""

from app.agents import llm
from app.agents.tools import search_reference_ranges, search_specialist_guidance
from app.models.profile import (
    SPECIALIST_DISCLAIMER,
    DoctorLink,
    SpecialistCategory,
    SpecialistGuidance,
)
from app.models.report import ABNORMAL_STATUSES, LabParameter
from app.services.specialist_mapping import (
    GENERAL_GROUP,
    get_doctor_link,
    get_mapping,
    get_source,
    parameter_group_for,
)

# Confidence grows with the number of abnormal parameters backing a group, and is capped so no
# suggestion ever reads as certain. Two supporting parameters produce the 0.82 in LLD Section 2.3.4.
_CONFIDENCE_BASE = 0.62
_CONFIDENCE_PER_PARAMETER = 0.10
_CONFIDENCE_CEILING = 0.95

# Non-diagnostic phrasing only (FR2.7): describe the measurement, never the condition.
_DIRECTION = {
    "high": "above the typical range",
    "low": "below the typical range",
    "critical_flag": "outside the typical range and worth discussing promptly",
}


def _join(names: list[str]) -> str:
    if len(names) == 1:
        return names[0]
    return f"{', '.join(names[:-1])} and {names[-1]}"


def confidence_for(matched_count: int) -> float:
    """Deterministic confidence for a group backed by `matched_count` abnormal parameters."""
    raw = _CONFIDENCE_BASE + _CONFIDENCE_PER_PARAMETER * matched_count
    return round(min(_CONFIDENCE_CEILING, raw), 2)


def group_abnormal(abnormal: list[LabParameter]) -> dict[str, list[LabParameter]]:
    """Bucket abnormal parameters by curated group; unmapped keys fall back to general."""
    groups: dict[str, list[LabParameter]] = {}
    for parameter in abnormal:
        group = parameter_group_for(parameter.canonical_key) or GENERAL_GROUP
        groups.setdefault(group, []).append(parameter)
    return groups


def _category_for(group: str, parameters: list[LabParameter]) -> SpecialistCategory:
    mapping = get_mapping(group)
    return SpecialistCategory(
        specialtyCategory=mapping["specialtyCategory"],
        parameterGroup=group,
        whenToConsult=mapping["whenToConsult"],
        confidence=confidence_for(len(parameters)),
        source=get_source(group),
        parameters=parameters,
    )


def build_categories(abnormal: list[LabParameter]) -> list[SpecialistCategory]:
    """Curated groups ranked by confidence; ties break on group name so ordering is reproducible.

    A report with nothing abnormal still yields general-physician guidance (LLD Section 2.9).
    """
    if not abnormal:
        return [_category_for(GENERAL_GROUP, [])]

    categories = [
        _category_for(group, parameters)
        for group, parameters in group_abnormal(abnormal).items()
    ]
    return sorted(categories, key=lambda category: (-category.confidence, category.parameter_group))


def build_rationale(abnormal: list[LabParameter]) -> str:
    """Plain-language reason for the suggestion; names measurements, never a condition (FR2.7)."""
    if not abnormal:
        return (
            "Every measured parameter in this report sits inside the typical range, so no "
            "parameter-specific specialty stands out."
        )

    sentences = []
    for status, phrase in _DIRECTION.items():
        names = sorted(
            {parameter.display_name for parameter in abnormal if parameter.status == status}
        )
        if names:
            verb = "is" if len(names) == 1 else "are"
            sentences.append(f"{_join(names)} {verb} {phrase}.")
    return " ".join(sentences)


def build_doctor_links(categories: list[SpecialistCategory]) -> list[DoctorLink]:
    """One public/demo directory link per suggested category, de-duplicated and order-stable."""
    links: dict[tuple[str, str], DoctorLink] = {}
    for category in categories:
        link = get_doctor_link(category.parameter_group)
        links.setdefault((link.name, link.url), link)
    return list(links.values())


async def _write_rationale(
    abnormal: list[LabParameter], categories: list[SpecialistCategory]
) -> str | None:
    """Let the agent retrieve its own grounding and explain the suggestion."""
    if not abnormal or not categories:
        return None

    findings = ", ".join(
        f"{parameter.display_name} {parameter.value} {parameter.unit} ({parameter.status})"
        for parameter in abnormal
    )
    suggested = ", ".join(category.specialty_category for category in categories)
    return await llm.with_tools(
        instructions=llm.prompt("specialist_advisor"),
        task=(
            f"Abnormal results: {findings}.\n"
            f"Specialty categories already decided: {suggested}.\n"
            "Research each finding with your tools, then write the rationale."
        ),
        tools=[search_reference_ranges, search_specialist_guidance],
        name="SpecialistAdvisorAgent",
    )


async def run(payload: dict) -> SpecialistGuidance:
    """`payload` is `{"parameters": list[LabParameter]}` taken from the caller's stored report."""
    parameters: list[LabParameter] = payload["parameters"]
    abnormal = [parameter for parameter in parameters if parameter.status in ABNORMAL_STATUSES]
    categories = build_categories(abnormal)

    rationale = await _write_rationale(abnormal, categories) or build_rationale(abnormal)

    return SpecialistGuidance(
        categories=categories,
        rationale=rationale,
        doctorLinks=build_doctor_links(categories),
        disclaimer=get_mapping(categories[0].parameter_group)["disclaimer"]
        if categories
        else SPECIALIST_DISCLAIMER,
    )
