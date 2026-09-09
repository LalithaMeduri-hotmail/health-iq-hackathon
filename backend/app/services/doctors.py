"""Curated registry of clinicians who can receive a Health IQ review request.

Demo/dev source is `data/doctors/registered_doctors.csv` (assumption A4 in
docs/lld/6-low-level-design-doctor-review-pdf-secure-share.md: no real practitioner directory).
Raw addresses stay in this module and the mailer; every API surface shows the masked form.
"""

import csv
from functools import lru_cache
from pathlib import Path

from app.errors import NotFoundError
from app.models.review import RegisteredDoctor

_REGISTRY_CSV_PATH = Path(__file__).resolve().parents[3] / "data" / "doctors" / "registered_doctors.csv"


def mask_email(email: str) -> str:
    """`duttadebopriya3@gmail.com` -> `d***@gmail.com`."""
    local, _, domain = email.partition("@")
    if not domain:
        return "***"
    return f"{local[:1]}***@{domain}"


@lru_cache
def _rows() -> list[dict]:
    with _REGISTRY_CSV_PATH.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def list_doctors() -> list[RegisteredDoctor]:
    """Every registered clinician, with the address masked for display."""
    return [
        RegisteredDoctor(
            doctorId=row["doctorId"],
            name=row["name"],
            specialty=row["specialty"],
            registrationNo=row["registrationNo"],
            emailMasked=mask_email(row["email"]),
        )
        for row in _rows()
    ]


def get_address(doctor_id: str) -> tuple[RegisteredDoctor, str]:
    """Resolve one clinician to `(display record, real address)`; raises when unknown."""
    row = next((candidate for candidate in _rows() if candidate["doctorId"] == doctor_id), None)
    if row is None:
        raise NotFoundError(f"Doctor {doctor_id!r} is not in the Health IQ registry")

    doctor = RegisteredDoctor(
        doctorId=row["doctorId"],
        name=row["name"],
        specialty=row["specialty"],
        registrationNo=row["registrationNo"],
        emailMasked=mask_email(row["email"]),
    )
    return doctor, row["email"]
