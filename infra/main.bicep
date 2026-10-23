// TactiX — serverless backend on Azure.
//
// Resource-group-scoped deployment: Log Analytics, a Container Apps managed environment,
// the backend Container App (scale-to-zero capable), and an Azure Database for PostgreSQL
// Flexible Server (Burstable B1ms — the cheapest tier, enough for the demo).
//
// NOTE: this is a starting point. It has not yet been validated against a live subscription;
// run infra/deploy.sh once and iterate. See infra/DEPLOY.md.

@description('Location for all resources.')
param location string = resourceGroup().location

@description('Short prefix for resource names.')
param namePrefix string = 'tactix'

@description('Backend image reference, e.g. ghcr.io/<owner>/tactix-backend:latest or <acr>.azurecr.io/tactix-backend:latest')
param backendImage string

@description('Registry login server. Leave empty for a public image (e.g. a public GHCR package).')
param registryServer string = ''

@description('Registry username. Leave empty for a public image.')
param registryUsername string = ''

@secure()
@description('Registry password. Leave empty for a public image.')
param registryPassword string = ''

@description('PostgreSQL administrator login.')
param postgresAdminUser string = 'tactix'

@secure()
@description('PostgreSQL administrator password.')
param postgresAdminPassword string

@description('PostgreSQL database name.')
param postgresDbName string = 'tactix'

@description('Microsoft Foundry project endpoint (optional; empty runs the backend without live agents).')
param foundryEndpoint string = ''

@description('Microsoft Foundry model deployment name (optional).')
param foundryModel string = ''

@description('Minimum backend replicas. 1 keeps the demo warm (no cold start); 0 is scale-to-zero.')
@minValue(0)
@maxValue(5)
param minReplicas int = 1

var logName = '${namePrefix}-logs'
var envName = '${namePrefix}-env'
var appName = '${namePrefix}-backend'
var postgresServerName = '${namePrefix}-pg-${uniqueString(resourceGroup().id)}'

// A private registry needs credentials; a public image (e.g. a public GHCR package) does not.
var usePrivateRegistry = !empty(registryPassword)

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logName
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: postgresServerName
  location: location
  sku: {
    name: 'Standard_B1ms'
    tier: 'Burstable'
  }
  properties: {
    version: '16'
    administratorLogin: postgresAdminUser
    administratorLoginPassword: postgresAdminPassword
    storage: { storageSizeGB: 32 }
    backup: { backupRetentionDays: 7, geoRedundantBackup: 'Disabled' }
    highAvailability: { mode: 'Disabled' }
  }
}

resource postgresDb 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  parent: postgres
  name: postgresDbName
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

// 0.0.0.0 is Azure's sentinel for "allow Azure services", not the public internet. It lets
// the Container App reach the database. Hackathon-grade; tighten to a VNet for production.
resource pgFirewallAzure 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2024-08-01' = {
  parent: postgres
  name: 'AllowAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: envName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

var databaseUrl = 'postgresql+psycopg://${postgresAdminUser}:${postgresAdminPassword}@${postgres.properties.fullyQualifiedDomainName}:5432/${postgresDbName}?sslmode=require'

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
      }
      registries: usePrivateRegistry ? [
        {
          server: registryServer
          username: registryUsername
          passwordSecretRef: 'registry-password'
        }
      ] : []
      secrets: usePrivateRegistry ? [
        { name: 'registry-password', value: registryPassword }
        { name: 'database-url', value: databaseUrl }
      ] : [
        { name: 'database-url', value: databaseUrl }
      ]
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
            { name: 'TACTIX_ENVIRONMENT', value: 'production' }
            { name: 'TACTIX_DATABASE_URL', secretRef: 'database-url' }
            { name: 'TACTIX_FOUNDRY_ENDPOINT', value: foundryEndpoint }
            { name: 'TACTIX_FOUNDRY_MODEL', value: foundryModel }
            // The container's managed identity authenticates to Foundry (see DEPLOY.md).
            { name: 'TACTIX_FOUNDRY_AUTHENTICATION', value: 'managed_identity' }
          ]
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: 3
      }
    }
  }
}

output backendUrl string = 'https://${app.properties.configuration.ingress.fqdn}'
output postgresHost string = postgres.properties.fullyQualifiedDomainName
output backendPrincipalId string = app.identity.principalId
