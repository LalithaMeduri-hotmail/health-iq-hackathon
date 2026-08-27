// Azure AI Search (hybrid BM25 + vector, semantic ranker) backing the 4 RAG indexes
// (Implementation Plan Section 3.1 / M3).
@description('Azure region for the resources.')
param location string

@description('Name of the Azure AI Search service. Lowercase alphanumeric + hyphens, 2-60 chars.')
param searchServiceName string

@description('Tags applied to all resources in this module.')
param tags object = {}

@description('SKU for the search service.')
@allowed([
  'free'
  'basic'
  'standard'
])
param skuName string = 'basic'

@description('Number of replicas.')
param replicaCount int = 1

@description('Number of partitions.')
param partitionCount int = 1

@description('Principal IDs granted Search Index Data Contributor (build/ingest job).')
param indexDataContributorPrincipalIds array = []

@description('Principal IDs granted Search Index Data Reader (query-only, e.g. backend runtime identity).')
param indexDataReaderPrincipalIds array = []

resource searchService 'Microsoft.Search/searchServices@2023-11-01' = {
  name: searchServiceName
  location: location
  tags: tags
  sku: {
    name: skuName
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    replicaCount: replicaCount
    partitionCount: partitionCount
    hostingMode: 'default'
    semanticSearch: 'standard'
    publicNetworkAccess: 'enabled'
    disableLocalAuth: false // keep API keys available as a local-dev fallback; app code prefers DefaultAzureCredential
    authOptions: {
      aadOrApiKey: {
        aadAuthFailureMode: 'http401WithBearerChallenge'
      }
    }
  }
}

@description('Built-in role: Search Index Data Contributor.')
var indexDataContributorRoleId = '8ebe5a00-799e-43f5-93ac-243d3dce84a7'

@description('Built-in role: Search Index Data Reader.')
var indexDataReaderRoleId = '1407120a-92aa-4202-b7e9-c0e197c71c8f'

resource indexDataContributorAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for principalId in indexDataContributorPrincipalIds: {
  name: guid(searchService.id, principalId, indexDataContributorRoleId)
  scope: searchService
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', indexDataContributorRoleId)
    principalId: principalId
  }
}]

resource indexDataReaderAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for principalId in indexDataReaderPrincipalIds: {
  name: guid(searchService.id, principalId, indexDataReaderRoleId)
  scope: searchService
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', indexDataReaderRoleId)
    principalId: principalId
  }
}]

output searchServiceName string = searchService.name
output searchEndpoint string = 'https://${searchService.name}.search.windows.net'
