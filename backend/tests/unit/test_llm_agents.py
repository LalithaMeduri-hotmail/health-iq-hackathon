"""Unit tests for the LLM-backed agents' fallback and grounding behaviour.

These run offline: `llm.structured` is monkeypatched, so they assert the contract every agent
must honour - use the model when it answers, fall back to Python when it does not, and never let
a model answer past the deterministic guard.
"""

import pytest

from app.agents import document_agent, llm, prescription_agent, report_agent
from app.services.ocr import OcrEnvelope, OcrLine


def _parameter(key: str, name: str, value: float, status: str) -> "report_agent.LabParameter":
    return report_agent.LabParameter(
        canonicalKey=key,
        displayName=name,
        value=value,
        unit="mg/dL",
        refLow=70,
        refHigh=100,
        status=status,
        reportDate="2025-01-15",
        sourceConfidence=0.95,
    )


def _envelope(*lines: tuple[str, float]) -> OcrEnvelope:
    return OcrEnvelope(
        pages=1,
        lines=[OcrLine(text=text, confidence=confidence, bbox=[]) for text, confidence in lines],
        tables=[],
        handwritten_ratio=0.0,
    )


async def test_triage_uses_the_model_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake(**_kwargs):
        return document_agent.DocumentVerdict(kind="lab_report", confidence=0.95, reason="analytes")

    monkeypatch.setattr(llm, "structured", fake)

    verdict = await document_agent.classify("HbA1c 7.4 % reference range 4.0-5.6")

    assert verdict.kind == "lab_report"
    assert verdict.reason == "analytes"


async def test_triage_falls_back_to_keywords_without_a_model(monkeypatch: pytest.MonkeyPatch) -> None:
    async def unavailable(**_kwargs):
        return None

    monkeypatch.setattr(llm, "structured", unavailable)

    verdict = await document_agent.classify(
        "Rx\nGlycomet 500mg 1-0-1 x10 days\nTablet after food\nDr. A. Mehta MBBS"
    )

    assert verdict.kind == "prescription"
    assert "fallback" in verdict.reason


async def test_triage_treats_a_hesitant_model_as_undecided(monkeypatch: pytest.MonkeyPatch) -> None:
    async def hesitant(**_kwargs):
        return document_agent.DocumentVerdict(kind="prescription", confidence=0.3, reason="unsure")

    monkeypatch.setattr(llm, "structured", hesitant)

    assert (await document_agent.classify("something ambiguous")).kind == "unknown"


async def test_triage_returns_unknown_for_empty_text() -> None:
    assert (await document_agent.classify("   ")).kind == "unknown"


async def test_reader_grounds_the_model_brand_against_the_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake(**_kwargs):
        return prescription_agent._ReadResult(
            items=[
                prescription_agent._ReadMedicine(
                    rawText="Glycomet 500mg 1-0-1 x10 days",
                    brandName="Glycomet",
                    # The model guessed the wrong ingredient; the catalog must win.
                    activeIngredient="Paracetamol",
                    strengthValue=500,
                    strengthUnit="mg",
                    frequency="1-0-1",
                    duration="10 days",
                    confidence=0.95,
                )
            ]
        )

    monkeypatch.setattr(llm, "structured", fake)

    analysis = await prescription_agent.run({"ocr_envelope": _envelope(("Glycomet 500mg", 0.95))})

    [item] = analysis.items
    assert item.active_ingredient == "Metformin"
    assert item.dosage_form == "tablet"
    assert item.needs_user_confirmation is False


async def test_reader_flags_a_brand_the_catalog_does_not_know(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake(**_kwargs):
        return prescription_agent._ReadResult(
            items=[
                prescription_agent._ReadMedicine(
                    rawText="Zzyxil 25mg", brandName="Zzyxil", strengthValue=25, confidence=0.9
                )
            ]
        )

    monkeypatch.setattr(llm, "structured", fake)

    analysis = await prescription_agent.run({"ocr_envelope": _envelope(("Zzyxil 25mg", 0.9))})

    [item] = analysis.items
    assert item.active_ingredient is None
    assert item.needs_user_confirmation is True


async def test_reader_falls_back_to_regex_without_a_model(monkeypatch: pytest.MonkeyPatch) -> None:
    async def unavailable(**_kwargs):
        return None

    monkeypatch.setattr(llm, "structured", unavailable)

    analysis = await prescription_agent.run(
        {"ocr_envelope": _envelope(("Glycomet 500mg 1-0-1 x10 days", 0.92))}
    )

    [item] = analysis.items
    assert item.brand_name == "Glycomet"
    assert item.active_ingredient == "Metformin"


async def test_report_uses_the_retrieved_narrative(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake(**_kwargs):
        return "Your fasting glucose is above the typical range (source: lab_reference_ranges)."

    monkeypatch.setattr(llm, "with_tools", fake)

    summary = await report_agent.run(
        {"parameters": [_parameter("glucose_fasting", "Fasting Glucose", 126, "high")]}
    )

    assert "source: lab_reference_ranges" in summary.narrative
    # The numbers stay deterministic even when the model writes the prose.
    assert [parameter.canonical_key for parameter in summary.abnormal] == ["glucose_fasting"]


async def test_report_falls_back_to_the_template_without_a_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def unavailable(**_kwargs):
        return None

    monkeypatch.setattr(llm, "with_tools", unavailable)

    parameters = [_parameter("glucose_fasting", "Fasting Glucose", 126, "high")]
    summary = await report_agent.run({"parameters": parameters})

    assert summary.narrative == report_agent.build_narrative(
        summary.parameters, summary.abnormal, summary.health_score
    )
    assert summary.narrative
