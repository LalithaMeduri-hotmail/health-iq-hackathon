"""Share-link security rules (implementation-plan.md Section 5.2)."""

import pytest

from app.errors import ForbiddenError, NotFoundError, RateLimitedError
from app.repositories import sql_repo
from app.services import share_links


async def test_token_is_opaque_and_only_its_hash_is_stored() -> None:
    share_id, _ = await share_links.create_share_link("generated-pdfs/demo-user/2026-09/doc.pdf")

    assert len(share_id) >= 20
    assert share_id not in sql_repo._DEMO_SHARE_LINKS
    assert share_links._hash(share_id) in sql_repo._DEMO_SHARE_LINKS


async def test_valid_token_resolves_to_its_blob_path() -> None:
    blob_path = "generated-pdfs/demo-user/2026-09/resolve.pdf"
    share_id, expires_at = await share_links.create_share_link(blob_path)

    assert await share_links.resolve_share_link(share_id, client_ip="203.0.113.9") == blob_path
    assert expires_at > ""


async def test_unknown_token_is_rejected() -> None:
    with pytest.raises(NotFoundError):
        await share_links.resolve_share_link("not-a-real-token", client_ip="203.0.113.10")


async def test_expired_token_is_rejected() -> None:
    share_id, _ = await share_links.create_share_link("generated-pdfs/demo-user/2026-09/expired.pdf")
    sql_repo._DEMO_SHARE_LINKS[share_links._hash(share_id)]["expiresAt"] = "2020-01-01T00:00:00+00:00"

    with pytest.raises(ForbiddenError):
        await share_links.resolve_share_link(share_id, client_ip="203.0.113.11")


async def test_requests_are_rate_limited_per_ip() -> None:
    share_id, _ = await share_links.create_share_link("generated-pdfs/demo-user/2026-09/limited.pdf")
    client_ip = "203.0.113.12"

    for _ in range(share_links.RATE_LIMIT_PER_MINUTE):
        await share_links.resolve_share_link(share_id, client_ip=client_ip)

    with pytest.raises(RateLimitedError):
        await share_links.resolve_share_link(share_id, client_ip=client_ip)
