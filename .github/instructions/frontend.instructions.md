---
applyTo: "frontend/**/*.{ts,tsx,js,jsx}"
description: "Frontend engineering standards for the Health IQ React app: structure, TypeScript, data fetching, state, safety UX, charts, accessibility, security, and testing."
---

# Frontend Instructions (React + TypeScript)

Apply these rules to all frontend code. The frontend is a thin presentation layer over the backend API. It contains **no** business logic, no direct Azure SDK calls, and no data-access code. All medical logic, grounding, and safety decisions come from the backend.

## Stack & tooling

- **React 18+ with TypeScript** (strict mode). Prefer Next.js (App Router) or Vite + React Router; keep the choice consistent across the app.
- Use functional components and hooks only. No class components.
- Package manager and lint/format: `npm`/`pnpm`, ESLint + Prettier, `typescript-eslint`. CI must pass lint + typecheck.
- No `any`. Model API payloads as explicit `interface`/`type`; derive shared types from the backend OpenAPI schema where possible.

## Structure (feature-first)

```
src/
  app/ or routes/        # pages/routes: prescription, profile, comparison, meal-planner
  features/              # one folder per feature (components + hooks + types colocated)
    prescription/
    health-profile/
    report-comparison/
    meal-planner/
  components/            # shared, presentational, reusable UI (Button, Card, Disclaimer, ConsentModal)
  lib/
    apiClient.ts         # single typed HTTP client (the ONLY place fetch/axios lives)
    auth.ts              # MSAL config + token acquisition
    types.ts             # shared API/domain types
  hooks/                 # shared cross-feature hooks
```

- Colocate a feature's components, hooks, and types under `features/<feature>/`. Do not scatter one feature across the tree.
- Shared presentational components live in `components/` and must be stateless where possible (props in, UI out).
- Keep components small and single-purpose. Extract logic into hooks rather than growing a component.

## Backend interaction & data fetching

- All network calls go through the single typed client in `lib/apiClient.ts`. Components and hooks never call `fetch`/`axios` directly.
- Use **TanStack Query (React Query)** for server state (fetching, caching, retries, loading/error). Do not hand-roll `useEffect` + `useState` fetch loops.
- Attach the Entra access token as `Authorization: Bearer <jwt>` in the client; acquire it via MSAL (`lib/auth.ts`). Locally, use the stub-user path.
- **No secrets in the frontend.** No API keys, connection strings, or Azure credentials. Only public config via `NEXT_PUBLIC_`/`VITE_` env vars.
- Treat the backend response envelope as the contract: read `data`, and always surface `disclaimer` and `safety`. If `safety.pass === false`, render the suppression notice and never present redacted content as valid.
- Handle RFC 7807 problem details centrally in the client: map `type`/`title`/`detail` to user-friendly messages. Map `422 low-confidence-ocr` to opening the confirmation grid, not a generic error toast.

## State management

- **Server state** → React Query. **URL state** (selected report, tab) → the router. **Local UI state** → `useState`/`useReducer`.
- Introduce a global store (Zustand or Context) only for genuinely cross-cutting client state (auth/session, consent status, theme). Do not put server data in a global store.
- Never persist secrets or full PHI blobs in `localStorage`/`sessionStorage`. Keep only IDs (`runId`, `reportId`) and display-ready results in memory.

## Safety & consent UX (mandatory)

- A blocking consent modal (`components/ConsentModal`) must be accepted before any upload. No file leaves the browser before consent.
- Every feature view renders the shared `Disclaimer` component. Never hide or omit it.
- Show OCR confidence visibly; force user confirmation for low-confidence tokens before requesting alternatives.
- Label alternatives as "doctor approval required" and savings as "estimated" with source date. Never present them as a recommendation to change medication.
- Use safe language in all copy ("possible concern", "discuss with your doctor"); never diagnostic wording. Show provenance (source + date) next to any medical/nutritional claim.

## Forms & validation

- Use **React Hook Form** (+ Zod resolver) for multi-field forms (preferences, OCR corrections). Validate with Zod schemas.
- Client validation (file type/size hints, required fields) improves UX only; never rely on it for security or correctness — the backend is the source of truth.

## Charts & visualization

- Use one charting library consistently (Recharts or Plotly-react) for line charts (repeated parameters), radar chart by system, health-score gauge, and color-coded before/after tables.
- Keep chart components presentational: pass data in, render a figure. Use colorblind-safe palettes and always label units.

## Accessibility & UX

- Semantic HTML and ARIA where needed; all interactive elements keyboard-navigable; visible focus states.
- Associate labels with inputs; provide `alt` text; meet WCAG AA color contrast.
- Show clear loading (skeletons/spinners) and error states around every async action; disable submit buttons while requests are in flight.

## Performance

- Code-split by route; lazy-load heavy feature bundles and chart libraries (`React.lazy`/dynamic import).
- Memoize expensive renders (`useMemo`/`React.memo`) and stable callbacks (`useCallback`) only where profiling shows benefit — do not over-memoize.
- Let React Query handle caching/dedup; set sensible `staleTime` for reference/profile reads. Gate network calls behind explicit user actions.

## Security

- Never render untrusted HTML; avoid `dangerouslySetInnerHTML`. Let React escape by default (XSS defense).
- Do not put PHI or tokens in URLs, logs, or analytics. Share links use the opaque backend `shareId` only.
- Keep dependencies patched; run dependency scanning in CI.

## Testing

- Unit/component tests with **Vitest/Jest + React Testing Library**; test behavior and accessibility, not implementation details.
- Mock the API client (or use MSW) — never hit live backend/Azure in unit tests.
- Add an E2E happy-path test (Playwright) for the primary flow: upload → confirm → alternatives → PDF/share.
- Explicitly test safety UX: consent gate blocks upload, disclaimer always present, low-confidence path forces confirmation, `safety.pass === false` suppresses content.
