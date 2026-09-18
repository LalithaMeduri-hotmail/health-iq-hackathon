"""Audit-event writer.

Audit records answer "who touched which resource, and was it allowed" - they must never carry
medical content. `detail` is restricted to short structural codes (a match status, a denial
reason), and this module drops anything longer so a careless caller cannot leak PHI into the
audit container.
"""

import logging
import uuid

from app.models.audit import AuditEvent, AuditOutcome
from app.repositories import cosmos_repo

logger = logging.getLogger(__name__)

_MAX_DETAIL_LENGTH = 120


async def record(
    *,
    account_id: str,
    action: str,
    profile_id: str | None = None,
    resource_type: str = "",
    resource_id: str | None = None,
    correlation_id: str = "",
    outcome: str = AuditOutcome.SUCCESS,
    detail: str = "",
) -> None:
    """Append one audit event. Never raises: a failed audit write must not fail the request."""
    event = AuditEvent(
        id=f"audit-{uuid.uuid4().hex[:16]}",
        accountId=account_id,
        profileId=profile_id,
        action=action,
        resourceType=resource_type,
        resourceId=resource_id,
        correlationId=correlation_id,
        outcome=outcome,
        detail=detail[:_MAX_DETAIL_LENGTH],
    )
    try:
        await cosmos_repo.record_audit_event(event)
    except Exception:  # noqa: BLE001 - auditing is best-effort, the request already succeeded
        logger.warning("audit write failed for action=%s outcome=%s", action, outcome)
