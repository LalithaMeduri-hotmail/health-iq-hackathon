"""Outbound mail for doctor-review requests.

Preferred transport: Azure Communication Services Email, authenticated with
`DefaultAzureCredential` so no mailbox password exists to leak. With `azure_communication_endpoint`
unset - or when the ACS send fails for any reason - the mailer falls back to preview mode and
writes the full RFC-822 message to `<repo>/.local-mail/*.eml`, so the flow is always exercisable
and a transport outage never silently drops a review.
"""

import logging
import re
import uuid
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path

from app.config import get_settings
from app.errors import UpstreamUnavailableError

logger = logging.getLogger(__name__)

_LOCAL_MAIL_ROOT = Path(__file__).resolve().parents[3] / ".local-mail"
_ADDRESS_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def is_preview_mode() -> bool:
    """True when no transport is configured, so nothing is actually delivered."""
    return not get_settings().azure_communication_endpoint


def sender() -> str:
    """The single From identity, identical on every message Health IQ sends."""
    settings = get_settings()
    address = settings.acs_sender_address or "no-reply@healthiq.invalid"
    return f"{settings.mail_sender_name} <{address}>"


def _write_preview(
    to_address: str,
    subject: str,
    text_body: str,
    html_body: str | None,
    attachment: tuple[str, bytes] | None,
) -> str:
    message = EmailMessage()
    message["From"] = sender()
    message["To"] = to_address
    # Header injection defence: strip anything that could start a new header line.
    message["Subject"] = subject.replace("\r", " ").replace("\n", " ")
    message["Date"] = datetime.now(UTC).strftime("%a, %d %b %Y %H:%M:%S +0000")
    message.set_content(text_body)
    # The text part stays first so clients that refuse HTML still show the approval URL.
    if html_body:
        message.add_alternative(html_body, subtype="html")
    if attachment is not None:
        filename, content = attachment
        message.add_attachment(content, maintype="application", subtype="pdf", filename=filename)

    _LOCAL_MAIL_ROOT.mkdir(parents=True, exist_ok=True)
    target = _LOCAL_MAIL_ROOT / f"{datetime.now(UTC):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}.eml"
    target.write_bytes(bytes(message))
    return "preview"


async def _deliver_acs(
    to_address: str,
    subject: str,
    text_body: str,
    html_body: str | None,
    attachment: tuple[str, bytes] | None,
) -> str:
    """Send through Azure Communication Services Email using the ambient Entra identity."""
    import base64

    from azure.communication.email.aio import EmailClient

    from app.deps import get_azure_credential

    settings = get_settings()
    message: dict = {
        "senderAddress": settings.acs_sender_address,
        "recipients": {"to": [{"address": to_address}]},
        "content": {
            "subject": subject.replace("\r", " ").replace("\n", " "),
            "plainText": text_body,
        },
    }
    if html_body:
        message["content"]["html"] = html_body
    if attachment is not None:
        filename, content = attachment
        message["attachments"] = [
            {
                "name": filename,
                "contentType": "application/pdf",
                "contentInBase64": base64.b64encode(content).decode("ascii"),
            }
        ]

    client = EmailClient(settings.azure_communication_endpoint, get_azure_credential())
    try:
        async with client:
            result = await _send_with_retry(client, message)
    except Exception as exc:  # noqa: BLE001 - the SDK raises a wide range of transport errors
        raise UpstreamUnavailableError(
            f"Could not send the review email through Communication Services: {type(exc).__name__}"
        ) from exc

    status = (result or {}).get("status", "")
    if status and status.lower() not in {"succeeded", "running"}:
        raise UpstreamUnavailableError(f"Communication Services returned status {status!r}")
    return "sent"


async def _send_with_retry(client, message: dict):
    """One retry on auth failure, covering the poll as well as the initial request.

    `DefaultAzureCredential` shells out to `az` for local dev, which intermittently fails to
    launch on a loaded machine. The token is re-fetched while polling too, so retrying only
    `begin_send` would still leave a window open. The second attempt hits the warmed token cache.
    """
    from azure.core.exceptions import ClientAuthenticationError

    try:
        poller = await client.begin_send(message)
        return await poller.result()
    except ClientAuthenticationError:
        logger.warning("credential acquisition failed for the email send; retrying once")
        poller = await client.begin_send(message)
        return await poller.result()


async def send(
    to_address: str,
    subject: str,
    text_body: str,
    *,
    attachment: tuple[str, bytes] | None = None,
    html_body: str | None = None,
) -> str:
    """Send one message. Returns `"sent"` or `"preview"`; never raises for an unknown mailbox."""
    if not _ADDRESS_RE.match(to_address):
        raise UpstreamUnavailableError("Recipient address is not a valid email address")

    settings = get_settings()
    if settings.azure_communication_endpoint and settings.acs_sender_address:
        try:
            delivery = await _deliver_acs(to_address, subject, text_body, html_body, attachment)
        except UpstreamUnavailableError as exc:
            # A transport outage must not lose the message: keep the local copy so the link and
            # PIN can still be recovered, and so the demo keeps working offline.
            logger.warning("ACS send failed, falling back to local preview mail: %s", exc.detail)
            delivery = _write_preview(to_address, subject, text_body, html_body, attachment)
    else:
        delivery = _write_preview(to_address, subject, text_body, html_body, attachment)
    logger.info("review email %s (subject=%r)", delivery, subject)
    return delivery
