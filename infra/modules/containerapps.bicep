// Optional Azure Container Apps hosting for the FastAPI backend + React SPA (dev/demo environment only).
// Not required for local development; deploy with `deployContainerApps = true` once container images exist.
// The working, verified deployment path is `infra/scripts/deploy-demo.ps1`, which also builds the
// images and grants the backend identity cross-resource-group data-plane RBAC.
@description('Azure region for the resources.')
param location string

@description('Name of the Container Apps managed environment.')
param environmentResourceName string

@description('Name of the backend container app.')
param backendAppName string

@description('Name of the frontend container app.')
param frontendAppName string

@description('Tags applied to all resources in this module.')
param tags object = {}

@description('Log Analytics workspace resource id used by the managed environment.')
param logAnalyticsWorkspaceId string

@description('Application Insights connection string injected into both apps.')
@secure()
param appInsightsConnectionString string

@description('Key Vault URI the backend reads configuration/secrets from.')
param keyVaultUri string

@description('Container image for the backend. Defaults to a placeholder until CI publishes a real image.')
param backendImage string = 'mcr.microsoft.com/k8se/quickstart:latest'

@description('Container image for the frontend. Defaults to a placeholder until CI publishes a real image.')
param frontendImage string = 'mcr.microsoft.com/k8se/quickstart:latest'

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' existing = {
  name: last(split(logAnalyticsWorkspaceId, '/'))
}

resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: environmentResourceName
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

resource backendApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: backendAppName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
      }
      secrets: [
        {
          name: 'appinsights-connection-string'
          value: appInsightsConnectionString
        }
      ]
      activeRevisionsMode: 'Single'
    }
    template: {
      containers: [
        {
          name: 'backend'
          image: backendImage
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              secretRef: 'appinsights-connection-string'
            }
            {
              name: 'AZURE_KEY_VAULT_URI'
              value: keyVaultUri
            }
            {
              name: 'SESSION_COOKIE_SECURE'
              value: 'true'
            }
            {
              // The SPA is served from a different hostname, so a Lax cookie would be dropped on
              // every cross-site API call and sign-in would immediately 401.
              name: 'SESSION_COOKIE_SAMESITE'
              value: 'none'
            }
            {
              name: 'CORS_ALLOWED_ORIGINS'
              value: 'https://${frontendAppName}.${containerAppsEnvironment.properties.defaultDomain}'
            }
          ]
        }
      ]
      // Pinned to a single always-on replica: share links and doctor reviews still live in
      // process memory (`sql_repo._DEMO_*`), so a second replica would not see links minted by
      // the first, and scale-to-zero would discard them.
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
}

resource frontendApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: frontendAppName
  location: location
  tags: tags
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      ingress: {
        external: true
        targetPort: 80
        transport: 'auto'
      }
      activeRevisionsMode: 'Single'
    }
    template: {
      containers: [
        {
          name: 'frontend'
          image: frontendImage
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          // No env here on purpose: Vite inlines `VITE_*` at build time, so the API origin must be
          // passed as a docker build-arg when the image is built, not as a container env var.
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 2
      }
    }
  }
}

output backendPrincipalId string = backendApp.identity.principalId
output backendFqdn string = backendApp.properties.configuration.ingress.fqdn
output frontendFqdn string = frontendApp.properties.configuration.ingress.fqdn
