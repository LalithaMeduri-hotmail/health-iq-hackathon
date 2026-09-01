// Health IQ - MVP infrastructure entry point.
// Provisions every Azure resource required to run all six features (Prescription Analyzer, Health Profile,
// Report Comparison, Meal Planner, Doctor-Review PDF/Share, Safety Reviewer) per docs/implementation-plan.md
// and docs/lld/8-low-level-design-cross-cutting-platform.md.
//
// Deploy into an existing resource group:
//   az deployment group create -g <rg-name> -f infra/main.bicep -p infra/main.local.parameters.json
//   az deployment group create -g <rg-name> -f infra/main.bicep -p infra/main.dev.parameters.json
targetScope = 'resourceGroup'

@description('Logical environment name. Drives resource naming/tagging; both "local" and "dev" provision the same Azure resources (local dev connects to the same PaaS services, there is no local emulator for Search/OpenAI/Document Intelligence).')
@allowed([
  'local'
  'dev'
])
param environmentName string = 'local'

@description('Primary Azure region for most resources.')
param location string = resourceGroup().location

@description('Region for the Azure AI Foundry account. Override if gpt-5.4/text-embedding-3-large quota is unavailable in `location`.')
param openAiLocation string = location

@description('Region for the Azure SQL server. Override if `location` rejects new SQL server creation.')
param sqlLocation string = location

@description('Region for Azure AI Search. Override if `location` is out of Search capacity.')
param searchLocation string = location

@description('Short workload prefix used in resource names.')
param namePrefix string = 'hiq'

@description('Entra object id of the developer (or CI identity) that needs direct data-plane access for local development. Leave empty to skip.')
param developerPrincipalId string = ''

@description('Display name (UPN or group name) of the Entra admin for the SQL server.')
param sqlAadAdminLogin string

@description('Object id of the Entra admin principal for the SQL server.')
param sqlAadAdminObjectId string

@description('Principal type of the SQL AAD admin.')
@allowed([
  'User'
  'Group'
  'Application'
])
param sqlAadAdminPrincipalType string = 'User'

@description('Client IP address allowed through the SQL firewall for local development (e.g. your machine\'s public IP). Leave empty to skip.')
param localDevClientIp string = ''

@description('Deploy Container Apps hosting for the backend + frontend. Keep false for local-only development.')
param deployContainerApps bool = false

@description('Azure OpenAI chat deployment throughput capacity (1K TPM units).')
param openAiChatCapacity int = 10

@description('Azure OpenAI embedding deployment throughput capacity (1K TPM units).')
param openAiEmbeddingCapacity int = 30

@description('Name of the Foundry Project created under the Azure AI Foundry account.')
param foundryProjectName string = 'healthiq'

@description('Azure AI Search SKU.')
@allowed([
  'free'
  'basic'
  'standard'
])
param searchSkuName string = 'basic'

@description('Azure SQL database SKU name (Basic, S0, etc).')
param sqlDatabaseSkuName string = 'Basic'

@description('Azure SQL database SKU tier.')
param sqlDatabaseSkuTier string = 'Basic'

var tags = {
  project: 'health-iq'
  environment: environmentName
  'azd-env-name': environmentName
}

// resourceToken keeps generated names globally unique and stable across re-deploys of the same environment.
var resourceToken = toLower(uniqueString(subscription().id, resourceGroup().id, environmentName))

var storageAccountName = take('${namePrefix}st${resourceToken}', 24)
var keyVaultName = take('${namePrefix}-kv-${resourceToken}', 24)
var cosmosAccountName = take('${namePrefix}-cosmos-${resourceToken}', 44)
var sqlServerName = take('${namePrefix}-sql-${resourceToken}', 63)
var searchServiceName = take('${namePrefix}-srch-${resourceToken}', 60)
var docIntelAccountName = take('${namePrefix}-di-${resourceToken}', 64)
var openAiAccountName = take('${namePrefix}-oai-${resourceToken}', 64)
var logAnalyticsName = take('${namePrefix}-log-${resourceToken}', 63)
var appInsightsName = take('${namePrefix}-appi-${resourceToken}', 260)
var containerAppsEnvName = take('${namePrefix}-cae-${resourceToken}', 32)
var backendAppName = take('${namePrefix}-backend-${resourceToken}', 32)
var frontendAppName = take('${namePrefix}-frontend-${resourceToken}', 32)

