# health-iq-hackathon
This is a hackathon project solution for health iq project

## Documentation

- [Implementation plan](docs/implementation-plan.md)
- [Team plan](docs/team-plan.md)
- [Low level design](docs/lld/1-low-level-design-overview.md)

## Repository structure

```text
backend/    FastAPI service: app/{api,models,services,agents,rag,repositories}, tests/
frontend/   React + TypeScript SPA (Vite): src/{routes,features,components,lib}
data/       Seed CSV/JSON/MD sources for the medicine catalog, reference ranges,
            specialist mapping, nutrition rules, lab synonyms, and demo samples
infra/      Bicep IaC (see infra/README.md)
scripts/    seed_sql.py, build_search_indexes.py, run_local.ps1
docs/       Implementation plan, team plan, low-level design
```

Every backend/frontend folder already contains the scaffolding (package manifests, app factory,
router/model/service/agent stubs with `TODO` markers) described in
[`docs/implementation-plan.md`](docs/implementation-plan.md) Section 2, so each dev can start
adding code directly in their owned area per [`docs/team-plan.md`](docs/team-plan.md):

| Dev | Owns |
|-----|------|
| D1 - Platform/Ingestion | `infra/`, `backend/app/services/{ocr,blob,deidentify}.py`, `backend/app/deps.py` (Azure clients), observability wiring in `main.py` |
| D2 - Domain Data/RAG | `data/`, `backend/app/services/{normalize_medicine,normalize_lab,reference_ranges,comparison}.py`, `backend/app/rag/`, `backend/app/repositories/sql_repo.py` |
| D3 - Agents/Outputs | `backend/app/agents/` (incl. `prompts/*.md`), `backend/app/services/{pdf_builder,share_links}.py` |
| D4 - API/Frontend | `backend/app/{api,models}/`, `backend/app/repositories/cosmos_repo.py`, all of `frontend/` |

## Running locally

Prerequisites: [`uv`](https://docs.astral.sh/uv/) (Python 3.11), Node.js 20+, and the infra
provisioned per the section below (`.env` filled in from `.env.example`).

```powershell
cd backend; uv sync --extra dev; cd ..
cd frontend; npm install; cd ..
./scripts/run_local.ps1   # starts uvicorn (:8000) and vite (:5173) together
```

Or run each independently:
`uv run --project backend --directory backend uvicorn app.main:app --reload --reload-dir app` and
`npm --prefix frontend run dev`. Verify with `GET http://localhost:8000/health`.

With `DEMO_MODE=true` (the `.env.example` default) the app runs entirely on cached fixtures, so no
Azure resources are required to start the servers or run the test suite.

## Provisioning the infrastructure

All Azure resources (Storage, Cosmos DB, Azure SQL, AI Search, Document Intelligence, Azure
OpenAI, Key Vault, Monitoring) are defined as Bicep in [`infra/`](infra/README.md). Local
development and the shared `dev` environment use the **same** provisioned resources - there is no
local emulator for Search/OpenAI/Document Intelligence, so `local` just means the app runs on your
machine while talking to those resources over the network.

### Prerequisites

- Azure CLI (`az login`) and Bicep CLI (`az bicep install`)
- Contributor + User Access Administrator (or Owner) on the target subscription/resource group
- Azure OpenAI access with `gpt-5.4` and `text-embedding-3-large` quota in the target region

### Provision for local development

```powershell
./infra/scripts/deploy.ps1 -Environment local -ResourceGroupName rg-healthiq-local -Location eastus2 -AutoFillDeveloperIdentity
```

This auto-fills your Entra object id and public IP into the deployment, grants your account
RBAC access to every resource, and writes all endpoints into Key Vault. Then copy `.env.example`
to `.env` and set `AZURE_KEY_VAULT_URI` to the deployment's `keyVaultUri` output - with `az login`
active, the backend authenticates via `DefaultAzureCredential` automatically (no keys needed).

### Provision for the shared dev environment

```powershell
./infra/scripts/deploy.ps1 -Environment dev -ResourceGroupName rg-healthiq-dev -Location eastus2
```

Fill in `infra/main.dev.parameters.json` first (SQL AAD admin group, etc.) and set
`deployContainerApps=true` once a backend/frontend container image exists to also provision
Container Apps hosting.

See [`infra/README.md`](infra/README.md) for the full resource list, RBAC model, SQL access
grants, and cost/teardown notes.
