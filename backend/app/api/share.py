"""GET /api/v1/share/{shareId} and its revocation route (implementation-plan.md Section 5.2).

Calls `services/share_links.py`: validates the hashed token, rate-limits 20 req/min/IP, logs
timestamp + `ipHash`, then redirects to a read-only user-delegation SAS URL. Revocation is
owner-scoped and makes every later resolve return `410 gone`.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse

from app.config import get_settings
from app.deps import CurrentUser, get_current_user
from app.models.common import ApiResponse, SafetyBlock
from app.services import blob, share_links

router = APIRouter(prefix="/api/v1/share", tags=["share"])


@router.get("/{share_id}")
async def resolve(share_id: str, request: Request, download: bool = False):
    """Public, unauthenticated route: the opaque token is the only credential. No PHI in the URL."""
    client_ip = request.client.host if request.client else "unknown"
    blob_path = await share_links.resolve_share_link(share_id, client_ip=client_ip)
    filename = await share_links.filename_for(share_id)

    settings = get_settings()
    if not settings.demo_mode and settings.azure_storage_account_name:
        sas_url = await share_links.build_sas_url(blob_path, filename=filename, download=download)
        return RedirectResponse(url=sas_url, status_code=302)

    content = await blob.read_generated_pdf(blob_path)
    disposition = "attachment" if download else "inline"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'{disposition}; filename="{filename}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/{share_id}/revoke")
async def revoke(
    share_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> ApiResponse[dict]:
    """Owner-scoped revocation (FR5.6): the link stops resolving immediately."""
    await share_links.revoke_share_link(share_id, user_id=current_user.user_id)
    return ApiResponse(
        request_id=getattr(request.state, "request_id", str(uuid.uuid4())),
        generated_at=datetime.now(UTC),
        safety=SafetyBlock(pass_=True, notes=[], reviewer_version="safety-1.0.0"),
        data={"revoked": True},
    )

