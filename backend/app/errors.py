"""Domain exceptions shared across features, mapped to RFC 7807 problem details in `main.py`.

Services/repositories/agents raise these instead of `HTTPException` (backend.instructions.md).
Each exception's `type_slug`/`title`/`status` mirror the global error table
(docs/lld/1-low-level-design-overview.md Section 0.4).
"""


class DomainError(Exception):
    """Base class for all typed domain exceptions."""

    type_slug: str = "internal-error"
    title: str = "Internal server error"
    status: int = 500

    def __init__(self, detail: str, *, errors: list[dict] | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.errors = errors or []


class ValidationError(DomainError):
    type_slug = "validation-error"
    title = "Validation error"
    status = 400


class UnauthenticatedError(DomainError):
    type_slug = "unauthenticated"
    title = "Unauthenticated"
    status = 401


class ForbiddenError(DomainError):
    type_slug = "forbidden"
    title = "Forbidden"
    status = 403


class NotFoundError(DomainError):
    type_slug = "resource-not-found"
    title = "Resource not found"
    status = 404


class UnsupportedMediaTypeError(DomainError):
    type_slug = "unsupported-media-type"
    title = "Unsupported media type"
    status = 415


class PayloadTooLargeError(DomainError):
    type_slug = "payload-too-large"
    title = "Payload too large"
    status = 413


class LowConfidenceOcrError(DomainError):
    type_slug = "low-confidence-ocr"
    title = "OCR confidence below threshold"
    status = 422


class NoSafeAlternativeError(DomainError):
    type_slug = "no-safe-alternative"
    title = "No safe alternative found"
    status = 422


class SafetyViolationError(DomainError):
    type_slug = "safety-violation"
    title = "Safety review blocked this response"
    status = 422


class RateLimitedError(DomainError):
    type_slug = "rate-limited"
    title = "Rate limited"
    status = 429


class UpstreamUnavailableError(DomainError):
    type_slug = "upstream-unavailable"
    title = "Upstream service unavailable"
    status = 502


class UpstreamTimeoutError(DomainError):
    type_slug = "upstream-timeout"
    title = "Upstream service timed out"
    status = 504
