#Requires -Version 7.0
<#
.SYNOPSIS
  Builds and deploys the Health IQ demo (backend API + SPA) to Azure Container Apps.

.DESCRIPTION
  Creates a registry, a Container Apps environment, and two apps, then grants the backend's
  managed identity data-plane access to the Azure services provisioned by infra/main.bicep -
  which normally live in a DIFFERENT resource group (`-DataResourceGroup`).

  Configuration is read from `backend/.env` so the hosted app matches local development. Two
  values are deliberately overridden for hosting:
    DEMO_MODE=false            persist to Cosmos instead of process memory
    SESSION_COOKIE_SAMESITE    `none` - the SPA and API are on different hostnames, so a Lax
                               cookie would be dropped on every cross-site API call

.EXAMPLE
  ./infra/scripts/deploy-demo.ps1
.EXAMPLE
  ./infra/scripts/deploy-demo.ps1 -SkipBuild -Tag v2
#>
param(
  [string]$ResourceGroupName = 'rg-healthiq-demo',
  [string]$DataResourceGroup = 'rg-healthiq-local',
  [string]$Location = 'eastus2',
  [string]$RegistryName = 'hiqacr4nrhw3yvnlazg',
  [string]$EnvironmentName = 'hiq-cae-demo',
  [string]$BackendApp = 'hiq-api',
  [string]$FrontendApp = 'hiq-web',
  [string]$Tag = 'v1',
  [switch]$SkipBuild
)

