<!-- Health IQ pull request. Keep the disclaimer, safety, and layering invariants intact. -->

## Summary

<!-- What does this PR change and why? Link the work item / issue. -->

## Changes

<!-- Bullet the notable changes. -->

-

## Review checklist

Check every item that applies to the changed code. Anything unchecked must be explained below.

### Architecture & layering

- [ ] Dependencies flow downward only; no `api/` code calls Azure SDKs, Cosmos, or SQL directly.
- [ ] No FastAPI/HTTP types (`Request`, `Response`, `HTTPException`) below `api/`; lower layers raise typed domain exceptions.
- [ ] Business/numeric logic (savings, classification, health score, allergen filtering, safety rules) is deterministic Python — not computed by the LLM.

### API contracts

- [ ] Every success response uses the shared envelope (`requestId`, `generatedAt`, `apiVersion`, `disclaimer`, `safety`, `data`).
- [ ] Errors are RFC 7807 problem details via the centralized handler (no ad hoc `HTTPException` bodies).
- [ ] `422 low-confidence-ocr` and other domain errors map to the agreed types the frontend consumes.

### Data access & security

- [ ] Every repository query is `userId`-scoped and parameterized (no string-built SQL/Cosmos queries).
- [ ] `DefaultAzureCredential` + managed identity only — no keys, connection strings, or secrets in code or config.
- [ ] Upload safety enforced (extension + MIME + magic-byte, size cap, allowlist) for any new upload path.
- [ ] De-identification runs before any content reaches the LLM; no PHI in logs, URLs, or telemetry.

### Safety UX (AI/agents & frontend)

- [ ] Every user-facing payload passes through the mandatory `SafetyReviewerAgent` stage before leaving the router.
- [ ] RAG-grounded claims carry provenance (source + date); alternatives labeled "doctor approval required" / savings "estimated".
- [ ] Frontend: consent gate blocks upload, disclaimer renders on every view, and `safety.pass === false` suppresses content.

### Quality

- [ ] Deterministic logic has unit tests; endpoints have contract tests (happy path + missing consent, oversized/wrong-MIME file, low-confidence).
- [ ] Lint/typecheck clean (`ruff` for Python; ESLint + `tsc` for the React app).

## Notes

<!-- Anything reviewers should know: tradeoffs, follow-ups, unchecked items above. -->
