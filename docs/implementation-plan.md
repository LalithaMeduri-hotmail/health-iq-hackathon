---
title: Health IQ - Hackathon 2026 MVP Implementation Plan
description: Detailed engineering implementation plan for the Health IQ MVP covering repository layout, Azure provisioning, data models, API contracts, agent design, milestones, and demo readiness.
author: Health IQ Hackathon Team
ms.date: 2026-08-27
ms.topic: how-to
keywords:
  - health iq
  - hackathon
  - azure ai
  - microsoft agent framework
  - rag
estimated_reading_time: 25
---

## 1. Plan Overview

This plan converts the `DesignDoc-V1` design into an executable build. It is organized as seven milestones (M0-M6) with concrete deliverables, file paths, contracts, and acceptance criteria.

| Item | Decision |
|------|----------|
| Backend | Python 3.11, FastAPI, `uv` for dependency management |
| Frontend | React + TypeScript SPA (4 routes) for the MVP; Vite or Next.js (App Router) |
| Agents | Microsoft Agent Framework (`agent-framework` Python package) |
| LLM | Azure OpenAI `gpt-4o` (reasoning) + `text-embedding-3-large` (vectors) |
| OCR | Azure AI Document Intelligence `prebuilt-read` + `prebuilt-layout` |
| Retrieval | Azure AI Search, hybrid (BM25 + vector) with semantic ranker |
| Storage | Azure Blob Storage (raw + generated containers) |
| Data | Azure Cosmos DB (profile/history), Azure SQL (medicine catalog, metrics) |
| Auth | Microsoft Entra ID; local dev uses a stub user |
| Secrets | Azure Key Vault + `DefaultAzureCredential`, no keys in code |
| Observability | Application Insights + OpenTelemetry agent traces |

### 1.1 Scope guardrails

Every feature must satisfy the design's safety principle: **patient decision support only**. No output ships without a doctor-review disclaimer, provenance labels, and a confidence value.

---

## 2. Repository Structure

```text
Hackathon-HealthIQ/
├─ docs/
│  ├─ implementation-plan.md
│  ├─ demo-script.md
│  └─ adr/
├─ infra/                            # Bicep IaC
│  ├─ main.bicep
│  ├─ main.parameters.json
│  └─ modules/
│     ├─ storage.bicep
│     ├─ cosmos.bicep
│     ├─ sql.bicep
│     ├─ search.bicep
│     ├─ docintel.bicep
│     ├─ openai.bicep
│     ├─ keyvault.bicep
│     └─ monitoring.bicep
├─ backend/
│  ├─ pyproject.toml
│  ├─ app/
│  │  ├─ main.py                     # FastAPI app factory + routers
│  │  ├─ config.py                   # pydantic-settings, Key Vault binding
│  │  ├─ deps.py                     # DI: clients, current_user
│  │  ├─ api/
│  │  │  ├─ prescriptions.py
│  │  │  ├─ medicines.py
│  │  │  ├─ reports.py
│  │  │  ├─ mealplan.py
│  │  │  ├─ pdf.py
│  │  │  ├─ share.py
│  │  │  └─ profile.py
│  │  ├─ models/                     # pydantic schemas (request/response/domain)
│  │  │  ├─ medicine.py
│  │  │  ├─ report.py
│  │  │  ├─ profile.py
│  │  │  └─ common.py
│  │  ├─ services/
│  │  │  ├─ ocr.py                   # Document Intelligence wrapper
│  │  │  ├─ normalize_medicine.py
│  │  │  ├─ normalize_lab.py
│  │  │  ├─ reference_ranges.py
│  │  │  ├─ comparison.py
│  │  │  ├─ pdf_builder.py
│  │  │  ├─ blob.py
│  │  │  ├─ share_links.py
│  │  │  └─ deidentify.py
│  │  ├─ agents/
│  │  │  ├─ orchestrator.py
│  │  │  ├─ prescription_agent.py
│  │  │  ├─ report_agent.py
│  │  │  ├─ comparison_agent.py
│  │  │  ├─ specialist_agent.py
│  │  │  ├─ mealplan_agent.py
│  │  │  ├─ safety_agent.py
│  │  │  ├─ tools.py                 # @ai_function tool definitions
│  │  │  └─ prompts/*.md
│  │  ├─ rag/
│  │  │  ├─ indexes.py               # index definitions + create/update
│  │  │  ├─ ingest.py                # chunk, embed, upload
│  │  │  └─ retrieve.py              # hybrid + semantic query helpers
│  │  └─ repositories/
│  │     ├─ cosmos_repo.py
│  │     └─ sql_repo.py
│  └─ tests/
│     ├─ unit/
│     ├─ integration/
│     └─ fixtures/
├─ frontend/
│  ├─ src/
│  │  ├─ main.tsx                    # React entry / router bootstrap
│  │  ├─ routes/
│  │  │  ├─ PrescriptionAnalyzer.tsx
│  │  │  ├─ HealthProfile.tsx
│  │  │  ├─ ReportComparison.tsx
│  │  │  └─ MealPlanner.tsx
│  │  ├─ lib/
│  │  │  ├─ apiClient.ts             # single typed HTTP client
│  │  │  ├─ auth.ts                  # MSAL config + token acquisition
│  │  │  └─ types.ts                 # shared API/domain types
│  │  └─ components/
│  │     ├─ Charts.tsx
│  │     ├─ ConsentModal.tsx
│  │     └─ Disclaimer.tsx
│  ├─ index.html
│  ├─ package.json
│  ├─ tsconfig.json
│  └─ vite.config.ts
├─ data/
│  ├─ medicines/medicine_catalog.csv
│  ├─ reference_ranges/lab_reference_ranges.csv
│  ├─ specialists/specialist_mapping.csv
│  ├─ nutrition/nutrition_rules.md
│  ├─ synonyms/lab_synonyms.json
│  └─ samples/                       # 5 prescriptions, 6 reports (3 pairs)
├─ scripts/
│  ├─ seed_sql.py
│  ├─ build_search_indexes.py
│  └─ run_local.ps1
├─ .env.example
├─ azure.yaml
└─ README.md
```

