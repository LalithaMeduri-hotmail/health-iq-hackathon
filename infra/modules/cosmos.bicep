// Cosmos DB (NoSQL, serverless) for profiles/reports/runs (Implementation Plan Section M0/M3, LLD 7.1).
@description('Azure region for the resources.')
param location string

@description('Name of the Cosmos DB account. Lowercase alphanumeric + hyphens, 3-44 chars.')
param cosmosAccountName string

@description('Name of the SQL (NoSQL) database.')
param databaseName string = 'healthiq'

@description('Tags applied to all resources in this module.')
param tags object = {}

@description('Principal IDs (AAD object ids) granted Cosmos DB Built-in Data Contributor at the account scope.')
param dataContributorPrincipalIds array = []

var containerDefs = [
  {
    name: 'profiles'
    partitionKey: '/userId'
  }
  {
    name: 'reports'
    partitionKey: '/userId'
  }
  {
    name: 'runs'
    partitionKey: '/userId'
  }
]

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' = {
  name: cosmosAccountName
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    databaseAccountOfferType: 'Standard'
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    capabilities: [
      {
        name: 'EnableServerless'
      }
    ]
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    disableLocalAuth: true // RBAC (Entra) only, no primary/secondary keys - matches "no secrets" design decision
    publicNetworkAccess: 'Enabled'
    minimalTlsVersion: 'Tls12'
  }
}

resource sqlDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-05-15' = {
  parent: cosmosAccount
  name: databaseName
  properties: {
    resource: {
      id: databaseName
    }
  }
}

resource sqlContainers 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = [for c in containerDefs: {
  parent: sqlDatabase
  name: c.name
  properties: {
    resource: {
      id: c.name
      partitionKey: {
        paths: [
          c.partitionKey
        ]
        kind: 'Hash'
        version: 2
      }
      defaultTtl: -1
    }
  }
}]

@description('Cosmos DB built-in data-plane role definition id for "Cosmos DB Built-in Data Contributor".')
var dataContributorRoleDefinitionId = '${cosmosAccount.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002'

resource dataContributorAssignments 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = [for principalId in dataContributorPrincipalIds: {
  parent: cosmosAccount
  name: guid(cosmosAccount.id, principalId, dataContributorRoleDefinitionId)
  properties: {
    roleDefinitionId: dataContributorRoleDefinitionId
    principalId: principalId
    scope: cosmosAccount.id
  }
}]

output cosmosAccountName string = cosmosAccount.name
output cosmosEndpoint string = cosmosAccount.properties.documentEndpoint
output databaseName string = sqlDatabase.name
