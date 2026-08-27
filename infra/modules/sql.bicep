// Azure SQL (Entra-only auth) for Medicine / MedicinePrice / LabMetric / ShareLink tables
// (Implementation Plan Section M0, LLD 7.1 - "Entra-auth db_datareader + scoped writer").
@description('Azure region for the resources.')
param location string

@description('Name of the logical SQL server. Lowercase alphanumeric + hyphens, 1-63 chars.')
param sqlServerName string

@description('Name of the SQL database.')
param sqlDatabaseName string = 'healthiq'

@description('Tags applied to all resources in this module.')
param tags object = {}

@description('Entra tenant id.')
param tenantId string = tenant().tenantId

@description('Display name (UPN or group name) of the Entra AAD admin for the SQL server.')
param aadAdminLogin string

@description('Object id of the Entra AAD admin principal (user, group, or service principal).')
param aadAdminObjectId string

@description('Principal type of the AAD admin: User, Group, or Application.')
@allowed([
  'User'
  'Group'
  'Application'
])
param aadAdminPrincipalType string = 'User'

@description('Optional client IP address to allow through the firewall for local development. Leave empty to skip.')
param localDevClientIp string = ''

@description('SKU name for the database, e.g. Basic, S0, GP_S_Gen5_1.')
param databaseSkuName string = 'Basic'

@description('SKU tier for the database.')
param databaseSkuTier string = 'Basic'

resource sqlServer 'Microsoft.Sql/servers@2023-08-01' = {
  name: sqlServerName
  location: location
  tags: tags
  properties: {
    administrators: {
      administratorType: 'ActiveDirectory'
      principalType: aadAdminPrincipalType
      login: aadAdminLogin
      sid: aadAdminObjectId
      tenantId: tenantId
      azureADOnlyAuthentication: true // no SQL logins/passwords - matches "no secrets in code" design decision
    }
    minimalTlsVersion: '1.2'
    publicNetworkAccess: 'Enabled'
  }
}

resource sqlDatabase 'Microsoft.Sql/servers/databases@2023-08-01' = {
  parent: sqlServer
  name: sqlDatabaseName
  location: location
  tags: tags
  sku: {
    name: databaseSkuName
    tier: databaseSkuTier
  }
  properties: {
    zoneRedundant: false
  }
}

resource allowAzureServices 'Microsoft.Sql/servers/firewallRules@2023-08-01' = {
  parent: sqlServer
  name: 'AllowAllWindowsAzureIps'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

resource allowLocalDev 'Microsoft.Sql/servers/firewallRules@2023-08-01' = if (!empty(localDevClientIp)) {
  parent: sqlServer
  name: 'AllowLocalDevClient'
  properties: {
    startIpAddress: localDevClientIp
    endIpAddress: localDevClientIp
  }
}

output sqlServerFqdn string = sqlServer.properties.fullyQualifiedDomainName
output sqlServerName string = sqlServer.name
output sqlDatabaseName string = sqlDatabase.name
