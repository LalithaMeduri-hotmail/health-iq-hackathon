"""Lab result normalization (implementation-plan.md Section 2.4). Owner: D2.

Contract frozen for D3/D4 consumption: `normalize(ocr) -> list[LabParameter]`. Uses
`data/synonyms/lab_synonyms.json` for canonical-key mapping and unit conversion
(mg/dL <-> mmol/L for glucose/cholesterol; ng/mL <-> nmol/L for vitamin D).
"""

import json
import re
import statistics
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from app.errors import NotFoundError
from app.models.report import LabParameter
from app.services.ocr import OcrEnvelope
from app.services.reference_ranges import classify_status, get_reference_range

_SYNONYMS_PATH = Path(__file__).resolve().parents[3] / "data" / "synonyms" / "lab_synonyms.json"

_ISO_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_NUMERIC_DATE_RE = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b")
_DAY_MONTH_NAME_RE = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?[\s.\-/]*([A-Za-z]{3,9})[\s.,\-/]+(\d{4})\b")
_MONTH_NAME_DAY_RE = re.compile(r"\b([A-Za-z]{3,9})[\s.\-/]+(\d{1,2})(?:st|nd|rd|th)?[\s.,\-/]+(\d{4})\b")
_DATE_LABEL_RE = re.compile(r"\b(report|collect|sample|drawn|receiv|registrat|date)\w*\b", re.IGNORECASE)
_MONTHS = {
    name: number
    for number, name in enumerate(
        ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), start=1
    )
}
_VALUE_RE = re.compile(r"-?\d+(?:\.\d+)?")
_UNIT_RE = re.compile(r"^[A-Za-z%µu][A-Za-z%/µ0-9.^-]*$")
_VALUE_WITH_UNIT_RE = re.compile(r"^(?P<value>-?\d+(?:\.\d+)?)\s*(?P<unit>%|[A-Za-z/µ][A-Za-z/µ0-9.^]*)?$")
_RANGE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:-|–|—|to)\s*(\d+(?:\.\d+)?)", re.IGNORECASE)
_UPPER_BOUND_RE = re.compile(r"(?:<=?|upto|up to|less than|max)\s*(\d+(?:\.\d+)?)", re.IGNORECASE)
_LOWER_BOUND_RE = re.compile(r"(?:>=?|greater than|min|above)\s*(\d+(?:\.\d+)?)", re.IGNORECASE)
_MEASUREMENT_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9 ()/,'-]+?)[\s:]+(?P<value>-?\d+(?:\.\d+)?)\s*(?P<unit>%|[A-Za-z/]+(?:/[A-Za-z]+)?)?\s*$"
)

# Words labs wrap around a parameter name that carry no identifying meaning.
_NOISE_TOKENS = frozenset({"serum", "plasma", "blood", "total", "level", "levels", "test", "estimation"})
_FUZZY_ACCEPT_SCORE = 92.0
_FUZZY_MARGIN = 4.0

# Conversions into each parameter's canonical unit (implementation-plan.md Section 2.4).
_UNIT_CONVERSIONS: dict[str, dict[str, float]] = {
    "glucose_fasting": {"mmol/l": 18.0182},
    "glucose_pp": {"mmol/l": 18.0182},
    "ldl": {"mmol/l": 38.67},
    "hdl": {"mmol/l": 38.67},
    "total_cholesterol": {"mmol/l": 38.67},
    "triglycerides": {"mmol/l": 88.57},
    "vitamin_d": {"nmol/l": 1 / 2.496},
}


def _clean_name(name: str) -> str:
    """Lower-case, drop punctuation, collapse spaces: `25-OH VITAMIN D (TOTAL)` -> `25 oh vitamin d total`."""
    return " ".join(re.sub(r"[^0-9a-z]+", " ", name.casefold()).split())


def _core_tokens(name: str) -> str:
    """Cleaned name minus filler words, so `Serum Creatinine` and `Creatinine` collapse together."""
    words = _clean_name(name).split()
    return " ".join([word for word in words if word not in _NOISE_TOKENS] or words)


def _squash(name: str) -> str:
    """All separators removed, so `VITAMIN B-12` and `Vitamin B12` become one key."""
    return _clean_name(name).replace(" ", "")


