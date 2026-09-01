"""Deterministic report-comparison classification (implementation-plan.md Section 4.4). Owner: D2.

All numeric verdicts are pure Python and must be unit-testable without network calls - the LLM
only writes the narrative (agents/comparison_agent.py).

    delta      = current - old
    pctChange  = delta / old * 100  (guard old == 0)
    inRange(v) = refLow <= v <= refHigh

    improved       : was out of range and now in range, OR moved >=10% toward range
    worsened       : was in range and now out, OR moved >=10% away from range
    unchanged      : |pctChange| < 5
    newlyAbnormal  : absent in old, out of range in current
    missing        : present in old, absent in current
"""

from app.models.report import ChangedParameter, LabParameter
from app.services.reference_ranges import classify_status

UNCHANGED_THRESHOLD_PCT = 5.0
SIGNIFICANT_MOVE_THRESHOLD_PCT = 10.0

BUCKETS = ("missing", "newlyAbnormal", "improved", "worsened", "unchanged")


def _out_of_range_distance(value: float, ref_low: float | None, ref_high: float | None) -> float:
    """How far `value` sits outside its band; `0.0` while it is inside."""
    if ref_low is not None and value < ref_low:
        return ref_low - value
    if ref_high is not None and value > ref_high:
        return value - ref_high
    return 0.0


def _status_for(value: float | None, ref_low: float | None, ref_high: float | None) -> str | None:
    if value is None:
        return None
    if ref_low is None and ref_high is None:
        return "unknown"
    return classify_status(value, ref_low, ref_high)


def classify_change(
    canonical_key: str,
    *,
    old: float | None,
    current: float | None,
    unit: str,
    ref_low: float | None,
    ref_high: float | None,
    display_name: str = "",
) -> tuple[str, ChangedParameter]:
    """Classify one aligned parameter pair.

    Returns `(bucket, ChangedParameter)` where `bucket` is one of
    `"improved" | "worsened" | "unchanged" | "newlyAbnormal" | "missing"`.
    """
    pct_change = None
    if old not in (None, 0) and current is not None:
        pct_change = round((current - old) / old * 100, 1)

    parameter = ChangedParameter(
        canonicalKey=canonical_key,
        displayName=display_name or canonical_key,
        old=old,
        current=current,
        unit=unit,
        pctChange=pct_change,
        status=_status_for(current, ref_low, ref_high),
    )

    if current is None:
        return "missing", parameter

    now_in_range = _out_of_range_distance(current, ref_low, ref_high) == 0.0
    if old is None:
        # A parameter appearing for the first time is only notable when it lands outside its band.
        return ("unchanged" if now_in_range else "newlyAbnormal"), parameter

    distance_before = _out_of_range_distance(old, ref_low, ref_high)
    distance_after = _out_of_range_distance(current, ref_low, ref_high)
    was_in_range = distance_before == 0.0
    significant_move = pct_change is not None and abs(pct_change) >= SIGNIFICANT_MOVE_THRESHOLD_PCT

    is_noise = pct_change is not None and abs(pct_change) < UNCHANGED_THRESHOLD_PCT
    if is_noise and was_in_range == now_in_range:
        return "unchanged", parameter
    if (not was_in_range and now_in_range) or (significant_move and distance_after < distance_before):
        return "improved", parameter
    if (was_in_range and not now_in_range) or (significant_move and distance_after > distance_before):
        return "worsened", parameter
    return "unchanged", parameter


def align_and_classify(
    old_parameters: list[LabParameter], current_parameters: list[LabParameter]
) -> dict[str, list[ChangedParameter]]:
    """Align both reports by `canonicalKey` and bucket every parameter (FR3.2/FR3.3).

    Units are assumed already normalized upstream by `normalize_lab.py` (LLD Section 3.12 risk).
    """
    old_by_key = {parameter.canonical_key: parameter for parameter in old_parameters}
    current_by_key = {parameter.canonical_key: parameter for parameter in current_parameters}

    buckets: dict[str, list[ChangedParameter]] = {bucket: [] for bucket in BUCKETS}

    for key in sorted(old_by_key.keys() | current_by_key.keys()):
        old_parameter = old_by_key.get(key)
        current_parameter = current_by_key.get(key)
        reference = current_parameter or old_parameter
        assert reference is not None  # key came from one of the two maps

        bucket, changed = classify_change(
            key,
            old=old_parameter.value if old_parameter else None,
            current=current_parameter.value if current_parameter else None,
            unit=reference.unit,
            ref_low=reference.ref_low,
            ref_high=reference.ref_high,
            display_name=reference.display_name,
        )
        buckets[bucket].append(changed)

    return buckets
