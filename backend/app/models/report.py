"""Lab report + comparison contracts (docs/lld/3- and 4-low-level-design-*.md).

`models/` is a pure leaf: no imports from services, repositories, or SDK clients here.
"""

from pydantic import BaseModel, ConfigDict, Field

Status = str  # "low" | "normal" | "high" | "critical_flag" | "unknown" (no reference range available)

# `unknown` means no range was available, which is not the same as out of range.
ABNORMAL_STATUSES = frozenset({"low", "high", "critical_flag"})


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


class ScorePenalty(BaseModel):
    """One parameter's contribution to the health-score deduction."""

    model_config = ConfigDict(populate_by_name=True)

    canonical_key: str = Field(alias="canonicalKey")
    display_name: str = Field(alias="displayName")
    status: Status
    penalty: float


class HealthScoreBreakdown(BaseModel):
    """Why the score is what it is - the score is a pure function of these penalties (NFR2.5)."""

    model_config = ConfigDict(populate_by_name=True)

    base_score: float = Field(alias="baseScore")
    penalties: list[ScorePenalty] = Field(default_factory=list)
    total_penalty: float = Field(alias="totalPenalty")
    health_score: float = Field(alias="healthScore")
    method: str


class ReportDetailResponse(BaseModel):
    """`GET /api/v1/reports/{reportId}` response `data` - one stored report, fully expanded."""

    model_config = ConfigDict(populate_by_name=True)

    report_id: str = Field(alias="reportId")
    report_date: str = Field(alias="reportDate")
    lab_name: str = Field(alias="labName", default="")
    parameters: list[LabParameter] = Field(default_factory=list)
    abnormal: list[LabParameter] = Field(default_factory=list)
    system_cards: list[SystemCard] = Field(alias="systemCards", default_factory=list)
    health_score: float = Field(alias="healthScore")
    score_breakdown: HealthScoreBreakdown = Field(alias="scoreBreakdown")
    narrative: str


class ReportAnalyzeResponse(BaseModel):
    """`POST /api/v1/reports/analyze` response `data` (implementation-plan.md Section 5.1)."""

    model_config = ConfigDict(populate_by_name=True)

    report_id: str = Field(alias="reportId")
    report_date: str = Field(alias="reportDate")
    blob_path: str | None = Field(alias="blobPath", default=None)
    parameters: list[LabParameter] = Field(default_factory=list)
    abnormal: list[LabParameter] = Field(default_factory=list)
    system_cards: list[SystemCard] = Field(alias="systemCards", default_factory=list)
    health_score: float = Field(alias="healthScore")
    narrative: str


class StoredReport(BaseModel):
    """A `reports` document as persisted in Cosmos (LLD Section 4.2), used as the comparison input."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    user_id: str = Field(alias="userId")
    report_date: str = Field(alias="reportDate")
    lab_name: str = Field(alias="labName", default="")
    parameters: list[LabParameter] = Field(default_factory=list)


class ReportListItem(BaseModel):
    """Report-picker entry for the Report Comparison tab (FR3.1)."""

    model_config = ConfigDict(populate_by_name=True)

    report_id: str = Field(alias="reportId")
    report_date: str = Field(alias="reportDate")
    lab_name: str = Field(alias="labName", default="")
    parameter_count: int = Field(alias="parameterCount")
    abnormal_count: int = Field(alias="abnormalCount")


class ReportListResponse(BaseModel):
    """`GET /api/v1/reports` payload backing the two-report picker."""

    model_config = ConfigDict(populate_by_name=True)

    reports: list[ReportListItem] = Field(default_factory=list)


class ComparisonRequest(BaseModel):
    """`POST /api/v1/reports/compare` body (LLD Section 3.3.1)."""

    model_config = ConfigDict(populate_by_name=True)

    old_report_id: str = Field(alias="oldReportId")
    current_report_id: str = Field(alias="currentReportId")


class PdfGenerateRequest(BaseModel):
    """`POST /api/v1/pdf/generate` body (implementation-plan.md Section 5.1)."""

    model_config = ConfigDict(populate_by_name=True)

    run_id: str = Field(alias="runId")


class PdfGenerateResponse(BaseModel):
    """`POST /api/v1/pdf/generate` response `data`; `shareUrl` is the revocable public route."""

    model_config = ConfigDict(populate_by_name=True)

    pdf_blob_url: str = Field(alias="pdfBlobUrl")
    share_id: str = Field(alias="shareId")
    share_url: str = Field(alias="shareUrl")
    expires_at: str = Field(alias="expiresAt")


class ChangedParameter(BaseModel):
    """One aligned parameter pair in a report comparison (LLD Section 3.3.1)."""

    model_config = ConfigDict(populate_by_name=True)

    canonical_key: str = Field(alias="canonicalKey")
    display_name: str = Field(alias="displayName", default="")
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

    run_id: str = Field(alias="runId", default="")
    old_report_date: str = Field(alias="oldReportDate")
    current_report_date: str = Field(alias="currentReportDate")
    improved: list[ChangedParameter] = Field(default_factory=list)
    worsened: list[ChangedParameter] = Field(default_factory=list)
    unchanged: list[ChangedParameter] = Field(default_factory=list)
    newly_abnormal: list[ChangedParameter] = Field(alias="newlyAbnormal", default_factory=list)
    missing: list[ChangedParameter] = Field(default_factory=list)
    trend_series: dict[str, list[TrendPoint]] = Field(alias="trendSeries", default_factory=dict)
    narrative: str = ""
