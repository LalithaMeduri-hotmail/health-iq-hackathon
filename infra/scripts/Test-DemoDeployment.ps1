#Requires -Version 7.0
# Prints the backend managed identity's effective RBAC and probes the live endpoints.
param(
  [string]$ResourceGroupName = 'rg-healthiq-demo',
  [string]$DataResourceGroup = 'rg-healthiq-local',
  [string]$BackendApp = 'hiq-api',
  [string]$FrontendApp = 'hiq-web',
  [string]$CosmosAccount = 'hiq-cosmos-4nrhw3yvnlazg'
)
$ErrorActionPreference = 'Continue'

$principalId = az containerapp show -g $ResourceGroupName -n $BackendApp --query 'identity.principalId' -o tsv
Write-Host "principalId: $principalId"

Write-Host "`n--- ARM roles ---"
az role assignment list --assignee $principalId --all -o tsv --query '[].roleDefinitionName'

Write-Host "`n--- Cosmos data-plane roles ---"
az cosmosdb sql role assignment list -g $DataResourceGroup -a $CosmosAccount -o tsv `
  --query "[?principalId=='$principalId'].roleDefinitionId"

$domain = az containerapp show -g $ResourceGroupName -n $BackendApp --query 'properties.configuration.ingress.fqdn' -o tsv
$web = az containerapp show -g $ResourceGroupName -n $FrontendApp --query 'properties.configuration.ingress.fqdn' -o tsv

Write-Host "`n--- probes ---"
foreach ($probe in @("https://$domain/health", "https://$web/")) {
  try {
    $r = Invoke-WebRequest -Uri $probe -TimeoutSec 90 -SkipHttpErrorCheck
    Write-Host ("{0} -> {1}" -f $probe, $r.StatusCode)
  }
  catch {
    Write-Host ("{0} -> ERR {1}" -f $probe, $_.Exception.Message)
  }
}
