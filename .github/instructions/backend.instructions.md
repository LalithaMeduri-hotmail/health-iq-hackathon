---
applyTo: "backend/**/*.py"
description: "Backend engineering standards for the Health IQ FastAPI service: layered architecture, dependency rules, async I/O, validation, security, and testing."
---

# Backend Instructions (FastAPI, Python 3.11)

Apply these rules to all backend Python code. They enforce the layered architecture defined in the Health IQ implementation plan and low-level design.

## Layered Architecture (strict dependency direction)

Dependencies flow **downward only**. A layer may import from layers below it, never above or sideways across sibling feature modules.

```
api/          (routers, HTTP concerns)          -> depends on: services, agents, models, deps
agents/       (orchestration + agent tools)     -> depends on: services, rag, repositories, models
services/     (domain logic, external SDK calls)-> depends on: repositories, models, config
rag/          (indexes, ingest, retrieve)       -> depends on: services (clients), models, config
repositories/ (Cosmos, SQL data access)         -> depends on: models, config
models/       (pydantic schemas, domain types)  -> depends on: nothing (leaf)
config.py     (pydantic-settings, Key Vault)    -> depends on: nothing
deps.py       (DI: clients, current_user)       -> wires the above
```

- **Never** call Azure SDKs, Cosmos, or SQL directly from `api/`. Routers orchestrate; they do not implement domain logic or data access.
- **Never** put HTTP/FastAPI types (`Request`, `Response`, `HTTPException`, status codes) below `api/`. Lower layers raise domain exceptions; routers translate them to HTTP.
- `models/` is a pure leaf. Do not import services, repositories, or SDK clients into it.
- Cross-cutting clients (OpenAI, Search, Blob, Cosmos, SQL) are constructed once in `deps.py` and injected; do not instantiate clients inside request handlers.

## Routers (`api/`)

- One router module per resource (`prescriptions.py`, `reports.py`, `profile.py`, etc.). Prefix all routes with `/api/v1`.
- Keep handlers thin: validate input, call a service/agent, shape the response envelope. No business logic.
- Every success response uses the shared envelope: `{ requestId, generatedAt, apiVersion, disclaimer, safety, data }`. Never return a bare domain object.
- Use `Depends()` for `current_user`, settings, and clients. Get the caller's `userId` (Entra `oid`) from the auth dependency, never from the request body.
- Errors must be RFC 7807 problem details. Map domain exceptions in a centralized exception handler; do not scatter `raise HTTPException` with ad hoc bodies.

Canonical response envelope (every success returns exactly this shape):

```python
return ApiResponse(
    request_id=ctx.request_id,
    generated_at=datetime.now(UTC),
    api_version="v1",
    disclaimer=DISCLAIMER_TEXT,
    safety=safety_result,   # from the mandatory SafetyReviewerAgent stage
    data=payload,           # the feature-specific pydantic model
)
```

Canonical error mapping (domain exception -> RFC 7807, wired once in a handler):

```python
@app.exception_handler(LowConfidenceError)
async def low_confidence_handler(request: Request, exc: LowConfidenceError):
    return JSONResponse(
        status_code=422,
        content=ProblemDetails(
            type="https://healthiq/errors/low-confidence-ocr",
            title="OCR confidence too low",
            status=422,
            detail=str(exc),
            instance=request.state.request_id,
        ).model_dump(),
        media_type="application/problem+json",
    )
```

## Services (`services/`)

- Services own domain logic and wrap external SDKs (`ocr.py`, `normalize_*.py`, `comparison.py`, `pdf_builder.py`, `blob.py`, `share_links.py`, `deidentify.py`).
- All numeric/business decisions (savings %, change classification, health score, allergen filtering, safety rule checks) are **deterministic Python** and must be unit-testable without network calls. The LLM never computes these.
- Raise typed domain exceptions (e.g., `LowConfidenceError`, `NoSafeAlternativeError`), not `HTTPException`.
- Guard boundaries: validate external SDK responses before trusting them. Treat OCR/user text as untrusted data.

## Repositories (`repositories/`)

- All persistence goes through `cosmos_repo.py` / `sql_repo.py`. No SQL strings or Cosmos queries anywhere else.
- Every query is scoped by `userId`. Owner-mismatch reads must be impossible by construction (filter in the query, then assert ownership).
- Use parameterized queries only. Never build SQL via string concatenation/f-strings with user input.
- Repositories return `models/` domain objects, not raw driver rows/dicts.

Canonical `userId`-scoped read (filter in the query, then assert ownership):

```python
async def get_report(self, user_id: str, report_id: str) -> Report:
    query = "SELECT * FROM c WHERE c.userId = @userId AND c.id = @id"
    params = [{"name": "@userId", "value": user_id}, {"name": "@id", "value": report_id}]
    items = [item async for item in self._container.query_items(query, parameters=params)]
    if not items:
        raise NotFoundError(report_id)
    report = Report.model_validate(items[0])
    assert report.user_id == user_id  # defense in depth; never trust a single filter
    return report
```

## Async, resilience, and performance

- Use `async def` for all I/O-bound handlers and SDK calls; use async Azure SDK clients. Do not block the event loop (no sync `requests`, no blocking `time.sleep`).
- Wrap upstream calls (Document Intelligence, OpenAI, Search) with timeouts and exponential-backoff retries (OCR: poll to 60 s; LLM: ~30 s budget). Retry only idempotent/5xx cases.
- Respect the p95 budgets from the LLD (prescription < 12 s, report analysis < 15 s). Parallelize independent I/O with `asyncio.gather` (bounded concurrency).

## Validation & typing

- Define request/response schemas as pydantic models in `models/`; validate at the boundary. Enable strict types; no `dict[str, Any]` leaking across layers.
- Use `pydantic-settings` in `config.py` bound to Key Vault. No literals for endpoints, model names, thresholds — read them from settings.
- Full type hints on every public function. Run `ruff` clean; no unused imports or `# type: ignore` without a reason.

## Security (non-negotiable)

- Authenticate to Azure with `DefaultAzureCredential` + managed identity. **No** account keys, connection strings, or secrets in code or committed config. `.env` is dev-only and gitignored.
- Enforce upload safety in `blob.py`: extension + MIME + magic-byte checks, 10 MB cap, allowlist `.jpg/.jpeg/.png/.pdf/.heic`, reject archives/SVG.
- Run `deidentify.py` before any content reaches the LLM; keep the reversible map in memory only, never persisted.
- Every user-facing payload passes through the mandatory `SafetyReviewerAgent` stage before it leaves the router.
- Write audit records to Cosmos `runs` (input hash, tool calls, agent versions, safety verdict). Never log PHI content.

## Testing

- Unit tests for all deterministic logic (strength parsing, synonym mapping, unit conversion, change classification thresholds, savings math, all six safety rules).
- Contract tests per endpoint: happy path, missing consent, oversized file, wrong MIME, low-confidence path.
- Use recorded fixtures for OCR/LLM/Search; do not hit live Azure in unit/contract tests. Honor `DEMO_MODE` for replayable flows.

## Dependency management

- Use `uv` for dependency management (`uv add`, `uv sync`). Pin Python 3.11. Do not hand-edit lockfiles.
