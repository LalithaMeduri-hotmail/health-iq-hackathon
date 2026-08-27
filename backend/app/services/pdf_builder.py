"""Doctor-review PDF builder, ReportLab (implementation-plan.md Section 5.3). Owner: D3.

Contract frozen for D4 consumption: `build(analysis) -> bytes`.

Sections, in order: header ("Doctor Review Request - Not a Prescription"), patient block
(consented fields only), prescribed medicines table (with OCR confidence), suggested
equivalents table (source + source date), doctor approval section (Approve/Modify/Reject,
notes, signature/date), footer disclaimer + provenance list + "Data is demo/curated" notice.
"""

from app.models.medicine import MedicineAnalysis


def build(analysis: MedicineAnalysis) -> bytes:
    """Render the 6-section doctor-review PDF and return the raw bytes."""
    raise NotImplementedError