var developerPrincipalIds = empty(developerPrincipalId) ? [] : [
  developerPrincipalId
]

// ---- Observability ----
module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring'
  params: {
    location: location
    logAnalyticsName: logAnalyticsName
    appInsightsName: appInsightsName
    tags: tags
  }
}

// ---- Secrets / configuration ----
module keyVault 'modules/keyvault.bicep' = {
  name: 'keyvault'
  params: {
    location: location
    keyVaultName: keyVaultName
    tags: tags
    secretsUserPrincipalIds: developerPrincipalIds
    secretsOfficerPrincipalIds: developerPrincipalIds
  }
}

// ---- Optional compute (dev/demo hosting only) ----
module containerApps 'modules/containerapps.bicep' = if (deployContainerApps) {
  name: 'containerapps'
  params: {
    location: location
    environmentResourceName: containerAppsEnvName
    backendAppName: backendAppName
    frontendAppName: frontendAppName
    tags: tags
    logAnalyticsWorkspaceId: monitoring.outputs.logAnalyticsWorkspaceId
    appInsightsConnectionString: monitoring.outputs.appInsightsConnectionString
    keyVaultUri: keyVault.outputs.keyVaultUri
  }
}

var backendPrincipalIds = deployContainerApps ? [
  containerApps.?outputs.?backendPrincipalId ?? ''
] : []
var dataPlanePrincipalIds = concat(developerPrincipalIds, backendPrincipalIds)

// ---- Data services ----
module storage 'modules/storage.bicep' = {
  name: 'storage'
  params: {
    location: location
    storageAccountName: storageAccountName
    tags: tags
    blobDataContributorPrincipalIds: dataPlanePrincipalIds
    blobDelegatorPrincipalIds: dataPlanePrincipalIds
  }
}

module cosmos 'modules/cosmos.bicep' = {
  name: 'cosmos'
  params: {
    location: location
    cosmosAccountName: cosmosAccountName
    tags: tags
    dataContributorPrincipalIds: dataPlanePrincipalIds
  }
}

module sql 'modules/sql.bicep' = {
  name: 'sql'
  params: {
    location: sqlLocation
    sqlServerName: sqlServerName
    tags: tags
    aadAdminLogin: sqlAadAdminLogin
    aadAdminObjectId: sqlAadAdminObjectId
    aadAdminPrincipalType: sqlAadAdminPrincipalType
    localDevClientIp: localDevClientIp
    databaseSkuName: sqlDatabaseSkuName
    databaseSkuTier: sqlDatabaseSkuTier
  }
}

module search 'modules/search.bicep' = {
  name: 'search'
  params: {
    location: searchLocation
    searchServiceName: searchServiceName
    tags: tags
    skuName: searchSkuName
    indexDataContributorPrincipalIds: dataPlanePrincipalIds
    indexDataReaderPrincipalIds: dataPlanePrincipalIds
  }
}

module docIntel 'modules/docintel.bicep' = {
  name: 'docintel'
  params: {
    location: location
    accountName: docIntelAccountName
    tags: tags
    cognitiveServicesUserPrincipalIds: dataPlanePrincipalIds
  }
}

module openAi 'modules/openai.bicep' = {
  name: 'openai'
  params: {
    location: openAiLocation
    accountName: openAiAccountName
    projectName: foundryProjectName
    tags: tags
    openAiUserPrincipalIds: dataPlanePrincipalIds
    chatCapacity: openAiChatCapacity
    embeddingCapacity: openAiEmbeddingCapacity
  }
}

// ---- Centralize configuration in Key Vault so backend `config.py` reads the same way in every environment ----
// The secret name must be a deploy-time constant, so it is built from the local `keyVaultName`
// variable rather than a module output. Bicep infers the dependency on the keyVault module
// automatically because that same variable is passed in as the module's `keyVaultName` param.
resource kvSecretStorageAccountName 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: '${keyVaultName}/AZURE-STORAGE-ACCOUNT-NAME'
  properties: {
    value: storage.outputs.storageAccountName
  }
}

