"""`SafetyReviewerAgent` - mandatory final stage on every user-facing payload. Owner: D3.

Tools: `check_citations`, `check_disclaimers`, `check_prohibited_claims`. Output: `SafetyVerdict`.
Run cheap deterministic checks (R1-R6) before any LLM classification turn; fail closed if the
safety reviewer itself errors.

| Rule | Check |
|------|-------|
| R1 | Payload contains the standard disclaimer string |
| R2 | Every medical/nutritional claim carries `sourceUrl` + `sourceDate` |
| R3 | No banned phrases: "you have", "diagnosed with", "stop taking", "replace your", "cure", "guaranteed" |
| R4 | Alternatives carry `doctorApprovalRequired=true` and `savingsEstimated=true` |
| R5 | Confidence below threshold forces `needsUserConfirmation=true` |
| R6 | No PHI leaked back into shareable artifacts beyond what consent permits |

Violations of R3-R6 are hard failures: return the redacted payload plus a `safety` block.
"""

"""`SafetyReviewerAgent` - mandatory final stage on every user-facing payload. Owner: D3.

Tools: `check_citations`, `check_disclaimers`, `check_prohibited_claims`. Output: `SafetyVerdict`.
Run cheap deterministic checks (R1-R6) before any LLM classification turn; fail closed if the
safety reviewer itself errors.

| Rule | Check |
|------|-------|
| R1 | Payload contains the standard disclaimer string |
| R2 | Every medical/nutritional claim carries `sourceUrl` + `sourceDate` |
| R3 | No banned phrases: "you have", "diagnosed with", "stop taking", "replace your", "cure", "guaranteed" |
| R4 | Alternatives carry `doctorApprovalRequired=true` and `savingsEstimated=true` |
| R5 | Confidence below threshold forces `needsUserConfirmation=true` |
| R6 | No PHI leaked back into shareable artifacts beyond what consent permits |

Violations of R3-R6 are hard failures: return the redacted payload plus a `safety` block.
"""

import copy
import re
from dataclasses import dataclass
from typing import Any

from app.config import get_settings
from app.models.common import DISCLAIMER_TEXT
from app.services.deidentify import EMAIL_RE, PHONE_RE

BANNED_PHRASES = (
    "you have",
    "diagnosed with",
    "stop taking",
    "replace your",
    "cure",
    "guaranteed",
)

_PHI_PATTERNS = (EMAIL_RE, PHONE_RE)


@dataclass(frozen=True)
class SafetyVerdict:
    passed: bool
    violations: list[str]
    redacted_payload: Any


def _iter_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _iter_strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _iter_strings(item)


def _check_r1_disclaimer(payload: dict) -> list[str]:
    disclaimers = payload.get("disclaimers")
    if disclaimers is not None and DISCLAIMER_TEXT not in disclaimers:
        return ["R1: missing standard disclaimer text in `disclaimers`"]
    return []


def _check_r2_citations(payload: dict) -> list[str]:
    violations = []
    for alt in payload.get("alternatives", []) or []:
        source = alt.get("source") or {}
        if not source.get("sourceUrl") or not source.get("sourceDate"):
            violations.append(f"R2: alternative {alt.get('original', '?')!r} missing sourceUrl/sourceDate")
    return violations


def _check_r3_banned_phrases(payload: dict) -> list[str]:
    violations = []
    for text in _iter_strings(payload):
        lowered = text.lower()
        for phrase in BANNED_PHRASES:
            if phrase in lowered:
                violations.append(f"R3: banned phrase {phrase!r} found in payload text")
    return violations


def _check_r4_alternatives(payload: dict) -> list[str]:
    violations = []
    for alt in payload.get("alternatives", []) or []:
        if not alt.get("doctorApprovalRequired"):
            violations.append(f"R4: alternative {alt.get('original', '?')!r} missing doctorApprovalRequired=true")
        if not alt.get("savingsEstimated"):
            violations.append(f"R4: alternative {alt.get('original', '?')!r} missing savingsEstimated=true")
    return violations


def _check_r5_confidence_gate(payload: dict) -> list[str]:
    threshold = get_settings().ocr_confidence_threshold
    violations = []
    for item in payload.get("items", []) or []:
        confidence = item.get("ocrConfidence")
        if confidence is not None and confidence < threshold and not item.get("needsUserConfirmation"):
            violations.append(f"R5: item {item.get('lineId', '?')!r} below confidence gate without needsUserConfirmation")
    return violations


def _check_r6_phi(payload: dict) -> list[str]:
    violations = []
    for text in _iter_strings(payload):
        for pattern in _PHI_PATTERNS:
            if pattern.search(text):
                violations.append("R6: possible PHI (email/phone) detected in shareable payload")
                break
    return violations


def review(payload: Any) -> SafetyVerdict:
    """Run rules R1-R6 against `payload` and return the verdict.

    `payload` is the feature-specific `data` dict (already `.model_dump(by_alias=True)`-shaped).
    Fails closed: any exception during review is itself treated as a hard failure.
    """
    try:
        if not isinstance(payload, dict):
            return SafetyVerdict(passed=False, violations=["safety reviewer requires a dict payload"], redacted_payload=None)

        violations = [
            *_check_r1_disclaimer(payload),
            *_check_r2_citations(payload),
            *_check_r3_banned_phrases(payload),
            *_check_r4_alternatives(payload),
            *_check_r5_confidence_gate(payload),
            *_check_r6_phi(payload),
        ]
        passed = len(violations) == 0
        redacted_payload = payload if passed else copy.deepcopy(payload)
        return SafetyVerdict(passed=passed, violations=violations, redacted_payload=redacted_payload)
    except Exception as exc:  # noqa: BLE001 - fail closed per module contract
        return SafetyVerdict(passed=False, violations=[f"safety reviewer error (fail-closed): {exc}"], redacted_payload=None)
