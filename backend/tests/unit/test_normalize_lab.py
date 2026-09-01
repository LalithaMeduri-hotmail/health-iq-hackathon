"""Lab normalization (implementation-plan.md Section 2.4): synonyms, units, dates, status."""

from datetime import UTC, datetime

import pytest

from app.services.normalize_lab import (
    _canonical_key,
    extract_report_date,
    find_report_date,
    normalize,
    parse_reference_range,
)
from app.services.ocr import OcrEnvelope, OcrLine


def _envelope(rows: list[list[str]], *, date_line: str = "Report Date: 2026-06-14") -> OcrEnvelope:
    return OcrEnvelope(
        pages=1,
        lines=[OcrLine(text=date_line, confidence=0.98, bbox=[])],
        tables=[[["Test", "Result", "Unit", "Reference Range"], *rows]],
        handwritten_ratio=0.0,
    )


def test_synonyms_map_to_canonical_keys() -> None:
    parameters = normalize(_envelope([["Glycated Haemoglobin", "7.4", "%", "4.0 - 5.6"], ["LDL-C", "128", "mg/dL", ""]]))

    keys = {parameter.canonical_key for parameter in parameters}
    assert keys == {"hba1c", "ldl"}


def test_status_is_computed_against_the_curated_range() -> None:
    parameters = normalize(_envelope([["HbA1c", "7.4", "%", ""], ["HDL-C", "48", "mg/dL", ""]]))
    by_key = {parameter.canonical_key: parameter for parameter in parameters}

    assert by_key["hba1c"].status == "high"
    assert by_key["hdl"].status == "normal"


def test_mmol_per_litre_glucose_is_converted_to_mg_per_dl() -> None:
    parameters = normalize(_envelope([["Fasting Glucose", "7.0", "mmol/L", ""]]))

    assert parameters[0].unit == "mg/dL"
    assert 125 < parameters[0].value < 127


def test_nmol_per_litre_vitamin_d_is_converted_to_ng_per_ml() -> None:
    parameters = normalize(_envelope([["Vitamin D", "50", "nmol/L", ""]]))

    assert parameters[0].unit == "ng/mL"
    assert 19 < parameters[0].value < 21


def test_unrecognized_parameters_are_kept_under_a_derived_key() -> None:
    parameters = normalize(_envelope([["Mystery Marker", "42", "mg/dL", ""], ["HbA1c", "5.2", "%", ""]]))

    assert [parameter.canonical_key for parameter in parameters] == ["mystery_marker", "hba1c"]
    assert parameters[0].status == "unknown"


def test_report_date_is_extracted_from_the_layout_lines() -> None:
    assert extract_report_date(_envelope([], date_line="Report Date: 2026-06-14")) == "2026-06-14"
    assert extract_report_date(_envelope([], date_line="Collected 14-06-2026")) == "2026-06-14"


@pytest.mark.parametrize(
    ("printed", "expected"),
    [
        ("Date: 01-Sep-2026", "2026-09-01"),
        ("Date: June-1-2026", "2026-06-01"),
        ("Date : 21 May, 2026", "2026-05-21"),
        ("Sample Collected On: 1 September 2026", "2026-09-01"),
        ("Reported: Sep 01, 2026", "2026-09-01"),
        ("Collected 15.Mar.2026", "2026-03-15"),
        ("Report Date: 2026-06-14", "2026-06-14"),
    ],
)
def test_month_name_dates_are_understood(printed: str, expected: str) -> None:
    assert extract_report_date(_envelope([], date_line=printed)) == expected


def test_a_missing_date_is_reported_rather_than_guessed() -> None:
    envelope = _envelope([], date_line="Patient: John Sample")

    assert find_report_date(envelope) is None
    assert extract_report_date(envelope) == datetime.now(UTC).strftime("%Y-%m-%d")


def test_non_date_lines_do_not_become_the_report_date() -> None:
    envelope = OcrEnvelope(
        pages=1,
        lines=[
            OcrLine(text="Age: 35", confidence=0.99, bbox=[]),
            OcrLine(text="Patient: John Sample", confidence=0.99, bbox=[]),
            OcrLine(text="Date: 01-Sep-2026", confidence=0.99, bbox=[]),
        ],
        tables=[],
        handwritten_ratio=0.0,
    )

    assert extract_report_date(envelope) == "2026-09-01"


def test_the_same_analyte_aligns_across_labs_that_word_it_differently() -> None:
    prime = normalize(_envelope([["Hematocrit", "42", "%", "36 - 50"], ["RBC Count", "4.8", "million/uL", ""]]))
    healthfirst = normalize(_envelope([["PCV", "44", "%", "36 - 50"], ["Total RBC Count", "5.1", "million/uL", ""]]))

    assert [p.canonical_key for p in prime] == [p.canonical_key for p in healthfirst]


def test_values_fall_back_to_plain_text_lines_when_no_table_is_present() -> None:
    envelope = OcrEnvelope(
        pages=1,
        lines=[
            OcrLine(text="Report Date: 2026-06-14", confidence=0.98, bbox=[]),
            OcrLine(text="HbA1c 7.4 %", confidence=0.96, bbox=[]),
        ],
        tables=[],
        handwritten_ratio=0.0,
    )

    parameters = normalize(envelope)

    assert [parameter.canonical_key for parameter in parameters] == ["hba1c"]
    assert parameters[0].value == 7.4


