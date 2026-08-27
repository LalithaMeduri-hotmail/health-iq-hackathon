// RBAC-only Key Vault used as the single configuration/secret source for backend `config.py`
// (both local and dev environments read from here per the deployment design in Section 7.4).
@description('Azure region for the resources.')
param location string

@description('Name of the Key Vault. Must be globally unique, 3-24 chars.')
param keyVaultName string

@description('Tags applied to all resources in this module.')
param tags object = {}

@description('Entra tenant id that owns the vault.')
param tenantId string = tenant().tenantId

@description('Principal IDs (users/service principals/managed identities) granted Key Vault Secrets User.')
param secretsUserPrincipalIds array = []

@description('Principal IDs granted Key Vault Secrets Officer (can write secrets, e.g. deployment identity).')
param secretsOfficerPrincipalIds array = []

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  tags: tags
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    enablePurgeProtection: true
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
  }
}

@description('Built-in role: Key Vault Secrets User (read secret values).')
var secretsUserRoleId = '4633458b-17de-408a-b874-0445c86b69e6'

@description('Built-in role: Key Vault Secrets Officer (manage secrets).')
var secretsOfficerRoleId = 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7'

resource secretsUserRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for principalId in secretsUserPrincipalIds: {
  name: guid(keyVault.id, principalId, secretsUserRoleId)
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', secretsUserRoleId)
    principalId: principalId
  }
}]

resource secretsOfficerRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for principalId in secretsOfficerPrincipalIds: {
  name: guid(keyVault.id, principalId, secretsOfficerRoleId)
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', secretsOfficerRoleId)
    principalId: principalId
  }
}]

output keyVaultName string = keyVault.name
output keyVaultUri string = keyVault.properties.vaultUri
output keyVaultId string = keyVault.id
