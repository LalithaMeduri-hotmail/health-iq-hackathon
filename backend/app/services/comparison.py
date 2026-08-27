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

from app.models.report import ChangedParameter

UNCHANGED_THRESHOLD_PCT = 5.0
SIGNIFICANT_MOVE_THRESHOLD_PCT = 10.0


def classify_change(
    canonical_key: str,
    *,
    old: float | None,
    current: float | None,
    unit: str,
    ref_low: float | None,
    ref_high: float | None,
) -> tuple[str, ChangedParameter]:
    """Classify one aligned parameter pair.

    Returns `(bucket, ChangedParameter)` where `bucket` is one of
    `"improved" | "worsened" | "unchanged" | "newlyAbnormal" | "missing"`.
    """
    raise NotImplementedError
