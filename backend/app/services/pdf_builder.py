"""Doctor-review PDF builder, ReportLab (implementation-plan.md Section 5.3). Owner: D3.

Contract frozen for D4 consumption: `build(analysis) -> bytes`.

Deliberately terse: a clinician skims this between patients, so it carries tables, one-line
context, and the approval block - no explanatory prose. Order: header line, data table(s),
decision block (Approve/Approve with changes/Do not approve, notes, signature), footnotes.
"""

from datetime import UTC, datetime
from html import escape
from io import BytesIO
from pathlib import Path

from app.models.common import DISCLAIMER_TEXT
from app.models.medicine import MedicineAnalysis, MedicineEntity
from app.models.report import ChangedParameter, ComparisonResult
from app.models.review import PrescriptionDocument

_LOGO_PATH = Path(__file__).resolve().parents[3] / "data" / "brand" / "healthiq-logo.png"

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

_DECISION_LABELS = {
    "approved": "Approved",
    "changes_requested": "Change requested",
    "rejected": "Not approved",
}

_DECISION_INK = {
    "approved": "#166534",
    "changes_requested": "#b45309",
    "rejected": "#b91c1c",
}

_PRESCRIPTION_TITLE = "Health IQ Review Summary"
_PRESCRIPTION_SUBTITLE = "A clinician's decision on the patient's own prescription"
_PRESCRIPTION_GUIDANCE = (
    "Note: Take medicines as directed. Only rows marked Approved may be switched to the Health IQ "
    "alternative; anything else stays as originally prescribed until the clinician below says "
    "otherwise. This does not replace your original prescription."
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


def _table(rows: list[list], colors, mm, Table, TableStyle, widths: list[float] | None = None):  # noqa: N803 - ReportLab symbols
    """Shared table styling for both PDF variants; ReportLab symbols are passed in by the caller."""
    col_widths = [width * mm for width in widths] if widths else None
    table = Table(rows, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
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


def build_prescription(document_model: PrescriptionDocument) -> bytes:
    """Render the single Health IQ review summary for one decided review.

    Laid out like the paper prescription a patient already recognises: the prescriber's block at
    the top, patient and reference details under a rule, then one row per medicine carrying the
    proposed alternative and the verdict side by side, and the clinician's sign-off at the foot.
    """
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        HRFlowable,
        Image,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    title, subtitle, guidance = _PRESCRIPTION_TITLE, _PRESCRIPTION_SUBTITLE, _PRESCRIPTION_GUIDANCE
    ink = colors.HexColor("#0b1220")
    muted = colors.HexColor("#64748b")

    styles = getSampleStyleSheet()
    fine = ParagraphStyle("Fine", parent=styles["BodyText"], fontSize=7, leading=9.5, spaceAfter=2, textColor=muted)
    wordmark = ParagraphStyle(
        "Wordmark", parent=styles["BodyText"], fontSize=13, leading=16, spaceAfter=0, textColor=ink
    )
    right = ParagraphStyle("Right", parent=styles["BodyText"], fontSize=9, leading=12, alignment=TA_RIGHT, spaceAfter=0)
    label = ParagraphStyle("Label", parent=styles["BodyText"], fontSize=8, leading=11, textColor=muted, spaceAfter=0)
    body = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=9, leading=12, spaceAfter=0, textColor=ink)
    med = ParagraphStyle("Med", parent=body, fontSize=9.5, leading=13)
    dose = ParagraphStyle("Dose", parent=styles["BodyText"], fontSize=7.5, leading=10, spaceAfter=0)

    buffer = BytesIO()
    pdf = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        title=title,
        author="Health IQ",
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
    )

    prescriber = (
        f"<b>{_escape(document_model.doctor_name)}</b><br/>"
        f"{_escape(document_model.doctor_specialty)}"
    )
    masthead = Table(
        [
            [
                _brandmark(Image, Paragraph, Table, TableStyle, mm, wordmark),
                Paragraph(
                    f"{prescriber}"
                    f'<br/><font size="7" color="#64748b">Registration No: '
                    f"{_escape(document_model.doctor_registration_no)}</font>"
                    f'<br/><font size="7" color="#64748b">Reviewed through Health IQ</font>',
                    right,
                ),
            ]
        ],
        colWidths=[60 * mm, 114 * mm],
        hAlign="LEFT",
    )
    masthead.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))

    details = Table(
        [
            [
                Paragraph("Patient Details", label),
                Paragraph(f"Ref no: &nbsp;<b>{_escape(document_model.reference)}</b>", body),
            ],
            [
                Paragraph(f"<b>{_escape(document_model.patient_name)}</b>", body),
                Paragraph(f"Reviewed on: &nbsp;{_escape(document_model.reviewed_at)}", body),
            ],
            [Paragraph(subtitle, fine), ""],
        ],
        colWidths=[94 * mm, 80 * mm],
        hAlign="LEFT",
    )
    details.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ]
        )
    )

    story = [
        masthead,
        Spacer(1, 4 * mm),
        HRFlowable(width="100%", thickness=0.8, color=ink, spaceAfter=5),
        details,
        Spacer(1, 4 * mm),
        HRFlowable(width="100%", thickness=0.8, color=ink, spaceAfter=0),
        _medicines_table(document_model, colors, mm, Table, TableStyle, Paragraph, med, dose, fine),
        Spacer(1, 3 * mm),
        Paragraph(f"***** {guidance} *****", fine),
        Spacer(1, 4 * mm),
    ]

    if document_model.notes:
        story.extend(
            [
                Paragraph("General instructions:", label),
                Paragraph(_escape(document_model.notes), body),
                Spacer(1, 6 * mm),
            ]
        )

    story.extend(
        [
            Spacer(1, 6 * mm),
            Paragraph(
                f"<b>{_escape(document_model.doctor_name)}</b><br/>"
                f"{_escape(document_model.doctor_specialty)}<br/>"
                f'<font size="7" color="#64748b">Recorded electronically through Health IQ on '
                f"{_escape(document_model.reviewed_at)} - no wet signature required.</font>",
                right,
            ),
            Spacer(1, 6 * mm),
            HRFlowable(width="100%", thickness=0.5, color=muted, spaceAfter=4),
            Paragraph(f"Disclaimer: {DISCLAIMER_TEXT}", fine),
        ]
    )

    pdf.build(story)
    return buffer.getvalue()


