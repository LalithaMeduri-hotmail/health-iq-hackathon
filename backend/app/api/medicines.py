"""POST /api/v1/medicines/alternatives (implementation-plan.md Section 5.1).

Calls `services/normalize_medicine.py` alternative-matching rules (Section 2.3) grounded via
`rag/retrieve.py` against `idx-medicines`.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/medicines", tags=["medicines"])

# TODO: POST /alternatives - { items[] } -> { alternatives[{ original, generic, cheaper,
#       savingsPct, source, doctorApprovalRequired }] } (app.models.medicine.MedicinesAlternativesResponse)
