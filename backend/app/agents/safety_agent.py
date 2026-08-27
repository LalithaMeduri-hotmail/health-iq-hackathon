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

from dataclasses import dataclass
from typing import Any

BANNED_PHRASES = (
    "you have",
    "diagnosed with",
    "stop taking",
    "replace your",
    "cure",
    "guaranteed",
)


@dataclass(frozen=True)
class SafetyVerdict:
    passed: bool
    violations: list[str]
    redacted_payload: Any


def review(payload: Any) -> SafetyVerdict:
    """Run rules R1-R6 against `payload` and return the verdict."""
    raise NotImplementedError
