"""GET /api/v1/share/{shareId} (implementation-plan.md Section 5.2).

Calls `services/share_links.py`: validates the hashed token, rate-limits 20 req/min/IP, logs
timestamp + `ipHash`, then redirects to a 24h read-only user-delegation SAS URL.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/share", tags=["share"])

# TODO: GET /{shareId} -> HTML page or 302 to the SAS URL. No PHI in the URL.