---

## 3. Milestones

### M0 - Foundation (Day 1, first half)

| # | Task | Deliverable | Owner role |
|---|------|-------------|------------|
| 0.1 | Init repo, `uv init`, pin Python 3.11, add ruff + pytest | `pyproject.toml`, CI-ready lint | Backend |
| 0.2 | Create `.env.example` and `app/config.py` with pydantic-settings | Typed settings object | Backend |
| 0.3 | FastAPI skeleton with `/health`, CORS, exception handlers, request-id middleware | `GET /health` returns 200 | Backend |
| 0.4 | React + TypeScript shell with 4 routes, consent modal, global disclaimer footer | Clickable UI shell | Frontend |
| 0.5 | Bicep `main.bicep` provisioning all Azure resources with managed identity + RBAC | `az deployment group create` succeeds | Infra |
| 0.6 | Wire Key Vault + `DefaultAzureCredential`; no secrets in code | Local + cloud auth working | Infra |

**Exit criteria:** UI shell loads, backend `/health` green, all Azure resources provisioned, App Insights receiving telemetry.

#### Azure resources to provision

| Resource | SKU (MVP) | Notes |
|----------|-----------|-------|
| Storage Account | Standard_LRS | Containers: `raw-uploads`, `generated-pdfs`, `thumbnails`; blob versioning on; public access off |
| Cosmos DB (NoSQL) | Serverless | DB `healthiq`; containers `profiles` (pk `/userId`), `reports` (pk `/userId`), `runs` (pk `/userId`) |
| Azure SQL | Basic/S0 | Tables: `Medicine`, `MedicinePrice`, `LabMetric`, `ShareLink` |
| Azure AI Search | Basic | 4 indexes (see 6.1); semantic ranker enabled |
| Document Intelligence | S0 | `prebuilt-read`, `prebuilt-layout` |
| Azure OpenAI | S0 | Deployments: `gpt-4o`, `text-embedding-3-large` |
| Key Vault | Standard | RBAC auth mode |
| App Insights + LA workspace | Pay-as-you-go | OTEL exporter from FastAPI + agents |
| Container Apps (optional) | Consumption | Hosting for backend + React SPA at demo time |

---

### M1 - Ingestion and OCR (Day 1, second half)

