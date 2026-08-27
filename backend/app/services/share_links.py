"""Secure share links (implementation-plan.md Section 5.2). Owner: D3.

`shareId` is a 128-bit URL-safe random token, stored hashed (SHA-256) in SQL `ShareLink`. Backend
issues a user-delegation SAS valid 24h, read-only, single blob. Rate limit 20 req/min/IP; log
every access with timestamp + `ipHash`. No PHI in the URL; the token is opaque and revocable.
"""


def create_share_link(blob_path: str) -> tuple[str, str]:
    """Create a new share token. Returns `(shareId, sasUrl)`."""
    raise NotImplementedError


def resolve_share_link(share_id: str, *, client_ip: str) -> str:
    """Validate the token, enforce rate limiting, log access, and return the SAS URL to redirect to."""
    raise NotImplementedError