resource kvSecretBlobEndpoint 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: '${keyVaultName}/AZURE-STORAGE-BLOB-ENDPOINT'
  properties: {
    value: storage.outputs.blobEndpoint
  }
}

resource kvSecretCosmosEndpoint 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: '${keyVaultName}/AZURE-COSMOS-ENDPOINT'
  properties: {
    value: cosmos.outputs.cosmosEndpoint
  }
}

resource kvSecretCosmosDatabaseName 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: '${keyVaultName}/AZURE-COSMOS-DATABASE-NAME'
  properties: {
    value: cosmos.outputs.databaseName
  }
}

resource kvSecretSqlServerFqdn 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: '${keyVaultName}/AZURE-SQL-SERVER-FQDN'
  properties: {
    value: sql.outputs.sqlServerFqdn
  }
}

resource kvSecretSqlDatabaseName 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: '${keyVaultName}/AZURE-SQL-DATABASE-NAME'
  properties: {
    value: sql.outputs.sqlDatabaseName
  }
}

resource kvSecretSearchEndpoint 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: '${keyVaultName}/AZURE-SEARCH-ENDPOINT'
  properties: {
    value: search.outputs.searchEndpoint
  }
}

resource kvSecretDocIntelEndpoint 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: '${keyVaultName}/AZURE-DOCINTEL-ENDPOINT'
  properties: {
    value: docIntel.outputs.endpoint
  }
}

resource kvSecretOpenAiEndpoint 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: '${keyVaultName}/AZURE-OPENAI-ENDPOINT'
  properties: {
    value: openAi.outputs.endpoint
  }
}

resource kvSecretOpenAiChatDeployment 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: '${keyVaultName}/AZURE-OPENAI-CHAT-DEPLOYMENT'
  properties: {
    value: openAi.outputs.chatDeploymentName
  }
}

resource kvSecretOpenAiEmbeddingDeployment 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: '${keyVaultName}/AZURE-OPENAI-EMBEDDING-DEPLOYMENT'
  properties: {
    value: openAi.outputs.embeddingDeploymentName
  }
}

resource kvSecretAppInsightsConnectionString 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: '${keyVaultName}/APPLICATIONINSIGHTS-CONNECTION-STRING'
  properties: {
    value: monitoring.outputs.appInsightsConnectionString
  }
}

output resourceGroupName string = resourceGroup().name
output keyVaultName string = keyVault.outputs.keyVaultName
output keyVaultUri string = keyVault.outputs.keyVaultUri
output storageAccountName string = storage.outputs.storageAccountName
output blobEndpoint string = storage.outputs.blobEndpoint
output cosmosAccountName string = cosmos.outputs.cosmosAccountName
output cosmosEndpoint string = cosmos.outputs.cosmosEndpoint
output cosmosDatabaseName string = cosmos.outputs.databaseName
output sqlServerFqdn string = sql.outputs.sqlServerFqdn
output sqlDatabaseName string = sql.outputs.sqlDatabaseName
output searchServiceName string = search.outputs.searchServiceName
output searchEndpoint string = search.outputs.searchEndpoint
output docIntelEndpoint string = docIntel.outputs.endpoint
output openAiEndpoint string = openAi.outputs.endpoint
output openAiChatDeployment string = openAi.outputs.chatDeploymentName
output openAiEmbeddingDeployment string = openAi.outputs.embeddingDeploymentName
output foundryProjectName string = openAi.outputs.projectName
output appInsightsConnectionString string = monitoring.outputs.appInsightsConnectionString
output logAnalyticsWorkspaceName string = monitoring.outputs.logAnalyticsWorkspaceName
output backendFqdn string = deployContainerApps ? (containerApps.?outputs.?backendFqdn ?? '') : ''
output frontendFqdn string = deployContainerApps ? (containerApps.?outputs.?frontendFqdn ?? '') : ''
