#Requires -Version 7.0
<#
.SYNOPSIS
  Grants an additional Entra principal db_datareader/db_datawriter on the Health IQ SQL database.

.DESCRIPTION
  Azure SQL contained-user creation cannot be expressed in Bicep/ARM, so this script runs
  infra/scripts/configure-sql-rbac.sql via sqlcmd using Azure AD interactive authentication.
  Must be run by (or with a token from) the SQL server's Entra admin.

.PARAMETER ServerFqdn
  Fully qualified domain name of the SQL logical server (see main.bicep output `sqlServerFqdn`).

.PARAMETER DatabaseName
  Target database name (see main.bicep output `sqlDatabaseName`, default "healthiq").

.PARAMETER PrincipalName
  UPN, managed identity display name, or Entra group name to grant access to.

.EXAMPLE
  ./infra/scripts/Set-SqlRbac.ps1 -ServerFqdn hiq-sql-abc123.database.windows.net -DatabaseName healthiq -PrincipalName teammate@contoso.com
#>
param(
  [Parameter(Mandatory = $true)]
  [string]$ServerFqdn,

  [Parameter(Mandatory = $false)]
  [string]$DatabaseName = 'healthiq',

  [Parameter(Mandatory = $true)]
  [string]$PrincipalName
)

$ErrorActionPreference = 'Stop'

if (-not (Get-Command sqlcmd -ErrorAction SilentlyContinue)) {
  throw 'sqlcmd not found. Install the "sqlcmd" utility (or the Azure CLI "sql" extension) first.'
}

$scriptPath = Join-Path $PSScriptRoot 'configure-sql-rbac.sql'
$rendered = (Get-Content $scriptPath -Raw) -replace '\{\{PRINCIPAL_NAME\}\}', $PrincipalName
$tempFile = New-TemporaryFile
Set-Content -Path $tempFile -Value $rendered -NoNewline

try {
  Write-Host "Granting db_datareader/db_datawriter to '$PrincipalName' on $DatabaseName@$ServerFqdn ..." -ForegroundColor Cyan
  sqlcmd -S $ServerFqdn -d $DatabaseName -G -Q "$rendered"
  Write-Host 'Done.' -ForegroundColor Green
}
finally {
  Remove-Item $tempFile -ErrorAction SilentlyContinue
}
