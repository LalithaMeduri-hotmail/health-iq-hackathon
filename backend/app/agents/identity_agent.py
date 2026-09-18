"""`IdentityExplanationAgent` - plain-language narrative for a profile-match verdict. Owner: D3.

This agent is deliberately powerless. `services/identity_match.py` has already decided the
verdict by the time it runs; its only job is to turn the field-by-field comparison into a
sentence a non-clinical reader can act on.

Guardrails (agents.instructions.md):

* It receives the *verdict*, never the raw document text, so nothing it writes can change it.
* It sees only the selected profile's own name and date of birth - no other profile, and no
  medical content from the document.
* If the model is unavailable or returns anything unexpected, the deterministic fallback
  sentence is used. An identity explanation is never allowed to block an upload.
"""

import logging

from app.config import get_settings
from app.models.medical_document import (
    IdentityEvidence,
    ProfileMatchExplanation,
    ProfileMatchStatus,
)
from app.models.patient_profile import PatientProfile

logger = logging.getLogger(__name__)

PROMPT_VERSION = "identity-explain-1.0.0"

_MAX_NARRATIVE_CHARS = 400

_FALLBACK = {
    ProfileMatchStatus.MATCH: (
        "The identity on this document lines up with this profile. Confirm it belongs to this "
        "person before we file it."
    ),
    ProfileMatchStatus.POSSIBLE_MATCH: (
        "Some identity details line up and others could not be confirmed. Check the comparison "
        "below and choose the right person."
    ),
    ProfileMatchStatus.MISMATCH: (
        "The identity on this document does not match this profile, so we have not filed it. "
        "Choose the right person or create a new profile."
    ),
    ProfileMatchStatus.INSUFFICIENT_IDENTITY_DATA: (
        "This document does not show enough identity details for us to check it. Confirm "
        "explicitly that it belongs to this person before we process it."
    ),
}

_SYSTEM_PROMPT = (
    "You explain, in two short sentences of plain English, why a medical document's identity "
    "details did or did not line up with a patient profile. You are given a decision that has "
    "already been made. Never contradict it, never state or imply that you are deciding "
    "anything, never guess at missing values, and never mention medical content. Address the "
    "reader as 'you'."
)


def _deterministic(match: ProfileMatchExplanation) -> str:
    """Verdict sentence plus the per-field reasons, with no model involved."""
    lead = _FALLBACK.get(match.status, _FALLBACK[ProfileMatchStatus.INSUFFICIENT_IDENTITY_DATA])
    reasons = " ".join(comparison.detail for comparison in match.comparisons if comparison.detail)
    return f"{lead} {reasons}".strip()[:_MAX_NARRATIVE_CHARS]


async def explain(
    profile: PatientProfile, evidence: IdentityEvidence, match: ProfileMatchExplanation
) -> str:
    """Return a narrative for the verdict, falling back to deterministic text on any problem."""
    fallback = _deterministic(match)

    settings = get_settings()
    if settings.demo_mode or not settings.azure_openai_endpoint:
        return fallback

    try:
        from app.deps import get_chat_client

        # Only the comparison outcomes are sent - not the document text, and not the values of
        # any field the evaluator did not already surface to the user.
        comparisons = "; ".join(
            f"{comparison.field}: {comparison.outcome}" for comparison in match.comparisons
        )
        prompt = (
            f"Decision: {match.status}. Field outcomes: {comparisons}. "
            f"Profile name shown to the user: {profile.display_name}. "
            f"Document name shown to the user: {evidence.identity.patient_name or 'not shown'}."
        )
        agent = get_chat_client().as_agent(instructions=_SYSTEM_PROMPT, name="IdentityExplainer")
        response = await agent.run(prompt)
        text = (getattr(response, "text", "") or "").strip()
    except Exception:  # noqa: BLE001 - never let the explainer break the upload flow
        logger.warning("identity narrative unavailable; using deterministic text")
        return fallback

    if not text or len(text) > _MAX_NARRATIVE_CHARS:
        return fallback
    return text
