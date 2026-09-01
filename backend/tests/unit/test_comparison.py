"""Deterministic comparison classification (implementation-plan.md Section 4.4, LLD Section 3.11).

NFR3.2: these verdicts must be 100% reproducible - no network, no LLM.
"""

import pytest

from app.models.report import LabParameter
from app.services.comparison import align_and_classify, classify_change


def _classify(old, current, ref_low=0.0, ref_high=99.0, key="ldl"):
    bucket, parameter = classify_change(
        key, old=old, current=current, unit="mg/dL", ref_low=ref_low, ref_high=ref_high
    )
    return bucket, parameter


def test_out_of_range_moving_back_into_range_is_improved() -> None:
    bucket, parameter = _classify(old=160.0, current=95.0)

    assert bucket == "improved"
    assert parameter.status == "normal"


def test_large_move_toward_range_is_improved_even_when_still_abnormal() -> None:
    bucket, parameter = _classify(old=160.0, current=128.0)

    assert bucket == "improved"
    assert parameter.pct_change == -20.0
    assert parameter.status == "high"


def test_move_further_out_of_range_is_worsened() -> None:
    bucket, parameter = _classify(old=6.4, current=7.4, ref_low=4.0, ref_high=5.6, key="hba1c")

    assert bucket == "worsened"
    assert parameter.pct_change == 15.6


def test_leaving_the_range_is_worsened_even_for_a_small_move() -> None:
    bucket, _ = _classify(old=98.0, current=101.0)

    assert bucket == "worsened"


def test_small_move_inside_range_is_unchanged() -> None:
    bucket, parameter = _classify(old=0.9, current=0.92, ref_low=0.6, ref_high=1.3, key="creatinine")

    assert bucket == "unchanged"
    assert parameter.pct_change == 2.2


def test_absent_in_old_and_out_of_range_is_newly_abnormal() -> None:
    bucket, parameter = _classify(old=None, current=6.1, ref_low=0.4, ref_high=4.0, key="tsh")

    assert bucket == "newlyAbnormal"
    assert parameter.old is None
    assert parameter.pct_change is None


def test_absent_in_current_is_missing() -> None:
    bucket, parameter = _classify(old=22.0, current=None, ref_low=30.0, ref_high=100.0, key="vitamin_d")

    assert bucket == "missing"
    assert parameter.status is None


@pytest.mark.parametrize("old", [0.0, None])
def test_zero_or_absent_old_never_divides_by_zero(old) -> None:
    bucket, parameter = _classify(old=old, current=50.0)

    assert parameter.pct_change is None
    assert bucket == "unchanged"


def _parameter(key: str, value: float, ref_low: float, ref_high: float, date: str) -> LabParameter:
    return LabParameter(
        canonicalKey=key,
        displayName=key.upper(),
        value=value,
        unit="mg/dL",
        refLow=ref_low,
        refHigh=ref_high,
        status="normal",
        reportDate=date,
        sourceConfidence=0.97,
    )


def test_align_and_classify_buckets_every_parameter_once() -> None:
    old = [
        _parameter("ldl", 160.0, 0.0, 99.0, "2026-03-10"),
        _parameter("vitamin_d", 22.0, 30.0, 100.0, "2026-03-10"),
    ]
    current = [
        _parameter("ldl", 128.0, 0.0, 99.0, "2026-06-14"),
        _parameter("tsh", 6.1, 0.4, 4.0, "2026-06-14"),
    ]

    buckets = align_and_classify(old, current)

    assert [p.canonical_key for p in buckets["improved"]] == ["ldl"]
    assert [p.canonical_key for p in buckets["newlyAbnormal"]] == ["tsh"]
    assert [p.canonical_key for p in buckets["missing"]] == ["vitamin_d"]
    assert sum(len(values) for values in buckets.values()) == 3


def test_classification_is_reproducible() -> None:
    first = align_and_classify(
        [_parameter("ldl", 160.0, 0.0, 99.0, "2026-03-10")],
        [_parameter("ldl", 128.0, 0.0, 99.0, "2026-06-14")],
    )
    second = align_and_classify(
        [_parameter("ldl", 160.0, 0.0, 99.0, "2026-03-10")],
        [_parameter("ldl", 128.0, 0.0, 99.0, "2026-06-14")],
    )

    assert first == second