| # | Task | Detail |
|---|------|--------|
| 1.1 | `services/blob.py` | Upload with `userId/{yyyy-mm}/{uuid}{ext}`, content-type sniffing, 10 MB cap, allowlist `.jpg/.jpeg/.png/.pdf/.heic`, magic-byte validation |
| 1.2 | Consent capture | Persist `consentVersion`, `consentAt`, `purpose` in blob metadata and Cosmos `profiles` doc |
| 1.3 | `services/ocr.py` | `prebuilt-read` for prescriptions/tablet strips; `prebuilt-layout` for lab reports (tables). Async polling, retry with exponential backoff, 60s timeout |
| 1.4 | OCR result envelope | Return `{ pages, lines[{text, confidence, bbox}], tables[], handwrittenRatio }` |
| 1.5 | `services/deidentify.py` | Regex + Presidio-style redaction of name, phone, email, MRN, address before any content reaches the LLM; keep a reversible map in memory only |
| 1.6 | Low-confidence gate | Any token with confidence `< 0.75` is flagged; UI must force user confirmation before alternatives are generated |

**Exit criteria:** Upload a sample prescription and a sample lab PDF and receive structured OCR JSON with confidence values.

---

### M2 - Domain Data and Normalization (Day 2, first half)

#### 2.1 Medicine catalog seed (`data/medicines/medicine_catalog.csv`)

| Column | Example |
|--------|---------|
| `brandName` | Brand A |
| `activeIngredient` | Active ingredient X |
| `strengthValue` / `strengthUnit` | 500 / mg |
| `dosageForm` | tablet |
| `genericName` | Generic X |
| `manufacturer` | Manufacturer B |
| `mrpInr` | 42.00 |
| `sourceName` / `sourceUrl` / `sourceDate` | NPPA / ... / 2026-06-01 |
| `isDemoData` | true |

Seed 60-80 rows covering the demo prescriptions plus common Indian generics.

#### 2.2 Medicine normalization (`normalize_medicine.py`)

1. Clean OCR text: strip dosage instructions (`1-0-1`, `BD`, `OD`, `HS`, `SOS`), units, and noise.
2. Fuzzy match brand name against catalog using RapidFuzz `token_set_ratio`; accept `>= 88`, review band `75-87`, reject below.
3. Parse strength with regex `(\d+(?:\.\d+)?)\s*(mg|mcg|g|ml|iu|%)`.
4. Emit `MedicineEntity{ rawText, brandName, activeIngredient, strength, dosageForm, frequency, duration, matchScore, needsUserConfirmation }`.

#### 2.3 Alternative matching rules (hard constraints)

An alternative is returned **only if** all are true:

* Identical normalized `activeIngredient` set.
* Identical `strengthValue` and `strengthUnit`.
* Identical `dosageForm`.
* Source record has `sourceDate` within 24 months.

Output ranks by price ascending; `savingsPct = round((orig - alt) / orig * 100)`. Savings always labeled "estimated" with source date. Combination drugs (multi-ingredient) require exact multiset match or are excluded.

#### 2.4 Lab normalization (`normalize_lab.py`, `data/synonyms/lab_synonyms.json`)

Canonical parameters for MVP: `glucose_fasting`, `glucose_pp`, `hba1c`, `hemoglobin`, `ldl`, `hdl`, `triglycerides`, `total_cholesterol`, `creatinine`, `urea`, `tsh`, `sgpt_alt`, `sgot_ast`, `vitamin_d`, `vitamin_b12`, `wbc`, `platelets`.

* Synonym map: `HbA1c | Glycated Haemoglobin | A1C -> hba1c`.
* Unit conversion table: `mg/dL <-> mmol/L` for glucose and cholesterol; `ng/mL <-> nmol/L` for vitamin D.
* Report date extraction from layout key-value pairs with fallback to filename and upload date.
* Emit `LabParameter{ canonicalKey, displayName, value, unit, refLow, refHigh, status, reportDate, sourceConfidence }` where `status` is one of `low | normal | high | critical_flag`.

#### 2.5 Reference ranges (`data/reference_ranges/lab_reference_ranges.csv`)

Columns: `canonicalKey`, `sex`, `ageMin`, `ageMax`, `refLow`, `refHigh`, `unit`, `plainLanguage`, `sourceName`, `sourceUrl`. Ranges are labeled educational, never diagnostic.

**Exit criteria:** Given OCR JSON, `normalize_*` produce clean entities for all 5 sample prescriptions and 6 sample reports.

---

### M3 - RAG Layer (Day 2, second half)

#### 3.1 Azure AI Search indexes

