"""Unit tests for the deterministic `SpecialistAdvisorAgent` logic (LLD Section 2.3.4 / NFR2.3)."""

import pytest

from app.agents.specialist_agent import (
    build_categories,
    build_doctor_links,
    build_rationale,
    confidence_for,
    group_abnormal,
    run,
)
from app.models.report import LabParameter


def _parameter(canonical_key: str, display_name: str, value: float, status: str) -> LabParameter:
    return LabParameter(
        canonicalKey=canonical_key,
        displayName=display_name,
        value=value,
        unit="mg/dL",
        status=status,
        reportDate="2026-06-14",
        sourceConfidence=0.96,
    )


_HBA1C = _parameter("hba1c", "HbA1c", 7.4, "high")
_GLUCOSE = _parameter("glucose_fasting", "Fasting Blood Sugar", 126.0, "high")
_VITAMIN_D = _parameter("vitamin_d", "Vitamin D", 18.0, "low")
_CREATININE = _parameter("creatinine", "Creatinine", 0.9, "normal")


def test_abnormal_parameters_group_by_curated_parameter_group() -> None:
    groups = group_abnormal([_HBA1C, _GLUCOSE, _VITAMIN_D])

    assert set(groups) == {"metabolic", "nutrition"}
    assert {p.canonical_key for p in groups["metabolic"]} == {"hba1c", "glucose_fasting"}


def test_unmapped_parameter_falls_back_to_the_general_group() -> None:
    groups = group_abnormal([_parameter("not_a_seeded_key", "Unknown Marker", 1.0, "high")])

    assert list(groups) == ["general"]


@pytest.mark.parametrize(
    ("matched", "expected"),
    [(0, 0.62), (1, 0.72), (2, 0.82), (3, 0.92), (4, 0.95), (9, 0.95)],
)
def test_confidence_is_deterministic_and_capped(matched: int, expected: float) -> None:
    assert confidence_for(matched) == expected


def test_categories_are_ranked_by_confidence_then_group_name() -> None:
    categories = build_categories([_HBA1C, _GLUCOSE, _VITAMIN_D])

    assert [c.parameter_group for c in categories] == ["metabolic", "nutrition"]
    assert categories[0].specialty_category == "diabetologist"
    assert categories[0].confidence == 0.82


def test_every_category_carries_provenance() -> None:
    """NFR2.2: every explanation carries `sourceUrl` + `sourceDate`."""
    for category in build_categories([_HBA1C, _GLUCOSE, _VITAMIN_D]):
        assert category.source.source_url
        assert category.source.source_date


def test_no_abnormal_parameters_yields_general_physician_guidance() -> None:
    """LLD Section 2.9: an all-normal report returns guidance, not an empty error."""
    categories = build_categories([])

    assert [c.specialty_category for c in categories] == ["general-physician"]
    assert categories[0].confidence == 0.62


def test_rationale_describes_measurements_without_naming_a_condition() -> None:
    rationale = build_rationale([_HBA1C, _GLUCOSE, _VITAMIN_D])

    assert "Fasting Blood Sugar and HbA1c are above the typical range." in rationale
    assert "Vitamin D is below the typical range." in rationale
    assert "diabetes" not in rationale.lower()


def test_rationale_for_an_all_normal_report() -> None:
    assert "inside the typical range" in build_rationale([])


def test_doctor_links_are_deduplicated_and_flagged_public_demo() -> None:
    links = build_doctor_links(build_categories([_HBA1C, _GLUCOSE, _VITAMIN_D]))

    assert len(links) == len({(link.name, link.url) for link in links})
    assert all(link.provenance == "public/demo" for link in links)


async def test_run_is_reproducible_for_the_same_report() -> None:
    payload = {"parameters": [_HBA1C, _GLUCOSE, _VITAMIN_D, _CREATININE]}

    first = await run(payload)
    second = await run(payload)

    assert first.model_dump(by_alias=True) == second.model_dump(by_alias=True)
    assert first.disclaimer == (
        "Specialist category suggestion only; not a diagnosis or urgency claim."
    )
