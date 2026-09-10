"""Doctor-review PDF builder, ReportLab (implementation-plan.md Section 5.3). Owner: D3.

Contract frozen for D4 consumption: `build(analysis) -> bytes`.

Deliberately terse: a clinician skims this between patients, so it carries tables, one-line
context, and the approval block - no explanatory prose. Order: header line, data table(s),
decision block (Approve/Approve with changes/Do not approve, notes, signature), footnotes.
"""

from datetime import UTC, datetime
from io import BytesIO

from app.models.common import DISCLAIMER_TEXT
from app.models.medicine import MedicineAnalysis, MedicineEntity
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


def build(analysis: MedicineAnalysis, alternatives: list[dict] | None = None) -> bytes:
    """Render the doctor-review PDF: tables, one-line context, and the approval block."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    styles = getSampleStyleSheet()
    fine = ParagraphStyle("Fine", parent=styles["BodyText"], fontSize=7.5, leading=10, spaceAfter=2)
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

    generated_at = datetime.now(UTC).strftime("%d %b %Y, %H:%M UTC")
    alt_count = len(alternatives or [])

    story = [
        Paragraph(_HEADER_TITLE, styles["Title"]),
        Paragraph(
            f"{generated_at} &nbsp;|&nbsp; {len(analysis.items)} medicine(s) &nbsp;|&nbsp; "
            f"{alt_count} equivalent(s) &nbsp;|&nbsp; de-identified",
            fine,
        ),
        Spacer(1, 6 * mm),
        Paragraph("Current medicines", styles["Heading3"]),
        _table(_prescribed_rows(analysis.items), colors, mm, Table, TableStyle),
        Spacer(1, 5 * mm),
        Paragraph("Equivalents for review", styles["Heading3"]),
    ]

    if alternatives:
        story.append(_table(_alternative_rows(alternatives), colors, mm, Table, TableStyle))
        story.append(Paragraph("Same ingredient, strength and form. Prices indicative.", fine))
    else:
        story.append(
            Paragraph("None matched on ingredient, strength and form.", styles["BodyText"])
        )

    story.extend(
        [
            Spacer(1, 6 * mm),
            Paragraph("Decision", styles["Heading3"]),
            Paragraph(
                "[ ] Approve &nbsp;&nbsp;&nbsp; [ ] Approve with changes &nbsp;&nbsp;&nbsp; "
                "[ ] Do not approve",
                styles["BodyText"],
            ),
            Spacer(1, 8 * mm),
            Paragraph(
                "Notes: ______________________________________________________", styles["BodyText"]
            ),
            Spacer(1, 7 * mm),
            Paragraph(
                "Signature: __________________&nbsp;&nbsp; Reg. no: ____________"
                "&nbsp;&nbsp; Date: __________",
                styles["BodyText"],
            ),
            Spacer(1, 8 * mm),
            Paragraph(_sources_note(alternatives), fine),
            Paragraph(DISCLAIMER_TEXT, fine),
        ]
    )
    for disclaimer in analysis.disclaimers:
        story.append(Paragraph(disclaimer, fine))

    document.build(story)
    return buffer.getvalue()


def _prescribed_rows(items: list[MedicineEntity]) -> list[list[str]]:
    rows = [["Medicine", "Strength", "How often", "For how long", "Read clarity"]]
    for item in items:
        strength = (
            f"{item.strength_value:g} {item.strength_unit or ''}".strip()
            if item.strength_value is not None
            else "-"
        )
        confidence = "-" if item.ocr_confidence is None else f"{item.ocr_confidence * 100:.0f}%"
        rows.append(
            [
                item.brand_name or item.raw_text,
                strength,
                item.frequency or "-",
                item.duration or "-",
                confidence,
            ]
        )
    return rows


def _alternative_rows(alternatives: list[dict]) -> list[list[str]]:
    rows = [["Currently on", "Same ingredient as", "Equivalent option", "Price (INR)", "Difference", "Price dated"]]
    for alternative in alternatives:
        source = alternative.get("source") or {}
        rows.append(
            [
                alternative["original"],
                alternative["generic"],
                alternative["cheaper"],
                f"{alternative['originalMrpInr']:.2f} -> {alternative['cheaperMrpInr']:.2f}",
                f"about {alternative['savingsPct']}% less",
                source.get("sourceDate", "-"),
            ]
        )
    return rows


def _sources_note(alternatives: list[dict] | None) -> str:
    names = sorted(
        {(alt.get("source") or {}).get("sourceName", "") for alt in alternatives or []} - {""}
    )
    if not names:
        return _PROVENANCE_NOTE
    return f"Price sources: {', '.join(names)}. Data is demo/curated."


def _table(rows: list[list[str]], colors, mm, Table, TableStyle):  # noqa: N803 - ReportLab symbols
    """Shared table styling for both PDF variants; ReportLab symbols are passed in by the caller."""
    table = Table(rows, repeatRows=1, hAlign="LEFT")
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
    return table


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
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    styles = getSampleStyleSheet()
    fine = ParagraphStyle("Fine", parent=styles["BodyText"], fontSize=7.5, leading=10, spaceAfter=2)
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
        Paragraph(
            f"{datetime.now(UTC).strftime('%d %b %Y, %H:%M UTC')} &nbsp;|&nbsp; "
            f"{result.old_report_date} vs {result.current_report_date} &nbsp;|&nbsp; de-identified",
            fine,
        ),
        Spacer(1, 6 * mm),
        Paragraph("Changed parameters", styles["Heading3"]),
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
    story.extend([table, Spacer(1, 5 * mm)])

    story.extend(
        [
            Paragraph("Summary", styles["Heading3"]),
            Paragraph(result.narrative or "No summary available.", styles["BodyText"]),
            Spacer(1, 6 * mm),
            Paragraph("Decision", styles["Heading3"]),
            Paragraph(
                "[ ] Approve &nbsp;&nbsp;&nbsp; [ ] Approve with changes &nbsp;&nbsp;&nbsp; "
                "[ ] Do not approve",
                styles["BodyText"],
            ),
            Spacer(1, 8 * mm),
            Paragraph("Notes: ______________________________________________________", styles["BodyText"]),
            Spacer(1, 7 * mm),
            Paragraph(
                "Signature: __________________&nbsp;&nbsp; Reg. no: ____________"
                "&nbsp;&nbsp; Date: __________",
                styles["BodyText"],
            ),
            Spacer(1, 8 * mm),
            Paragraph(_PROVENANCE_NOTE, fine),
            Paragraph(DISCLAIMER_TEXT, fine),
        ]
    )

    document.build(story)
    return buffer.getvalue()