| Index | Key fields | Vector field | Purpose |
|-------|-----------|--------------|---------|
| `idx-medicines` | `brandName`, `activeIngredient`, `strength`, `dosageForm`, `genericName`, `mrpInr`, `sourceUrl`, `sourceDate` | `compositionVector` | Composition + alternative lookup |
| `idx-reference-ranges` | `canonicalKey`, `displayName`, `rangeText`, `plainLanguage`, `sourceUrl` | `explanationVector` | Patient-friendly parameter meaning |
| `idx-specialists` | `parameterGroup`, `specialtyCategory`, `whenToConsult`, `disclaimer` | `mappingVector` | Abnormality -> specialist category |
| `idx-nutrition` | `condition`, `cuisine`, `mealType`, `guidance`, `avoidList`, `sourceUrl` | `guidanceVector` | Meal planning grounding |

Common config: `text-embedding-3-large` (3072 dims), HNSW profile, semantic configuration with title/content fields, hybrid query (`search` + `vectorQueries`) with `queryType=semantic`, `top=5`.

#### 3.2 Ingestion (`rag/ingest.py`)

Read CSV/MD sources -> chunk (500 tokens, 60 overlap for prose; one row per doc for tabular) -> embed -> upload in batches of 100 -> verify document counts. Idempotent via deterministic doc IDs (`sha1(source + row_key)`).

#### 3.3 Retrieval contract (`rag/retrieve.py`)

Every retrieval returns `RetrievedChunk{ content, score, sourceName, sourceUrl, sourceDate }`. Agents are prompt-bound: **no claim may appear in output without at least one attached `RetrievedChunk`.**

**Exit criteria:** `python scripts/build_search_indexes.py` creates and populates all 4 indexes; smoke queries return grounded chunks with sources.

---

### M4 - Agents (Day 3)

#### 4.1 Orchestrator

`agents/orchestrator.py` builds one `ChatAgent` per role over `AzureOpenAIChatClient` with `DefaultAzureCredential`, registers function tools, and routes by intent. Sequential workflow per feature; `SafetyReviewerAgent` runs as a mandatory final stage on every user-facing payload.

```text
request -> feature agent -> (tools: OCR/normalize/RAG/SQL/PDF) -> draft -> SafetyReviewerAgent -> response
```

#### 4.2 Agent specifications

| Agent | Tools | Output contract | Guardrails |
|-------|-------|-----------------|------------|
| `PrescriptionAnalyzerAgent` | `ocr_extract`, `normalize_medicine`, `search_medicines`, `find_alternatives`, `generate_pdf` | `MedicineAnalysis{ items[], disclaimers[], confidence }` | Never suggests stopping/starting a drug; alternatives always `doctorApprovalRequired=true` |
| `ReportAnalysisAgent` | `ocr_layout`, `normalize_lab`, `lookup_reference_range`, `search_reference_explanations` | `ReportSummary{ parameters[], abnormal[], systemCards[], healthScore, narrative }` | Uses "possible concern"; no disease naming |
| `ComparisonAgent` | `load_report`, `align_parameters`, `classify_change` | `ComparisonResult{ improved[], worsened[], unchanged[], newlyAbnormal[], missing[], trendSeries[] }` | Deterministic classification in Python; LLM only writes the narrative |
| `SpecialistAdvisorAgent` | `search_specialist_mapping`, `get_doctor_links` | `SpecialistGuidance{ categories[], rationale, doctorLinks[], disclaimer }` | Category only; no named-doctor endorsement; links flagged as public/demo data |
| `MealPlannerAgent` | `search_nutrition_rules`, `get_profile_preferences` | `MealPlan{ days[], rationale[], avoidList[], disclaimer }` | Hard-blocks allergens; no supplement dosing; no calorie prescriptions for minors |
| `SafetyReviewerAgent` | `check_citations`, `check_disclaimers`, `check_prohibited_claims` | `SafetyVerdict{ pass, violations[], redactedPayload }` | Blocks response on diagnosis language, missing citation, or missing disclaimer |

#### 4.3 Safety reviewer rules

| Rule | Check |
|------|-------|
| R1 | Payload contains the standard disclaimer string |
| R2 | Every medical/nutritional claim carries `sourceUrl` + `sourceDate` |
| R3 | No banned phrases: "you have", "diagnosed with", "stop taking", "replace your", "cure", "guaranteed" |
| R4 | Alternatives carry `doctorApprovalRequired=true` and `savingsEstimated=true` |
| R5 | Confidence below threshold forces `needsUserConfirmation=true` |
| R6 | No PHI leaked back into shareable artifacts beyond what consent permits |

