#Requires -Version 7.0
<#
.SYNOPSIS
  Deploys the Health IQ Bicep infrastructure to an Azure resource group.

.DESCRIPTION
  Thin wrapper around `az deployment group create`. Creates the resource group if it
  does not exist, then deploys infra/main.bicep with the parameter file for the given
  environment (local|dev). Optionally auto-fills the developer's Entra object id and
  public IP so main.local.parameters.json placeholders do not need manual editing.

.PARAMETER Environment
  "local" or "dev". Selects infra/main.<Environment>.parameters.json.

.PARAMETER ResourceGroupName
  Target resource group name. Created if missing.

.PARAMETER Location
  Azure region used when creating the resource group.

.EXAMPLE
  ./infra/scripts/deploy.ps1 -Environment local -ResourceGroupName rg-healthiq-local -Location eastus2
#>
param(
  [Parameter(Mandatory = $true)]
  [ValidateSet('local', 'dev')]
  [string]$Environment,

  [Parameter(Mandatory = $true)]
  [string]$ResourceGroupName,

  [Parameter(Mandatory = $false)]
  [string]$Location = 'eastus2',

  [Parameter(Mandatory = $false)]
  [switch]$AutoFillDeveloperIdentity
)

$ErrorActionPreference = 'Stop'

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..' '..')
$bicepFile = Join-Path $repoRoot 'infra' 'main.bicep'
$paramsFile = Join-Path $repoRoot 'infra' "main.$Environment.parameters.json"

if (-not (Test-Path $paramsFile)) {
  throw "Parameter file not found: $paramsFile"
}

Write-Host "Ensuring resource group '$ResourceGroupName' exists in '$Location'..." -ForegroundColor Cyan
az group create --name $ResourceGroupName --location $Location --output none

$overrides = @()

if ($AutoFillDeveloperIdentity) {
  Write-Host 'Resolving signed-in user object id and public IP for local RBAC/firewall...' -ForegroundColor Cyan
  $objectId = az ad signed-in-user show --query id -o tsv
  $upn = az ad signed-in-user show --query userPrincipalName -o tsv
  $publicIp = (Invoke-RestMethod -Uri 'https://api.ipify.org?format=json').ip

  if (-not $objectId) {
    throw 'Could not resolve signed-in user. Run "az login" first.'
  }

  $overrides += "developerPrincipalId=$objectId"
  $overrides += "sqlAadAdminObjectId=$objectId"
  $overrides += "sqlAadAdminLogin=$upn"
  $overrides += "localDevClientIp=$publicIp"
  Write-Host "  developerPrincipalId = $objectId"
  Write-Host "  sqlAadAdminLogin     = $upn"
  Write-Host "  localDevClientIp     = $publicIp"
}

Write-Host "Deploying $bicepFile with $paramsFile ..." -ForegroundColor Cyan
$deployArgs = @(
  'deployment', 'group', 'create',
  '--resource-group', $ResourceGroupName,
  '--template-file', $bicepFile,
  '--parameters', "@$paramsFile"
)
foreach ($override in $overrides) {
  $deployArgs += '--parameters'
  $deployArgs += $override
}

az @deployArgs

Write-Host 'Deployment complete. Fetching outputs...' -ForegroundColor Green
az deployment group show --resource-group $ResourceGroupName --name main --query properties.outputs