@pytest.mark.parametrize(
    ("printed_name", "expected_key"),
    [
        ("25-OH VITAMIN D (TOTAL)", "vitamin_d"),
        ("VITAMIN B-12", "vitamin_b12"),
        ("FASTING BLOOD SUGAR(GLUCOSE)", "glucose_fasting"),
        ("POST PRANDIAL BLOOD SUGAR(GLUCOSE)", "glucose_pp"),
        ("HbA1c (Glycosylated Haemoglobin)", "hba1c"),
        ("SERUM CREATININE", "creatinine"),
        ("ULTRASENSITIVE TSH", "tsh"),
        ("TOTAL LEUKOCYTE COUNT (TLC)", "wbc"),
        ("SGPT (ALT)", "sgpt_alt"),
    ],
)
def test_real_world_lab_names_resolve(printed_name: str, expected_key: str) -> None:
    assert _canonical_key(printed_name) == expected_key


def test_sibling_analytes_are_never_confused() -> None:
    assert _canonical_key("LDL CHOLESTEROL - DIRECT") == "ldl"
    assert _canonical_key("HDL CHOLESTEROL - DIRECT") == "hdl"
    assert _canonical_key("SGOT (AST)") == "sgot_ast"


@pytest.mark.parametrize("noise", ["Patient Name", "TEST DETAILS", "Report Status", "Referred By", "Processed At"])
def test_non_parameter_rows_are_ignored(noise: str) -> None:
    assert _canonical_key(noise) is None


def test_value_is_found_when_it_is_not_the_second_column() -> None:
    envelope = OcrEnvelope(
        pages=1,
        lines=[OcrLine(text="Report Date: 2026-05-21", confidence=0.99, bbox=[])],
        tables=[
            [
                ["TEST NAME", "TECHNOLOGY", "VALUE", "UNITS", "REFERENCE"],
                ["FASTING BLOOD SUGAR(GLUCOSE)", "HEXOKINASE", "108", "mg/dL", "70 - 99"],
                ["25-OH VITAMIN D (TOTAL)", "CLIA", "16.4", "ng/mL", "30 - 100"],
            ]
        ],
        handwritten_ratio=0.0,
    )

    by_key = {parameter.canonical_key: parameter for parameter in normalize(envelope)}

    assert by_key["glucose_fasting"].value == 108.0
    assert by_key["glucose_fasting"].unit == "mg/dL"
    assert by_key["glucose_fasting"].status == "high"
    assert by_key["vitamin_d"].status == "low"


@pytest.mark.parametrize(
    ("printed", "expected"),
    [
        ("70 - 99", (70.0, 99.0)),
        ("0.4-4.0", (0.4, 4.0)),
        ("13.0 to 17.0", (13.0, 17.0)),
        ("< 200", (None, 200.0)),
        ("Upto 150", (None, 150.0)),
        ("> 40", (40.0, None)),
        ("", (None, None)),
        ("Not Detected", (None, None)),
    ],
)
def test_printed_reference_ranges_are_parsed(printed: str, expected: tuple) -> None:
    assert parse_reference_range(printed) == expected


def _uncurated_envelope(rows: list[list[str]]) -> OcrEnvelope:
    return OcrEnvelope(
        pages=1,
        lines=[OcrLine(text="Report Date: 2026-05-21", confidence=0.99, bbox=[])],
        tables=[[["TEST NAME", "VALUE", "UNITS", "REFERENCE"], *rows]],
        handwritten_ratio=0.0,
    )


def test_parameters_outside_the_curated_set_are_kept() -> None:
    parameters = normalize(
        _uncurated_envelope(
            [
                ["HOMOCYSTEINE", "22", "umol/L", "5 - 15"],
                ["SERUM COPPER", "70", "ug/dL", "80 - 155"],
                ["APOLIPOPROTEIN A1", "140", "mg/dL", "110 - 205"],
            ]
        )
    )
    by_key = {parameter.canonical_key: parameter for parameter in parameters}

    assert set(by_key) == {"homocysteine", "copper", "apolipoprotein a1".replace(" ", "_")}
    assert by_key["homocysteine"].status == "high"
    assert by_key["copper"].status == "low"
    assert by_key["apolipoprotein_a1"].status == "normal"
    assert by_key["copper"].display_name == "SERUM COPPER"


def test_uncurated_parameter_without_a_printed_range_is_marked_unknown() -> None:
    parameters = normalize(_uncurated_envelope([["Lipoprotein (a)", "18", "mg/dL", "Not Established"]]))

    assert parameters[0].status == "unknown"
    assert parameters[0].ref_low is None
    assert parameters[0].ref_high is None


def test_curated_ranges_win_over_the_printed_range() -> None:
    parameters = normalize(_uncurated_envelope([["HbA1c", "5.9", "%", "4.0 - 9.9"]]))

    assert parameters[0].ref_high == 5.6
    assert parameters[0].status == "high"


def test_the_same_analyte_aligns_across_differently_worded_reports() -> None:
    first = normalize(_uncurated_envelope([["SERUM COPPER", "70", "ug/dL", "80 - 155"]]))
    second = normalize(_uncurated_envelope([["Copper", "96", "ug/dL", "80 - 155"]]))

    assert first[0].canonical_key == second[0].canonical_key