Violations of R3-R6 cause hard failure; the API returns the redacted payload plus a `safety` block explaining suppression.

#### 4.4 Classification logic (deterministic, `services/comparison.py`)

```text
delta      = current - old
pctChange  = delta / old * 100  (guard old == 0)
inRange(v) = refLow <= v <= refHigh

improved       : was out of range and now in range, OR moved >=10% toward range
worsened       : was in range and now out, OR moved >=10% away from range
unchanged      : |pctChange| < 5
newlyAbnormal  : absent in old, out of range in current
missing        : present in old, absent in current
```

**Exit criteria:** Each agent callable via a pytest integration test with recorded fixtures; safety agent blocks a deliberately unsafe draft.

---

### M5 - APIs, PDF, and UI (Day 4)

#### 5.1 API contracts

| Method | Route | Request | Response |
|--------|-------|---------|----------|
| POST | `/api/v1/prescriptions/analyze` | multipart `file`, `consent=true` | `{ runId, items[], ocrConfidence, needsConfirmation[], disclaimers[] }` |
| POST | `/api/v1/prescriptions/confirm` | `{ runId, corrections[] }` | Updated `items[]` |
| POST | `/api/v1/medicines/alternatives` | `{ items[] }` | `{ alternatives[{ original, generic, cheaper, savingsPct, source, doctorApprovalRequired }] }` |
| POST | `/api/v1/reports/analyze` | multipart `file` | `{ reportId, parameters[], abnormal[], healthScore, systemCards[], narrative }` |
| POST | `/api/v1/reports/compare` | `{ oldReportId, currentReportId }` | `ComparisonResult` + `trendSeries[]` |
| GET | `/api/v1/profile` | - | `{ profile, reports[], latestSummary }` |
| PUT | `/api/v1/profile/preferences` | `{ allergies[], cuisine, goals[], location }` | Updated profile |
| POST | `/api/v1/specialists/suggest` | `{ reportId }` | `SpecialistGuidance` |
| POST | `/api/v1/meal-plan/generate` | `{ reportId, preferences }` | `MealPlan` |
| POST | `/api/v1/pdf/generate` | `{ runId }` | `{ pdfBlobUrl, shareId, expiresAt }` |
| GET | `/api/v1/share/{shareId}` | - | HTML page or 302 to SAS URL |

Cross-cutting: all responses include `{ requestId, generatedAt, disclaimer, safety: { pass, notes[] } }`. Errors use RFC 7807 problem details.

#### 5.2 Share link security

* `shareId` = 128-bit URL-safe random token, stored hashed (SHA-256) in SQL `ShareLink`.
* Backend issues a **user-delegation SAS** valid 24 hours, read-only, single blob.
* Rate limit `GET /share/{id}` to 20 req/min/IP; log every access with timestamp and IP hash.
* No PHI in the URL; the token is opaque and revocable.

#### 5.3 Doctor-review PDF (`services/pdf_builder.py`, ReportLab)

Sections in order:

1. Header: "Doctor Review Request - Not a Prescription", generated timestamp, Health IQ branding.
2. Patient block: only fields the user consented to share.
3. Prescribed medicines table (as extracted, with OCR confidence per row).
4. Suggested equivalents table: original, composition, generic, cheaper alternative, estimated savings, source + source date.
5. Doctor approval section: per-row Approve / Modify / Reject checkboxes, notes field, signature and date lines.
6. Footer disclaimer + provenance list + "Data is demo/curated" notice.

#### 5.4 React UI

| Route | Contents |
|-------|----------|
| Prescription Analyzer | Upload -> OCR preview with confidence highlighting -> editable confirmation grid -> alternatives table with savings -> "Generate doctor PDF" -> share link |
| Health Profile | Demographics + preferences form, consent status, report history timeline, health score gauge, organ/system cards with risk chips, specialist suggestion panel with links |
| Report Comparison | Two-report picker (upload or history) -> color-coded before/after table -> line chart per repeated parameter -> radar chart by system -> progression narrative |
| Meal Planner | Condition chips from latest report, allergy/cuisine/budget inputs -> 3-day plan cards -> avoid list -> rationale with sources |

Charts via Recharts or Plotly-react. Every route renders the disclaimer component; consent modal blocks upload until accepted.

