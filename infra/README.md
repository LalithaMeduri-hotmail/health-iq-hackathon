# Health IQ Infrastructure

Bicep IaC that provisions every Azure resource required by the MVP (see
[`docs/implementation-plan.md`](../docs/implementation-plan.md) Section 2 and
[`docs/lld/8-low-level-design-cross-cutting-platform.md`](../docs/lld/8-low-level-design-cross-cutting-platform.md)
Section 7.4).

## Why the same infra for local and dev

There is no local emulator for Azure AI Search, Azure OpenAI, or Document Intelligence, so
**local development connects to the same provisioned Azure resources as the `dev` environment** -
only the deploying identity and resource sizing differ. `environmentName` (`local` | `dev`)
only affects resource naming/tags and whether Container Apps hosting is deployed.

| | `local` | `dev` |
|---|---|---|
| Resources provisioned | Storage, Cosmos, SQL, Search, Doc Intelligence, OpenAI, Key Vault, Monitoring | same |
| Who has data-plane RBAC | Your Entra user (`developerPrincipalId`) | Team/CI identity + Container Apps managed identity |
| Compute | Runs on your machine (`uvicorn` + `vite`) | Azure Container Apps (`deployContainerApps=true`) |

## Layout

```text
infra/
├─ main.bicep                     # orchestrates all modules, writes config to Key Vault
├─ main.parameters.json           # generic template (docs reference)
├─ main.local.parameters.json     # local development deployment
├─ main.dev.parameters.json       # shared dev/demo deployment
├─ modules/
│  ├─ monitoring.bicep            # Log Analytics + Application Insights
│  ├─ keyvault.bicep              # RBAC-mode Key Vault (single config source for config.py)
│  ├─ storage.bicep               # Blob: raw-uploads, generated-pdfs, thumbnails
│  ├─ cosmos.bicep                # Serverless Cosmos DB: profiles, reports, runs
│  ├─ sql.bicep                   # Entra-only Azure SQL server + database
│  ├─ search.bicep                # Azure AI Search (hybrid + semantic ranker)
│  ├─ docintel.bicep              # Document Intelligence (prebuilt-read/layout)
│  ├─ openai.bicep                # Azure AI Foundry account (kind=AIServices) + project: gpt-5.4 + text-embedding-3-large
│  └─ containerapps.bicep         # Optional dev/demo hosting (backend + frontend)
└─ scripts/
   ├─ deploy.ps1                  # az deployment group create wrapper
   ├─ configure-sql-rbac.sql      # grants an extra Entra principal DB access
   └─ Set-SqlRbac.ps1             # runs the .sql script via sqlcmd (AAD auth)
```

## Prerequisites

- Azure CLI (`az`) logged in: `az login`
- Bicep CLI: `az bicep install` (or `az bicep upgrade`)
- Contributor + User Access Administrator (or Owner) on the target subscription/resource group,
  so the deployment can create RBAC role assignments
- Azure OpenAI access approved on the subscription, with `gpt-5.4` and `text-embedding-3-large`
  quota in the target region
- `deploy.ps1` requires PowerShell 7 (`pwsh`); on Windows PowerShell 5.1, run the equivalent
  `az deployment group create` command shown below instead.

### Known regional/subscription quirks (observed 2026-09)

- `chatModelVersion`/`chatModelName` in `modules/openai.bicep` may need bumping if Azure marks the
  current default model version "Deprecating" (`az cognitiveservices model list -l <region> --query "[?model.name=='gpt-5.4']"`).
- If Azure AI Search reports `InsufficientResourcesAvailable` in `location`, override just Search
  via the `searchLocation` parameter (already set to `eastus` in `main.local.parameters.json`).
- If Azure SQL reports `RegionDoesNotAllowProvisioning`, try the `sqlLocation` parameter override -
  but if it fails across multiple regions (eastus2/eastus/westus2/southcentralus all failed on one
  subscription), that's a subscription-level restriction on first-time SQL server creation, not a
  regional one; it needs an Azure support request. The app degrades gracefully without it -
  `sql_repo.py` falls back to `data/medicines/medicine_catalog.csv` whenever
  `AZURE_SQL_SERVER_FQDN` is unset, so leave that `.env` value empty and move on.