$ErrorActionPreference = 'Stop'
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..' '..')
Push-Location $repoRoot
try {
  $envFile = Join-Path $repoRoot 'backend' '.env'
  if (-not (Test-Path $envFile)) { throw "backend/.env not found - it supplies the Azure endpoints." }
  $cfg = @{}
  Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*([A-Za-z0-9_]+)\s*=(.*)$') { $cfg[$matches[1]] = $matches[2].Trim() }
  }

  Write-Host "==> Resource group + registry" -ForegroundColor Cyan
  az group create -n $ResourceGroupName -l $Location -o none
  az acr create -g $ResourceGroupName -n $RegistryName --sku Basic --admin-enabled false -o none 2>$null
  $registry = "$RegistryName.azurecr.io"

  Write-Host "==> Container Apps environment" -ForegroundColor Cyan
  az containerapp env create -g $ResourceGroupName -n $EnvironmentName -l $Location --logs-destination none -o none 2>$null
  $domain = az containerapp env show -g $ResourceGroupName -n $EnvironmentName --query 'properties.defaultDomain' -o tsv
  # FQDNs are deterministic, so the SPA can be built against the API origin before either app exists.
  $apiUrl = "https://$BackendApp.$domain"
  $webUrl = "https://$FrontendApp.$domain"
  Write-Host "    API: $apiUrl"
  Write-Host "    Web: $webUrl"

  if (-not $SkipBuild) {
    Write-Host "==> Building images in ACR" -ForegroundColor Cyan
    az acr build -r $RegistryName -t "healthiq-backend:$Tag" -f backend/Dockerfile . -o none
    az acr build -r $RegistryName -t "healthiq-frontend:$Tag" -f frontend/Dockerfile `
      --build-arg "VITE_API_BASE_URL=$apiUrl" --build-arg 'VITE_DEMO_MODE=false' . -o none
  }

  $backendEnv = @(
    "AZURE_TENANT_ID=$($cfg.AZURE_TENANT_ID)"
    "AZURE_KEY_VAULT_URI=$($cfg.AZURE_KEY_VAULT_URI)"
    "AZURE_STORAGE_ACCOUNT_NAME=$($cfg.AZURE_STORAGE_ACCOUNT_NAME)"
    "AZURE_COSMOS_ENDPOINT=$($cfg.AZURE_COSMOS_ENDPOINT)"
    "AZURE_COSMOS_DATABASE_NAME=$($cfg.AZURE_COSMOS_DATABASE_NAME)"
    "AZURE_SEARCH_ENDPOINT=$($cfg.AZURE_SEARCH_ENDPOINT)"
    "AZURE_DOCINTEL_ENDPOINT=$($cfg.AZURE_DOCINTEL_ENDPOINT)"
    "AZURE_OPENAI_ENDPOINT=$($cfg.AZURE_OPENAI_ENDPOINT)"
    "AZURE_OPENAI_CHAT_DEPLOYMENT=$($cfg.AZURE_OPENAI_CHAT_DEPLOYMENT)"
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT=$($cfg.AZURE_OPENAI_EMBEDDING_DEPLOYMENT)"
    "AZURE_COMMUNICATION_ENDPOINT=$($cfg.AZURE_COMMUNICATION_ENDPOINT)"
    "ACS_SENDER_ADDRESS=$($cfg.ACS_SENDER_ADDRESS)"
    "OCR_CONFIDENCE_THRESHOLD=$($cfg.OCR_CONFIDENCE_THRESHOLD)"
    'DEMO_MODE=false'
    'SESSION_COOKIE_SECURE=true'
    'SESSION_COOKIE_SAMESITE=none'
    "CORS_ALLOWED_ORIGINS=$webUrl"
    "PUBLIC_API_BASE_URL=$apiUrl"
    'JWT_SECRET=secretref:jwt-secret'
  )

  Write-Host "==> Backend app" -ForegroundColor Cyan
  # Exactly one replica, always on. Share links and doctor reviews still live in
  # `sql_repo._DEMO_*` (process memory), so a second replica would 404 links minted by the first,
  # and scale-to-zero would discard them entirely.
  az containerapp create -g $ResourceGroupName -n $BackendApp --environment $EnvironmentName `
    --image "$registry/healthiq-backend:$Tag" `
    --registry-server $registry --registry-identity system `
    --system-assigned --ingress external --target-port 8000 --transport auto `
    --min-replicas 1 --max-replicas 1 --cpu 1.0 --memory 2.0Gi `
    --secrets "jwt-secret=$($cfg.JWT_SECRET)" `
    --env-vars $backendEnv -o none

  Write-Host "==> Frontend app" -ForegroundColor Cyan
  az containerapp create -g $ResourceGroupName -n $FrontendApp --environment $EnvironmentName `
    --image "$registry/healthiq-frontend:$Tag" `
    --registry-server $registry --registry-identity system --system-assigned `
    --ingress external --target-port 80 --transport auto `
    --min-replicas 1 --max-replicas 2 --cpu 0.25 --memory 0.5Gi -o none

  Write-Host "==> Data-plane RBAC for the backend identity" -ForegroundColor Cyan
  $principalId = az containerapp show -g $ResourceGroupName -n $BackendApp --query 'identity.principalId' -o tsv
  $dataRg = az group show -n $DataResourceGroup --query id -o tsv
  # Resource-group scope: every Health IQ data service lives in that one group.
  $roles = @(
    'Storage Blob Data Contributor'
    'Search Index Data Contributor'
    'Search Service Contributor'
    'Cognitive Services User'
    'Cognitive Services OpenAI User'
    'Key Vault Secrets User'
  )
  foreach ($role in $roles) {
    az role assignment create --assignee-object-id $principalId --assignee-principal-type ServicePrincipal `
      --role $role --scope $dataRg -o none 2>$null
    Write-Host "    $role"
  }
  # Cosmos data-plane access is a separate, Cosmos-specific role system.
  $cosmosAccount = ([uri]$cfg.AZURE_COSMOS_ENDPOINT).Host.Split('.')[0]
  az cosmosdb sql role assignment create -g $DataResourceGroup -a $cosmosAccount `
    --role-definition-name 'Cosmos DB Built-in Data Contributor' `
    --principal-id $principalId --scope '/' -o none 2>$null
  Write-Host "    Cosmos DB Built-in Data Contributor"

  Write-Host ""
  Write-Host "Share this link: $webUrl" -ForegroundColor Green
  Write-Host "API health:      $apiUrl/health"
}
finally {
  Pop-Location
}