**Exit criteria:** All 4 routes work end to end against the live backend with sample data.

---

### M6 - Hardening, Observability, and Demo (Day 5)

| # | Task |
|---|------|
| 6.1 | OpenTelemetry: trace spans for OCR, retrieval, each agent turn, PDF; export to App Insights |
| 6.2 | Custom metrics: `ocr_confidence`, `agent_latency_ms`, `safety_block_count`, `alternative_match_rate`, `pdf_success_rate` |
| 6.3 | Availability test on `/health`; alert on 5xx rate and OCR failure spike |
| 6.4 | Load fixtures: 5 prescriptions, 3 report pairs, 2 profiles; deterministic replay mode (`DEMO_MODE=true` uses cached OCR to avoid live-demo risk) |
| 6.5 | Test suite: unit (normalization, comparison math, savings, safety rules), integration (each API), one E2E happy path |
| 6.6 | Security pass: file-type validation, size limits, no secrets in repo, private endpoints or firewall rules on data services, RBAC-only data access, dependency scan |
| 6.7 | `docs/demo-script.md`, one-pager, slides, backup recording |

#### Test matrix

| Layer | Cases |
|-------|-------|
| Unit | Strength parsing, synonym mapping, unit conversion, change classification thresholds, savings math, all six safety rules |
| Contract | Every endpoint: happy path, missing consent, oversized file, wrong MIME, low-confidence path |
| Integration | OCR -> normalize -> RAG -> agent -> PDF for one prescription; two-report comparison |
| Safety | Red-team prompts attempting diagnosis, dosage change, emergency advice; all must be blocked |
| Performance | Prescription flow p95 under 12 s; report analysis p95 under 15 s |

---

## 4. Data Models

### 4.1 Cosmos DB `profiles` (pk `/userId`)

```json
{
  "id": "profile-<userId>",
  "userId": "<entra-oid>",
  "demographics": { "ageBand": "35-44", "sex": "F", "location": "Bengaluru" },
  "consent": { "version": "1.0", "acceptedAt": "2026-08-27T10:00:00Z", "purposes": ["ocr", "analysis", "pdf"] },
  "preferences": { "allergies": ["peanut"], "cuisine": "south-indian-veg", "budget": "low", "goals": ["reduce-hba1c"] },
  "latestSummaryId": "report-...",
  "createdAt": "...", "updatedAt": "..."
}
```

### 4.2 Cosmos DB `reports` (pk `/userId`)

```json
{
  "id": "report-<uuid>",
  "userId": "<entra-oid>",
  "reportDate": "2026-06-14",
  "reportType": "lab-panel",
  "blobPath": "raw-uploads/<userId>/2026-06/<uuid>.pdf",
  "ocr": { "engine": "prebuilt-layout", "avgConfidence": 0.93, "handwrittenRatio": 0.02 },
  "parameters": [
    { "canonicalKey": "hba1c", "displayName": "HbA1c", "value": 7.4, "unit": "%",
      "refLow": 4.0, "refHigh": 5.6, "status": "high", "sourceConfidence": 0.96 }
  ],
  "healthScore": 68,
  "summaryNarrative": "...",
  "safety": { "pass": true, "notes": [] }
}
```

### 4.3 Azure SQL

```sql
CREATE TABLE Medicine (
  MedicineId       INT IDENTITY PRIMARY KEY,
  BrandName        NVARCHAR(200) NOT NULL,
  ActiveIngredient NVARCHAR(300) NOT NULL,
  StrengthValue    DECIMAL(10,3) NOT NULL,
  StrengthUnit     NVARCHAR(10)  NOT NULL,
  DosageForm       NVARCHAR(50)  NOT NULL,
  GenericName      NVARCHAR(200) NULL,
  Manufacturer     NVARCHAR(200) NULL,
  IsDemoData       BIT NOT NULL DEFAULT 1
);
CREATE INDEX IX_Medicine_Match ON Medicine(ActiveIngredient, StrengthValue, StrengthUnit, DosageForm);

CREATE TABLE MedicinePrice (
  PriceId    INT IDENTITY PRIMARY KEY,
  MedicineId INT NOT NULL REFERENCES Medicine(MedicineId),
  MrpInr     DECIMAL(10,2) NOT NULL,
  SourceName NVARCHAR(100) NOT NULL,
  SourceUrl  NVARCHAR(500) NULL,
  SourceDate DATE NOT NULL
);

CREATE TABLE LabMetric (
  MetricId     BIGINT IDENTITY PRIMARY KEY,
  UserId       NVARCHAR(64) NOT NULL,
  ReportId     NVARCHAR(64) NOT NULL,
  CanonicalKey NVARCHAR(60) NOT NULL,
  Value        DECIMAL(12,4) NOT NULL,
  Unit         NVARCHAR(20) NOT NULL,
  ReportDate   DATE NOT NULL,
  Status       NVARCHAR(20) NOT NULL
);
CREATE INDEX IX_LabMetric_Trend ON LabMetric(UserId, CanonicalKey, ReportDate);

CREATE TABLE ShareLink (
  ShareId    NVARCHAR(64) PRIMARY KEY,   -- SHA-256 of token
  BlobPath   NVARCHAR(500) NOT NULL,
  UserId     NVARCHAR(64) NOT NULL,
  ExpiresAt  DATETIME2 NOT NULL,
  RevokedAt  DATETIME2 NULL,
  AccessCount INT NOT NULL DEFAULT 0
);
```

