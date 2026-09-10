"""Share-link security rules (implementation-plan.md Section 5.2)."""

import pytest

from app.errors import GoneError, NotFoundError, RateLimitedError
from app.repositories import sql_repo
from app.services import share_links


async def _new_link(blob_path: str, *, user_id: str = "demo-user") -> tuple[str, str]:
    return await share_links.create_share_link(blob_path, user_id=user_id, run_id="run-test")


async def test_token_is_opaque_and_only_its_hash_is_stored() -> None:
    share_id, _ = await _new_link("generated-pdfs/demo-user/2026-09/doc.pdf")

    assert len(share_id) >= 20
    assert share_id not in sql_repo._DEMO_SHARE_LINKS
    assert share_links._hash(share_id) in sql_repo._DEMO_SHARE_LINKS


async def test_valid_token_resolves_to_its_blob_path() -> None:
    blob_path = "generated-pdfs/demo-user/2026-09/resolve.pdf"
    share_id, expires_at = await _new_link(blob_path)

    assert await share_links.resolve_share_link(share_id, client_ip="203.0.113.9") == blob_path
    assert expires_at > ""


async def test_unknown_token_is_rejected() -> None:
    with pytest.raises(NotFoundError):
        await share_links.resolve_share_link("not-a-real-token", client_ip="203.0.113.10")


async def test_expired_token_is_gone() -> None:
    share_id, _ = await _new_link("generated-pdfs/demo-user/2026-09/expired.pdf")
    sql_repo._DEMO_SHARE_LINKS[share_links._hash(share_id)]["expiresAt"] = "2020-01-01T00:00:00+00:00"

    with pytest.raises(GoneError):
        await share_links.resolve_share_link(share_id, client_ip="203.0.113.11")


async def test_requests_are_rate_limited_per_ip() -> None:
    share_id, _ = await _new_link("generated-pdfs/demo-user/2026-09/limited.pdf")
    client_ip = "203.0.113.12"

    for _ in range(share_links.RATE_LIMIT_PER_MINUTE):
        await share_links.resolve_share_link(share_id, client_ip=client_ip)

    with pytest.raises(RateLimitedError):
        await share_links.resolve_share_link(share_id, client_ip=client_ip)


async def test_every_access_is_logged_with_a_hashed_ip() -> None:
    share_id, _ = await _new_link("generated-pdfs/demo-user/2026-09/audited.pdf")
    client_ip = "203.0.113.20"

    await share_links.resolve_share_link(share_id, client_ip=client_ip)
    await share_links.resolve_share_link(share_id, client_ip=client_ip)

    record = sql_repo._DEMO_SHARE_LINKS[share_links._hash(share_id)]
    assert record["accessCount"] == 2
    assert record["lastAccessAt"] is not None
    assert record["lastAccessIpHash"] == share_links._hash(client_ip)
    assert client_ip not in str(record)


async def test_revoked_token_is_gone() -> None:
    share_id, _ = await _new_link("generated-pdfs/demo-user/2026-09/revoked.pdf")

    await share_links.revoke_share_link(share_id, user_id="demo-user")

    with pytest.raises(GoneError):
        await share_links.resolve_share_link(share_id, client_ip="203.0.113.21")


async def test_only_the_owner_can_revoke_a_link() -> None:
    share_id, _ = await _new_link("generated-pdfs/demo-user/2026-09/owned.pdf")

    with pytest.raises(NotFoundError):
        await share_links.revoke_share_link(share_id, user_id="someone-else")

    assert await share_links.resolve_share_link(share_id, client_ip="203.0.113.22")

