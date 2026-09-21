// Azure Communication Services Email - outbound doctor-review notifications.
// Uses an Azure Managed Domain so mail sends immediately with no DNS/TXT verification. Managed
// domains are rate-limited and carry an azurecomm.net sender, which is fine for the MVP; a custom
// verified domain is the production follow-up.
targetScope = 'resourceGroup'

@description('Name of the Email Communication Service resource.')
param emailServiceName string

@description('Name of the Communication Services resource that sends the mail.')
param communicationServiceName string

@description('Where message content and logs are stored at rest. Not a deployment region.')
@allowed([
  'Africa'
  'Asia Pacific'
  'Australia'
  'Brazil'
  'Canada'
  'Europe'
  'France'
  'Germany'
  'India'
  'Japan'
  'Korea'
  'Norway'
  'Switzerland'
  'UAE'
  'UK'
  'United States'
])
param dataLocation string = 'United States'

@description('Entra object ids granted permission to send mail through this resource.')
param senderPrincipalIds array = []

@description('Mailbox part of the sender address. Stays fixed so the From address never changes.')
param senderUsernameValue string = 'DoNotReply'

@description('Friendly name the doctor sees in their inbox.')
param senderDisplayName string = 'Health IQ'

param tags object = {}

// Communication resources are global; only `dataLocation` decides where content rests.
resource emailService 'Microsoft.Communication/emailServices@2023-04-01' = {
  name: emailServiceName
  location: 'global'
  tags: tags
  properties: {
    dataLocation: dataLocation
  }
}

resource managedDomain 'Microsoft.Communication/emailServices/domains@2023-04-01' = {
  parent: emailService
  name: 'AzureManagedDomain'
  location: 'global'
  tags: tags
  properties: {
    domainManagement: 'AzureManaged'
    // Open/click tracking would put patient-identifiable URLs through a redirector.
    userEngagementTracking: 'Disabled'
  }
}

// The display name a doctor sees in their inbox. Without this the From header falls back to the
// raw mailbox ("DoNotReply"), which reads like spam next to a medical request.
resource senderUsername 'Microsoft.Communication/emailServices/domains/senderUsernames@2023-04-01' = {
  parent: managedDomain
  name: senderUsernameValue
  properties: {
    username: senderUsernameValue
    displayName: senderDisplayName
  }
}

resource communicationService 'Microsoft.Communication/communicationServices@2023-04-01' = {
  name: communicationServiceName
  location: 'global'
  tags: tags
  properties: {
    dataLocation: dataLocation
    linkedDomains: [
      managedDomain.id
    ]
  }
}

// ACS Email has no dedicated data-plane role yet; Contributor on the resource is what grants
// Entra-authenticated senders access, so the backend never needs a connection string.
var contributorRoleDefinitionId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'b24988ac-6180-42a0-ab88-20f7382dd24c'
)

resource senderRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for principalId in senderPrincipalIds: {
    name: guid(communicationService.id, principalId, contributorRoleDefinitionId)
    scope: communicationService
    properties: {
      roleDefinitionId: contributorRoleDefinitionId
      principalId: principalId
    }
  }
]

output communicationServiceName string = communicationService.name
output communicationEndpoint string = 'https://${communicationService.name}.communication.azure.com/'
output senderDomain string = managedDomain.properties.mailFromSenderDomain
output senderAddress string = '${senderUsernameValue}@${managedDomain.properties.mailFromSenderDomain}'
output senderDisplayName string = senderDisplayName