---

## 5. Security and Responsible AI Checklist

| Control | Implementation | Verified in |
|---------|----------------|-------------|
| Consent-first | Blocking modal; consent version persisted with every upload | M1 |
| PHI minimization | `deidentify.py` runs before any LLM call; age band instead of DOB | M1 |
| Encryption | Storage/Cosmos/SQL encryption at rest; TLS 1.2+ in transit | M0 |
| Least privilege | Managed identity + RBAC data roles; zero connection strings in app config | M0 |
| Secrets | Key Vault references only; `.env` is dev-only and gitignored | M0 |
| Upload safety | Extension + MIME + magic-byte checks, 10 MB cap, no archive/SVG | M1 |
| Injection defense | OCR text treated as untrusted data, wrapped in delimiters, never as instructions | M4 |
| Human-in-the-loop | Doctor approval section mandatory on PDF | M5 |
| Grounding | Citation check enforced by `SafetyReviewerAgent` | M4 |
| Auditability | `runs` container logs inputs hash, tool calls, agent versions, safety verdict | M6 |
| Share-link safety | Hashed token, 24 h user-delegation SAS, revocable, rate limited | M5 |
| Data retention | Demo data purged post-hackathon; lifecycle rule deletes blobs after 7 days | M6 |

---

## 6. Risk Register with Engineering Mitigations

| Risk | Mitigation in this plan |
|------|-------------------------|
| Handwriting OCR failure | Confidence gate at 0.75, mandatory user confirmation grid, manual entry fallback |
| Wrong alternative match | Hard equality on ingredient/strength/form, 24-month source freshness, exact multiset for combinations, doctor approval flag |
| Stale price data | `sourceDate` displayed on every row; savings labeled estimated |
| Hallucination | Citation-required prompts, retrieval-only claims, safety reviewer R2/R3 |
| Live-demo flakiness | `DEMO_MODE` replays cached OCR and retrieval fixtures; backup recorded video |
| Azure quota/latency | Pre-provision on day 0, warm deployments, p95 budgets tracked in App Insights |
| Scope creep | Out-of-scope list from design enforced; anything new goes to Phase 2 backlog |

---

## 7. Definition of Done (maps to design success metrics)

| Metric | Done when |
|--------|-----------|
| Prescription OCR | 5 sample prescriptions/tablet images extract medicines with confidence shown |
| Medicine alternatives | Generic + cheaper alternatives returned with source, source date, and confidence |
| Doctor-review PDF | Every analyzed prescription produces a downloadable and shareable PDF |
| Report analysis | Common lab fields parsed and rendered as a visual health snapshot |
| Report comparison | Improved / worsened / unchanged / newly abnormal / missing correctly classified on 3 report pairs |
| Meal planner | Condition-aware plan generated with allergy and cuisine handling |
| Safety compliance | Zero outputs without disclaimer; red-team suite fully blocked |

---

## 8. Immediate Next Actions

1. Confirm frontend choice (React + TypeScript SPA for MVP) and Azure subscription/region.
2. Scaffold `backend/` and `frontend/` per section 2 and run `uv sync`.
3. Deploy `infra/main.bicep` to a dedicated resource group.
4. Author the 4 seed datasets in `data/` - this is the critical path for M2 and M3.
5. Collect the 5 sample prescriptions and 3 report pairs for fixtures and the demo.
