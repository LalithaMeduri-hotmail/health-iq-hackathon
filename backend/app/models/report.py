"""Lab report + comparison contracts (docs/lld/3- and 4-low-level-design-*.md).

`models/` is a pure leaf: no imports from services, repositories, or SDK clients here.
"""

from pydantic import BaseModel, ConfigDict, Field

Status = str  # "low" | "normal" | "high" | "critical_flag" (implementation-plan.md Section 2.4)


class LabParameter(BaseModel):
    """Normalized lab result (implementation-plan.md Section 2.4)."""

    model_config = ConfigDict(populate_by_name=True)

    canonical_key: str = Field(alias="canonicalKey")
    display_name: str = Field(alias="displayName")
    value: float
    unit: str
    ref_low: float | None = Field(alias="refLow", default=None)
    ref_high: float | None = Field(alias="refHigh", default=None)
    status: Status
    report_date: str = Field(alias="reportDate")
    source_confidence: float = Field(alias="sourceConfidence")


class SystemCard(BaseModel):
    """Organ/system risk card shown on the Health Profile tab."""

    model_config = ConfigDict(populate_by_name=True)

    system: str
    risk_level: str = Field(alias="riskLevel")
    summary: str


class ReportSummary(BaseModel):
    """`ReportAnalysisAgent` output contract (implementation-plan.md Section 4.2)."""

    model_config = ConfigDict(populate_by_name=True)

    parameters: list[LabParameter]
    abnormal: list[LabParameter] = Field(default_factory=list)
    system_cards: list[SystemCard] = Field(alias="systemCards", default_factory=list)
    health_score: float = Field(alias="healthScore")
    narrative: str


class ChangedParameter(BaseModel):
    """One aligned parameter pair in a report comparison (LLD Section 3.3.1)."""

    model_config = ConfigDict(populate_by_name=True)

    canonical_key: str = Field(alias="canonicalKey")
    old: float | None = None
    current: float | None = None
    unit: str
    pct_change: float | None = Field(alias="pctChange", default=None)
    status: Status | None = None


class TrendPoint(BaseModel):
    """One point of a longitudinal trend series (sourced from SQL `LabMetric`)."""

    model_config = ConfigDict(populate_by_name=True)

    report_date: str = Field(alias="reportDate")
    value: float


class ComparisonResult(BaseModel):
    """`ComparisonAgent` output contract (implementation-plan.md Section 4.2)."""

    model_config = ConfigDict(populate_by_name=True)

    old_report_date: str = Field(alias="oldReportDate")
    current_report_date: str = Field(alias="currentReportDate")
    improved: list[ChangedParameter] = Field(default_factory=list)
    worsened: list[ChangedParameter] = Field(default_factory=list)
    unchanged: list[ChangedParameter] = Field(default_factory=list)
    newly_abnormal: list[ChangedParameter] = Field(alias="newlyAbnormal", default_factory=list)
    missing: list[ChangedParameter] = Field(default_factory=list)
    trend_series: dict[str, list[TrendPoint]] = Field(alias="trendSeries", default_factory=dict)
    narrative: str = ""
