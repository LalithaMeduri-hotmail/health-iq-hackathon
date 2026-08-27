// Azure AI Document Intelligence (prebuilt-read + prebuilt-layout) for OCR (Implementation Plan M1).
@description('Azure region for the resources.')
param location string

@description('Name of the Document Intelligence (Form Recognizer) account.')
param accountName string

@description('Tags applied to all resources in this module.')
param tags object = {}

@description('SKU for Document Intelligence.')
param skuName string = 'S0'

@description('Principal IDs granted Cognitive Services User (call the OCR APIs).')
param cognitiveServicesUserPrincipalIds array = []

resource docIntelAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: accountName
  location: location
  tags: tags
  kind: 'FormRecognizer'
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
    networkAcls: {
      defaultAction: 'Allow'
    }
  }
}

@description('Built-in role: Cognitive Services User.')
var cognitiveServicesUserRoleId = 'a97b65f3-24c7-4388-baec-2e87135dc908'

resource cognitiveServicesUserAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for principalId in cognitiveServicesUserPrincipalIds: {
  name: guid(docIntelAccount.id, principalId, cognitiveServicesUserRoleId)
  scope: docIntelAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesUserRoleId)
    principalId: principalId
  }
}]

output accountName string = docIntelAccount.name
output endpoint string = docIntelAccount.properties.endpoint
