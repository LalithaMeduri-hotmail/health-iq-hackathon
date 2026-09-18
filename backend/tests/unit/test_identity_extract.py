from app.services.identity_extract import extract
from app.services.ocr import OcrEnvelope, OcrLine


def _envelope(*texts: str) -> OcrEnvelope:
    lines = [OcrLine(text=text, confidence=0.99, bbox=[]) for text in texts]
    return OcrEnvelope(pages=1, lines=lines, tables=[], handwritten_ratio=0.0, source="pdf-text")


def test_patient_name_stops_before_the_next_field_on_the_same_line() -> None:
    """Lab headers pack fields onto one line; the label must not become part of the name."""
    evidence = extract(_envelope("Patient: Rohan Sharma    Age/Sex: 42 / M"))

    assert evidence.identity.patient_name == "Rohan Sharma"


def test_patient_name_is_read_when_it_is_the_only_field_on_the_line() -> None:
    evidence = extract(_envelope("Patient Name: Asha Rao"))

    assert evidence.identity.patient_name == "Asha Rao"
