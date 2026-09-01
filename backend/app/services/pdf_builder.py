"""Doctor-review PDF builder, ReportLab (implementation-plan.md Section 5.3). Owner: D3.

Contract frozen for D4 consumption: `build(analysis) -> bytes`.

Sections, in order: header ("Doctor Review Request - Not a Prescription"), patient block
(consented fields only), prescribed medicines table (with OCR confidence), suggested
equivalents table (source + source date), doctor approval section (Approve/Modify/Reject,
notes, signature/date), footer disclaimer + provenance list + "Data is demo/curated" notice.
"""

from datetime import UTC, datetime
from io import BytesIO

from app.models.common import DISCLAIMER_TEXT
from app.models.medicine import MedicineAnalysis
from app.models.report import ChangedParameter, ComparisonResult

_BUCKET_LABELS: tuple[tuple[str, str], ...] = (
    ("worsened", "Moved away from range"),
    ("newlyAbnormal", "Newly outside range"),
    ("improved", "Moved toward range"),
    ("unchanged", "About the same"),
    ("missing", "Not repeated"),
)

_HEADER_TITLE = "Doctor Review Request - Not a Prescription"
_PROVENANCE_NOTE = (
    "Reference ranges are curated demo/educational data (MedlinePlus Lab Tests, seed date 2026-06-01). "
    "Classification is computed deterministically from the values above; no diagnosis is implied."
)


def build(analysis: MedicineAnalysis) -> bytes:
    """Render the 6-section doctor-review PDF and return the raw bytes."""
    raise NotImplementedError


def _format_value(value: float | None, unit: str) -> str:
    return "-" if value is None else f"{value} {unit}"


def _rows(result: ComparisonResult) -> list[list[str]]:
    rows = [["Parameter", result.old_report_date, result.current_report_date, "Change", "Verdict"]]
    for bucket, label in _BUCKET_LABELS:
        parameters: list[ChangedParameter] = getattr(result, {"newlyAbnormal": "newly_abnormal"}.get(bucket, bucket))
        for parameter in parameters:
            change = "-" if parameter.pct_change is None else f"{parameter.pct_change:+}%"
            rows.append(
                [
                    parameter.display_name,
                    _format_value(parameter.old, parameter.unit),
                    _format_value(parameter.current, parameter.unit),
                    change,
                    label,
                ]
            )
    return rows


def build_comparison(result: ComparisonResult) -> bytes:
    """Render the doctor-review comparison PDF (implementation-plan.md Section 5.3) as raw bytes."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    styles = getSampleStyleSheet()
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        title=_HEADER_TITLE,
        author="Health IQ",
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )

    story = [
        Paragraph(_HEADER_TITLE, styles["Title"]),
        Paragraph(f"Generated {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')} by Health IQ", styles["Normal"]),
        Spacer(1, 6 * mm),
        Paragraph(
            f"Lab report comparison: {result.old_report_date} vs {result.current_report_date}", styles["Heading2"]
        ),
    ]

    table = Table(_rows(result), repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0072b2")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c9d3df")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f7fb")]),
            ]
        )
    )
    story.extend([table, Spacer(1, 6 * mm)])

    story.extend(
        [
            Paragraph("Progression summary", styles["Heading2"]),
            Paragraph(result.narrative or "A plain-language summary was unavailable.", styles["BodyText"]),
            Spacer(1, 6 * mm),
            PageBreak(),
            Paragraph("Doctor review", styles["Heading2"]),
            Paragraph(
                "For each row above, please mark: [ ] Approve &nbsp;&nbsp; [ ] Modify &nbsp;&nbsp; [ ] Discuss",
                styles["BodyText"],
            ),
            Spacer(1, 12 * mm),
            Paragraph("Notes: ______________________________________________________", styles["BodyText"]),
            Spacer(1, 10 * mm),
            Paragraph("Signature: ____________________  Date: ______________", styles["BodyText"]),
            Spacer(1, 10 * mm),
            Paragraph("Disclaimer", styles["Heading2"]),
            Paragraph(DISCLAIMER_TEXT, styles["BodyText"]),
            Spacer(1, 4 * mm),
            Paragraph(_PROVENANCE_NOTE, styles["BodyText"]),
        ]
    )

    document.build(story)
    return buffer.getvalue()
