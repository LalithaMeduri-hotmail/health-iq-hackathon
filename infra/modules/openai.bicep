// Azure AI Foundry account (gpt-4o reasoning + text-embedding-3-large vectors) for agents + RAG
// (Implementation Plan M3/M4). Provisioned as kind=AIServices with a Foundry Project so the
// account also exposes the full Foundry model catalog/portal; agents still call it through the
// OpenAI-compatible endpoint via AzureOpenAIChatClient (docs/.github/instructions/agents.instructions.md).
@description('Azure region for the resources. Must support the requested model deployments.')
param location string

@description('Name of the Azure AI Foundry account.')
param accountName string

@description('Name of the Foundry project created under the account.')
param projectName string = 'healthiq'

@description('Display name of the Foundry project.')
param projectDisplayName string = 'Health IQ'

@description('Tags applied to all resources in this module.')
param tags object = {}

@description('SKU for the Azure AI Foundry account.')
param skuName string = 'S0'

@description('Principal IDs granted Cognitive Services OpenAI User (chat + embeddings calls).')
param openAiUserPrincipalIds array = []

@description('Chat model deployment name used by agents.')
param chatDeploymentName string = 'gpt-4o'

@description('Chat model version.')
param chatModelVersion string = '2024-08-06'

@description('Chat deployment throughput capacity (in 1K TPM units).')
param chatCapacity int = 10

@description('Embedding model deployment name used by RAG ingestion/retrieval.')
param embeddingDeploymentName string = 'text-embedding-3-large'

@description('Embedding model version.')
param embeddingModelVersion string = '1'

@description('Embedding deployment throughput capacity (in 1K TPM units).')
param embeddingCapacity int = 30

@description('Deployment SKU (GlobalStandard, Standard, ProvisionedManaged).')
param deploymentSkuName string = 'GlobalStandard'

resource openAiAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: accountName
  location: location
  tags: tags
  kind: 'AIServices'
  identity: {
    type: 'SystemAssigned'
  }
  sku: {
    name: skuName
  }
  properties: {
    customSubDomainName: accountName
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: false // local dev fallback to key auth; runtime identity uses DefaultAzureCredential
    allowProjectManagement: true // enables the Foundry Project below (model catalog, portal, evaluations)
    networkAcls: {
      defaultAction: 'Allow'
    }
  }
}

resource foundryProject 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: openAiAccount
  name: projectName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    displayName: projectDisplayName
    description: 'Health IQ hackathon MVP - agents, RAG grounding, and model deployments.'
  }
}

resource chatDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: openAiAccount
  name: chatDeploymentName
  sku: {
    name: deploymentSkuName
    capacity: chatCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4o'
      version: chatModelVersion
    }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
  }
}

resource embeddingDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: openAiAccount
  name: embeddingDeploymentName
  sku: {
    name: deploymentSkuName
    capacity: embeddingCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'text-embedding-3-large'
      version: embeddingModelVersion
    }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
  }
  dependsOn: [
    chatDeployment // Cognitive Services accounts only allow one deployment operation at a time
  ]
}

@description('Built-in role: Cognitive Services OpenAI User.')
var openAiUserRoleId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'

resource openAiUserAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for principalId in openAiUserPrincipalIds: {
  name: guid(openAiAccount.id, principalId, openAiUserRoleId)
  scope: openAiAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', openAiUserRoleId)
    principalId: principalId
  }
}]

output accountName string = openAiAccount.name
output endpoint string = openAiAccount.properties.endpoint
output chatDeploymentName string = chatDeployment.name
output embeddingDeploymentName string = embeddingDeployment.name
output projectName string = foundryProject.name
output projectId string = foundryProject.id
