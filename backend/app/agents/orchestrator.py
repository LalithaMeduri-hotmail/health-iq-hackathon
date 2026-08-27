"""Agent orchestration (.github/instructions/agents.instructions.md). Owner: D3.

Builds one `ChatAgent` per role over `AzureOpenAIChatClient` + `DefaultAzureCredential` (no API
keys), registers `tools.py` function tools, and routes by intent to exactly one feature agent
via a sequential tool workflow. `SafetyReviewerAgent` is a mandatory final stage on every
user-facing payload.

    request -> feature agent -> (tools: OCR/normalize/RAG/SQL/PDF) -> draft -> SafetyReviewerAgent -> response
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AgentResult:
    """`run(feature, payload) -> AgentResult`. Consumed by `api/` routers (D4)."""

    data: Any
    safety_pass: bool
    safety_notes: list[str]


async def run(feature: str, payload: dict) -> AgentResult:
    """Route `feature` (e.g. "prescription", "report", "comparison", "specialist", "meal-plan")

    to its agent, then always run `safety_agent.review()` before returning.
    """
    raise NotImplementedError
