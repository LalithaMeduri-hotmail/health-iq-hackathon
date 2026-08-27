// Blob Storage for raw uploads, generated PDFs and thumbnails (Implementation Plan Section 2, M0/M1).
@description('Azure region for the resources.')
param location string

@description('Name of the storage account. Lowercase alphanumeric, 3-24 chars.')
@minLength(3)
@maxLength(24)
param storageAccountName string

@description('Tags applied to all resources in this module.')
param tags object = {}

@description('Origins allowed for CORS on blob endpoints (local dev + hosted frontend).')
param corsAllowedOrigins array = [
  'http://localhost:5173'
  'http://localhost:3000'
]

@description('Principal IDs granted Storage Blob Data Contributor (read/write blobs).')
param blobDataContributorPrincipalIds array = []

@description('Principal IDs granted Storage Blob Delegator (issue user-delegation SAS for share links).')
param blobDelegatorPrincipalIds array = []

@description('Days after which blobs in raw-uploads move to cool tier (cost control for demo data).')
param rawUploadsCoolAfterDays int = 30

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  tags: tags
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: true // dev convenience; app code uses DefaultAzureCredential (RBAC) exclusively
    supportsHttpsTrafficOnly: true
    accessTier: 'Hot'
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
  }
}

resource blobServices 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storageAccount
  name: 'default'
  properties: {
    isVersioningEnabled: true
    deleteRetentionPolicy: {
      enabled: true
      days: 14
    }
    containerDeleteRetentionPolicy: {
      enabled: true
      days: 14
    }
    cors: {
      corsRules: [
        {
          allowedOrigins: corsAllowedOrigins
          allowedMethods: [
            'GET'
            'PUT'
            'POST'
            'DELETE'
            'HEAD'
            'OPTIONS'
          ]
          allowedHeaders: [
            '*'
          ]
          exposedHeaders: [
            '*'
          ]
          maxAgeInSeconds: 3600
        }
      ]
    }
  }
}

var containerNames = [
  'raw-uploads'
  'generated-pdfs'
  'thumbnails'
]

resource containers 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = [for containerName in containerNames: {
  parent: blobServices
  name: containerName
  properties: {
    publicAccess: 'None'
  }
}]

resource lifecycleManagement 'Microsoft.Storage/storageAccounts/managementPolicies@2023-05-01' = {
  parent: storageAccount
  name: 'default'
  properties: {
    policy: {
      rules: [
        {
          name: 'raw-uploads-cool-tier'
          enabled: true
          type: 'Lifecycle'
          definition: {
            filters: {
              blobTypes: [
                'blockBlob'
              ]
              prefixMatch: [
                'raw-uploads/'
              ]
            }
            actions: {
              baseBlob: {
                tierToCool: {
                  daysAfterModificationGreaterThan: rawUploadsCoolAfterDays
                }
              }
            }
          }
        }
      ]
    }
  }
}

@description('Built-in role: Storage Blob Data Contributor.')
var blobDataContributorRoleId = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'

@description('Built-in role: Storage Blob Delegator (required to mint user-delegation SAS tokens).')
var blobDelegatorRoleId = 'db58b8e5-c6ad-4a2a-8342-4190687cbf4a'

resource blobDataContributorRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for principalId in blobDataContributorPrincipalIds: {
  name: guid(storageAccount.id, principalId, blobDataContributorRoleId)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', blobDataContributorRoleId)
    principalId: principalId
  }
}]

resource blobDelegatorRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for principalId in blobDelegatorPrincipalIds: {
  name: guid(storageAccount.id, principalId, blobDelegatorRoleId)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', blobDelegatorRoleId)
    principalId: principalId
  }
}]

output storageAccountName string = storageAccount.name
output blobEndpoint string = storageAccount.properties.primaryEndpoints.blob
output storageAccountId string = storageAccount.id
