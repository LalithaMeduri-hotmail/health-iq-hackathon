#Requires -Version 7.0
# Grants the backend container app's managed identity permission to send mail through
# Azure Communication Services. ACS Email with Entra auth has no data-plane role, so the
# identity needs `Contributor` scoped to the Communication Services resource itself.
param(
  [string]$ResourceGroupName = 'rg-healthiq-demo',
  [string]$DataResourceGroup = 'rg-healthiq-local',
  [string]$BackendApp = 'hiq-api',
  [string]$AcsName = 'hiq-acs-4nrhw3yvnlazg'
)
$ErrorActionPreference = 'Stop'

$principalId = az containerapp show -g $ResourceGroupName -n $BackendApp --query 'identity.principalId' -o tsv
$acsId = az communication show -g $DataResourceGroup -n $AcsName --query id -o tsv
if (-not $acsId) { throw "Communication Services resource $AcsName not found in $DataResourceGroup" }

az role assignment create --assignee-object-id $principalId --assignee-principal-type ServicePrincipal `
  --role 'Contributor' --scope $acsId -o none

Write-Host "Granted Contributor on $AcsName to $principalId"