def _brandmark(Image, Paragraph, Table, TableStyle, mm, wordmark):  # noqa: N803 - ReportLab symbols
    """Health IQ logo beside the wordmark; the wordmark alone if the asset is missing."""
    name = Paragraph('<b>Health</b> <font color="#16a34a"><b>IQ</b></font>', wordmark)
    if not _LOGO_PATH.exists():
        return name

    mark = Table(
        [[Image(str(_LOGO_PATH), width=13 * mm, height=13 * mm), name]],
        colWidths=[15 * mm, 43 * mm],
        hAlign="LEFT",
    )
    mark.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (0, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return mark


def _medicines_table(  # noqa: N803 - ReportLab symbols are passed in by the caller
    document_model: PrescriptionDocument, colors, mm, Table, TableStyle, Paragraph, med, dose, fine
):
    """One row per medicine: what was prescribed, the Health IQ equivalent, and the verdict."""
    rows: list[list] = [
        [
            "",
            Paragraph("<b>Current medicine</b>", med),
            Paragraph("<b>Health IQ alternative</b>", med),
            Paragraph("<b>Directions</b>", med),
            Paragraph("<b>Decision</b>", med),
        ]
    ]
    for index, line in enumerate(document_model.lines, start=1):
        maker = f' <font color="#64748b">({_escape(line.maker)})</font>' if line.maker else ""
        detail = "".join(
            f'<br/><font size="7.5" color="#64748b">{_escape(part)}</font>'
            for part in (line.generic, line.form)
            if part
        )
        rows.append(
            [
                Paragraph(f"{index}.", med),
                Paragraph(f"<b>{_escape(line.label)}</b>{maker}{detail}", med),
                Paragraph(_alternative_cell(line), dose),
                Paragraph(
                    f"{_escape(line.frequency)}<br/>"
                    f'<font color="#64748b">{_escape(line.duration)}</font>',
                    dose,
                ),
                Paragraph(
                    f'<b><font color="{_DECISION_INK.get(line.decision, "#64748b")}">'
                    f'{_escape(_DECISION_LABELS.get(line.decision, line.decision))}</font></b>'
                    f'<br/><font size="7" color="#64748b">{_escape(line.note)}</font>',
                    dose,
                ),
            ]
        )

    table = Table(
        rows,
        colWidths=[7 * mm, 54 * mm, 54 * mm, 27 * mm, 32 * mm],
        repeatRows=1,
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (0, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.HexColor("#0b1220")),
                ("LINEBELOW", (0, 1), (-1, -2), 0.3, colors.HexColor("#e2e8f0")),
            ]
        )
    )
    return table


def _alternative_cell(line) -> str:
    """The equivalent the clinician was asked about, priced so the saving is auditable."""
    if not line.alternative:
        return '<font color="#64748b">No equivalent found - confirmed as prescribed</font>'

    maker = (
        f' <font color="#64748b">({_escape(line.alternative_maker)})</font>'
        if line.alternative_maker
        else ""
    )
    generic = (
        f'<br/><font size="7.5" color="#64748b">{_escape(line.alternative_generic)}</font>'
        if line.alternative_generic
        else ""
    )
    price = ""
    if line.original_mrp_inr and line.cheaper_mrp_inr:
        saving = f" &middot; about {line.savings_pct}% less" if line.savings_pct else ""
        # Prices stay in "Rs" rather than the rupee sign: the base PDF fonts have no glyph for it.
        price = (
            f'<br/><font size="7.5" color="#64748b">Rs {line.original_mrp_inr:.2f} &rarr; '
            f"Rs {line.cheaper_mrp_inr:.2f}{saving}</font>"
        )
    return f"<b>{_escape(line.alternative)}</b>{maker}{generic}{price}"


def _escape(value: str) -> str:
    """ReportLab parses cell text as mini-HTML, so user/clinician text must be escaped."""
    return escape(value or "")


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
