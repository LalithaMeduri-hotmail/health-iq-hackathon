"""`ComparisonAgent` (implementation-plan.md Section 4.2). Owner: D3.

Tools: `load_report`, `align_parameters`, `classify_change` (deterministic, `services/comparison.py`).
Output: `ComparisonResult`. The LLM writes only the narrative; classification is pure Python.
"""

from pathlib import Path

from app.config import get_settings
from app.errors import NotFoundError
from app.models.report import ChangedParameter, ComparisonResult, StoredReport, TrendPoint
from app.services.comparison import align_and_classify
from app.services.reference_ranges import get_reference_range, get_source

_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "comparison_agent.md"
_GROUNDED_NOTE_LIMIT = 2


def _label(parameter: ChangedParameter) -> str:
    if parameter.old is None:
        return f"{parameter.display_name} ({parameter.current} {parameter.unit})"
    if parameter.current is None:
        return f"{parameter.display_name} (last recorded {parameter.old} {parameter.unit})"
    return f"{parameter.display_name} ({parameter.old} to {parameter.current} {parameter.unit})"


def _grounded_notes(parameters: list[ChangedParameter]) -> list[str]:
    """Reference-range-grounded discussion points (FR3.6); every claim carries its source (rule R2)."""
    notes = []
    for parameter in parameters[:_GROUNDED_NOTE_LIMIT]:
        try:
            reference = get_reference_range(parameter.canonical_key)
            source = get_source(parameter.canonical_key)
        except NotFoundError:
            continue
        notes.append(
            f"{parameter.display_name}: {reference['plainLanguage']} "
            f"Typical range {reference['refLow']}-{reference['refHigh']} {reference['unit']} "
            f"(source: {source.source_name}, {source.source_date})."
        )
    return notes


def build_narrative(buckets: dict[str, list[ChangedParameter]], old_date: str, current_date: str) -> str:
    """Deterministic, source-grounded progression summary - the always-available narrative floor."""
    sentences = [
        f"Between {old_date} and {current_date}, {len(buckets['improved'])} parameter(s) moved toward the "
        f"typical range, {len(buckets['worsened'])} moved further away, and {len(buckets['unchanged'])} "
        "stayed about the same."
    ]
    if buckets["improved"]:
        sentences.append("Moving toward the typical range: " + ", ".join(_label(p) for p in buckets["improved"]) + ".")
    if buckets["worsened"]:
        sentences.append("Worth discussing with a doctor: " + ", ".join(_label(p) for p in buckets["worsened"]) + ".")
    if buckets["newlyAbnormal"]:
        sentences.append(
            "Outside the typical range for the first time: "
            + ", ".join(_label(p) for p in buckets["newlyAbnormal"])
            + "."
        )
    if buckets["missing"]:
        sentences.append(
            "Not repeated in the newer report: " + ", ".join(p.display_name for p in buckets["missing"]) + "."
        )
    sentences.extend(_grounded_notes(buckets["worsened"] + buckets["newlyAbnormal"]))
    sentences.append("Please review these results with a qualified doctor before changing anything.")
    return " ".join(sentences)


async def _write_llm_narrative(summary: str) -> str | None:
    """Rephrase the deterministic summary; returns `None` so the caller can flag it unavailable."""
    from app.deps import get_chat_client

    try:
        agent = get_chat_client().create_agent(
            instructions=_PROMPT_PATH.read_text(encoding="utf-8"), name="ComparisonAgent"
        )
        response = await agent.run(
            "Rewrite this comparison summary in warm, plain language. Keep every number, direction, "
            "and source exactly as given, and add no new claims.\n\n" + summary
        )
        return (response.text or "").strip() or None
    except Exception:  # noqa: BLE001 - narrative is optional; a math-only result is still valuable
        return None


async def run(payload: dict) -> ComparisonResult:
    """`payload` is `{"old_report": StoredReport, "current_report": StoredReport, "trend_series": {...}}`.

    Classification stays pure Python (`services/comparison.py`); only the narrative may use an LLM.
    """
    old_report: StoredReport = payload["old_report"]
    current_report: StoredReport = payload["current_report"]
    trend_series: dict[str, list[TrendPoint]] = payload.get("trend_series", {})

    buckets = align_and_classify(old_report.parameters, current_report.parameters)
    narrative = build_narrative(buckets, old_report.report_date, current_report.report_date)

    settings = get_settings()
    if not settings.demo_mode and settings.azure_openai_endpoint:
        narrative = await _write_llm_narrative(narrative) or ""

    return ComparisonResult(
        oldReportDate=old_report.report_date,
        currentReportDate=current_report.report_date,
        improved=buckets["improved"],
        worsened=buckets["worsened"],
        unchanged=buckets["unchanged"],
        newlyAbnormal=buckets["newlyAbnormal"],
        missing=buckets["missing"],
        trendSeries=trend_series,
        narrative=narrative,
    )
