"""Outbound mail for doctor-review requests.

Transport-agnostic by design: with `smtp_host` set the message goes out over SMTP+STARTTLS;
without it the mailer stays in preview mode and writes the full RFC-822 message to
`<repo>/.local-mail/*.eml` so the flow stays exercisable with no credentials. Credentials are
read from settings only - never logged, never returned to a caller.
"""

import asyncio
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
    """True when no SMTP host is configured, so nothing is actually delivered."""
    return not get_settings().smtp_host


def _build(to_address: str, subject: str, text_body: str, attachment: tuple[str, bytes] | None) -> EmailMessage:
    if not _ADDRESS_RE.match(to_address):
        raise UpstreamUnavailableError("Recipient address is not a valid email address")

    settings = get_settings()
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to_address
    # Header injection defence: strip anything that could start a new header line.
    message["Subject"] = subject.replace("\r", " ").replace("\n", " ")
    message["Date"] = datetime.now(UTC).strftime("%a, %d %b %Y %H:%M:%S +0000")
    message.set_content(text_body)

    if attachment is not None:
        filename, content = attachment
        message.add_attachment(content, maintype="application", subtype="pdf", filename=filename)
    return message


def _deliver(message: EmailMessage) -> str:
    settings = get_settings()

    if not settings.smtp_host:
        _LOCAL_MAIL_ROOT.mkdir(parents=True, exist_ok=True)
        target = _LOCAL_MAIL_ROOT / f"{datetime.now(UTC):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}.eml"
        target.write_bytes(bytes(message))
        return "preview"

    import smtplib

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
    except smtplib.SMTPException as exc:
        # `exc` can echo the envelope; keep the recipient out of the surfaced detail.
        raise UpstreamUnavailableError(f"Could not send the review email: {type(exc).__name__}") from exc
    return "sent"


async def send(
    to_address: str,
    subject: str,
    text_body: str,
    *,
    attachment: tuple[str, bytes] | None = None,
) -> str:
    """Send one message. Returns `"sent"` or `"preview"`; never raises for an unknown mailbox."""
    message = _build(to_address, subject, text_body, attachment)
    delivery = await asyncio.to_thread(_deliver, message)
    logger.info("review email %s (subject=%r)", delivery, subject)
    return delivery