@lru_cache
def _synonym_index() -> tuple[dict[str, str], dict[str, str], tuple[tuple[str, str], ...]]:
    """`(cleaned -> key, squashed -> key, (core tokens, key) pairs used for fuzzy matching)`."""
    raw = json.loads(_SYNONYMS_PATH.read_text(encoding="utf-8"))
    cleaned: dict[str, str] = {}
    squashed: dict[str, str] = {}
    cores: list[tuple[str, str]] = []

    for canonical_key, synonyms in raw.items():
        if canonical_key.startswith("_"):
            continue
        for label in (canonical_key, canonical_key.replace("_", " "), *synonyms):
            cleaned.setdefault(_clean_name(label), canonical_key)
            cleaned.setdefault(_core_tokens(label), canonical_key)
            squashed.setdefault(_squash(label), canonical_key)
            cores.append((_core_tokens(label), canonical_key))
    return cleaned, squashed, tuple(cores)


def _fuzzy_key(name: str) -> str | None:
    """Best fuzzy match, accepted only when it clearly beats every other parameter.

    The margin guard matters because sibling analytes read almost identically (`LDL` vs `HDL`
    Cholesterol), and a wrong key would silently corrupt a comparison.
    """
    from rapidfuzz import fuzz

    candidate = _core_tokens(name)
    best_by_key: dict[str, float] = {}
    for core, canonical_key in _synonym_index()[2]:
        score = fuzz.token_sort_ratio(candidate, core)
        if score > best_by_key.get(canonical_key, 0.0):
            best_by_key[canonical_key] = score

    ranked = sorted(best_by_key.items(), key=lambda item: item[1], reverse=True)
    if not ranked:
        return None
    best_key, best_score = ranked[0]
    runner_up = ranked[1][1] if len(ranked) > 1 else 0.0
    if best_score >= _FUZZY_ACCEPT_SCORE and best_score - runner_up >= _FUZZY_MARGIN:
        return best_key
    return None


def _canonical_key(name: str) -> str | None:
    cleaned = _clean_name(name)
    if not cleaned:
        return None
    cleaned_index, squashed_index, _ = _synonym_index()
    return (
        cleaned_index.get(cleaned)
        or squashed_index.get(_squash(name))
        or cleaned_index.get(_core_tokens(name))
        or _fuzzy_key(name)
    )


def _normalize_unit(unit: str) -> str:
    return unit.strip().casefold().replace("μ", "u").replace("µ", "u")


def _convert(canonical_key: str, value: float, unit: str, target_unit: str) -> float:
    """Convert `value` into `target_unit`; unknown pairings are left untouched."""
    source = _normalize_unit(unit)
    if source == _normalize_unit(target_unit):
        return value
    factor = _UNIT_CONVERSIONS.get(canonical_key, {}).get(source)
    return round(value * factor, 2) if factor else value


def _parse_date(text: str) -> str | None:
    """Read one printed date in any of the layouts labs use, as ISO `YYYY-MM-DD`."""
    iso = _ISO_DATE_RE.search(text)
    if iso:
        return iso.group(0)

    numeric = _NUMERIC_DATE_RE.search(text)
    if numeric:
        day, month, year = numeric.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"

    for pattern, order in ((_DAY_MONTH_NAME_RE, "dmy"), (_MONTH_NAME_DAY_RE, "mdy")):
        match = pattern.search(text)
        if not match:
            continue
        day, name, year = match.groups() if order == "dmy" else (match.group(2), match.group(1), match.group(3))
        month = _MONTHS.get(name[:3].casefold())
        if month and 1 <= int(day) <= 31:
            return f"{year}-{month:02d}-{int(day):02d}"
    return None


def find_report_date(ocr: OcrEnvelope) -> str | None:
    """The printed report date, or `None` when the document does not state one.

    Lines that name the date are read first, so a collection date wins over any stray date
    elsewhere on the page.
    """
    texts = [line.text for line in ocr.lines]
    labelled = [text for text in texts if _DATE_LABEL_RE.search(text)]
    for text in (*labelled, *texts):
        parsed = _parse_date(text)
        if parsed:
            return parsed
    return None


