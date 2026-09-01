"""GET /api/v1/share/{shareId} (implementation-plan.md Section 5.2).

Calls `services/share_links.py`: validates the hashed token, rate-limits 20 req/min/IP, logs
timestamp + `ipHash`, then redirects to a 24h read-only user-delegation SAS URL.
"""

from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse

from app.config import get_settings
from app.services import blob, share_links

router = APIRouter(prefix="/api/v1/share", tags=["share"])


@router.get("/{share_id}")
async def resolve(share_id: str, request: Request):
    """Public, unauthenticated route: the opaque token is the only credential. No PHI in the URL."""
    client_ip = request.client.host if request.client else "unknown"
    blob_path = await share_links.resolve_share_link(share_id, client_ip=client_ip)

    settings = get_settings()
    if not settings.demo_mode and settings.azure_storage_account_name:
        return RedirectResponse(url=await share_links.build_sas_url(blob_path), status_code=302)

    content = await blob.read_generated_pdf(blob_path)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'inline; filename="health-iq-doctor-review.pdf"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