- A failed SQL server deployment can leave a phantom name/location reservation ("resource already
  exists in location X") even though `az sql server list` shows nothing - clear it with
  `az sql server delete --name <name> --resource-group <rg> --yes` before retrying in a new region.

## 1. Fill in parameters

Edit `infra/main.local.parameters.json` (or run `deploy.ps1 -AutoFillDeveloperIdentity` to fill
these automatically):

| Parameter | How to get it |
|---|---|
| `developerPrincipalId` | `az ad signed-in-user show --query id -o tsv` |
| `sqlAadAdminObjectId` | same as above (or your team's Entra group object id) |
| `sqlAadAdminLogin` | `az ad signed-in-user show --query userPrincipalName -o tsv` (or group display name) |
| `localDevClientIp` | your current public IP, e.g. `curl https://api.ipify.org` |

## 2. Deploy

```powershell
# Local development
./infra/scripts/deploy.ps1 -Environment local -ResourceGroupName rg-healthiq-local -Location eastus2 -AutoFillDeveloperIdentity

# Shared dev/demo environment
./infra/scripts/deploy.ps1 -Environment dev -ResourceGroupName rg-healthiq-dev -Location eastus2
```

Or directly with the Azure CLI:

```powershell
az group create -n rg-healthiq-local -l eastus2
az deployment group create -g rg-healthiq-local -f infra/main.bicep -p infra/main.local.parameters.json
```

Deployment provisions:

- **Storage account** (`Standard_LRS`) with `raw-uploads`, `generated-pdfs`, `thumbnails`
  containers, blob versioning, soft delete, and a lifecycle rule tiering old raw uploads to cool.
- **Cosmos DB** (serverless, NoSQL API) with `profiles`, `reports`, `runs` containers partitioned
  on `/userId`. AAD-only (`disableLocalAuth: true`) - no primary keys.
- **Azure SQL** logical server with **Entra-only authentication** (no SQL logins/passwords) and a
  `healthiq` database. Run `scripts/seed_sql.py` (backend repo, once it exists) to create the
  `Medicine`, `MedicinePrice`, `LabMetric`, `ShareLink` tables.
- **Azure AI Search** (`basic`, semantic ranker `standard`) ready for the 4 RAG indexes built by
  `scripts/build_search_indexes.py`.
- **Document Intelligence** (`S0`) and **Azure AI Foundry account** (`S0`, kind `AIServices`, with a
  Foundry Project and `gpt-5.4` + `text-embedding-3-large` deployments). `allowProjectManagement`
  is enabled so the account also exposes the full Foundry model catalog and portal; agents keep
  calling it through the OpenAI-compatible endpoint via `AzureOpenAIChatClient`.
- **Key Vault** (RBAC mode) pre-loaded with every endpoint/deployment name as a secret, so
  `config.py` reads configuration the same way in every environment.
- **Log Analytics + Application Insights** for OpenTelemetry traces and custom metrics.
- RBAC role assignments scoped to each resource for `developerPrincipalId` (and, when
  `deployContainerApps=true`, the Container App's managed identity) - no connection strings or
  API keys required by the application.

## 3. Grant SQL data access to additional principals

The SQL AAD admin (`sqlAadAdminObjectId`) already has full access. To grant another teammate or
the Container App's managed identity `db_datareader`/`db_datawriter`:

```powershell
./infra/scripts/Set-SqlRbac.ps1 -ServerFqdn <sqlServerFqdn output> -PrincipalName teammate@contoso.com
```

## 4. Point the backend at these resources

Copy `.env.example` (repo root) to `.env` and set `AZURE_KEY_VAULT_URI` to the `keyVaultUri`
deployment output. With `az login` active locally, `DefaultAzureCredential` picks up your session
automatically - no keys needed.

## Cost / cleanup notes

- Default SKUs are the cheapest tier that supports every required feature (serverless Cosmos,
  Search `basic`, SQL `Basic`, Storage `Standard_LRS`) to keep hackathon spend low.
- `deployContainerApps` defaults to `false`; enable it only when you actually deploy the backend
  container image (Day 4 per `docs/team-plan.md`).
- Tear down with `az group delete -n <resource-group> --yes --no-wait`.

## Deferred / out of scope

- API Management is intentionally not provisioned (open question in the LLD; JWT validation can
  happen directly in FastAPI for the MVP).
- Private endpoints/VNet integration are left as a hardening follow-up (`networkAcls` default to
  `Allow` for demo simplicity); tighten before any non-demo use.