def extract_report_date(ocr: OcrEnvelope) -> str:
    """Report date from the layout key-value lines, falling back to today (Section 2.4)."""
    return find_report_date(ocr) or datetime.now(UTC).strftime("%Y-%m-%d")


def _rows_from_tables(tables: list[list[list[str]]]) -> list[tuple[str, str, str, str]]:
    """`(name, value, unit, printed range)` tuples from `prebuilt-layout` result tables.

    Labs order columns differently (name/method/result/unit/range), so the result is the first
    numeric cell after the name and the unit is taken from that cell or the next unit-shaped one.
    """
    rows = []
    for table in tables:
        for row in table:
            cells = [cell.strip() for cell in row]
            if len(cells) < 2 or not cells[0]:
                continue
            match = None
            index = 0
            for position in range(1, len(cells)):
                match = _VALUE_WITH_UNIT_RE.match(cells[position])
                if match:
                    index = position
                    break
            if match is None:
                continue
            trailing = [cell for cell in cells[index + 1 :] if cell]
            unit = match.group("unit") or next((cell for cell in trailing if _UNIT_RE.match(cell)), "")
            printed_range = next((cell for cell in trailing if _RANGE_RE.search(cell)), "")
            rows.append((cells[0], match.group("value"), unit, printed_range))
    return rows


def _rows_from_lines(lines: list[str]) -> list[tuple[str, str, str, str]]:
    """Fallback for reports whose results are plain text lines rather than a table."""
    rows = []
    for text in lines:
        match = _MEASUREMENT_RE.match(text.strip())
        if match:
            rows.append((match.group("name"), match.group("value"), match.group("unit") or "", ""))
    return rows


def parse_reference_range(text: str) -> tuple[float | None, float | None]:
    """Read the range a lab printed next to a result: `70 - 99`, `< 200`, `Upto 150`, `>= 40`."""
    if not text:
        return None, None

    bounded = _RANGE_RE.search(text)
    if bounded:
        low, high = float(bounded.group(1)), float(bounded.group(2))
        return (low, high) if low <= high else (high, low)

    upper = _UPPER_BOUND_RE.search(text)
    if upper:
        return None, float(upper.group(1))

    lower = _LOWER_BOUND_RE.search(text)
    if lower:
        return float(lower.group(1)), None
    return None, None


def _fallback_key(name: str) -> str:
    """Stable key for a parameter with no curated entry, e.g. `SERUM ZINC` -> `zinc`.

    Built from the noise-stripped tokens so the same analyte aligns across reports that word it
    slightly differently.
    """
    return "_".join(_core_tokens(name).split()) or _squash(name)


def normalize(ocr: OcrEnvelope) -> list[LabParameter]:
    """Synonym-map parameter names, convert units, extract report date, compute `status`.

    Curated ranges win for the canonical parameters (they stay consistent across labs); every
    other analyte is kept too, graded against the range printed on the report itself.
    """
    report_date = extract_report_date(ocr)
    confidence = round(statistics.mean(line.confidence for line in ocr.lines), 4) if ocr.lines else 0.95

    raw_rows = _rows_from_tables(ocr.tables) or _rows_from_lines([line.text for line in ocr.lines])

    parameters: dict[str, LabParameter] = {}
    for name, raw_value, raw_unit, printed_range in raw_rows:
        canonical_key = _canonical_key(name) or _fallback_key(name)
        if not canonical_key or canonical_key in parameters:
            continue

        value = float(raw_value)
        unit = raw_unit
        reference: dict | None = None
        try:
            reference = get_reference_range(canonical_key)
        except NotFoundError:
            reference = None

        if reference is not None:
            value = _convert(canonical_key, value, raw_unit, reference["unit"])
            unit = reference["unit"]
            ref_low, ref_high = reference["refLow"], reference["refHigh"]
        else:
            ref_low, ref_high = parse_reference_range(printed_range)

        status = "unknown" if ref_low is None and ref_high is None else classify_status(value, ref_low, ref_high)
        parameters[canonical_key] = LabParameter(
            canonicalKey=canonical_key,
            displayName=name.strip(),
            value=value,
            unit=unit,
            refLow=ref_low,
            refHigh=ref_high,
            status=status,
            reportDate=report_date,
            sourceConfidence=confidence,
        )

    return list(parameters.values())
