@description('Existing Container Apps environment in this resource group with a Consumption workload profile.')
param environmentName string

@description('Azure region of the existing Container Apps environment.')
param location string

@description('Dedicated Olist staging app name.')
param appName string

@description('Public OCI image reference pinned to the verified linux/amd64 digest.')
param image string

@description('Exact commit used to build the image.')
@minLength(40)
@maxLength(40)
param sourceCommit string

@description('Single reviewer IPv4 address without a prefix. Ingress permits only this address.')
param reviewerAddress string

@secure()
@description('Restricted runtime PostgreSQL DSN with sslmode=verify-full and a trusted CA.')
param runtimeDatabaseUrl string

resource environment 'Microsoft.App/managedEnvironments@2025-01-01' existing = {
  name: environmentName
}

var hostname = '${appName}.${environment.properties.defaultDomain}'
var port = 8080
var probeHeaders = [{ name: 'Host', value: hostname }]

resource app 'Microsoft.App/containerApps@2025-01-01' = {
  name: appName
  location: location
  tags: {
    purpose: 'olist-portfolio-staging'
  }
  properties: {
    environmentId: environment.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      maxInactiveRevisions: 2
      secrets: [
        { name: 'olist-db-runtime', value: runtimeDatabaseUrl }
      ]
      ingress: {
        external: true
        allowInsecure: false
        targetPort: port
        transport: 'auto'
        ipSecurityRestrictions: [
          {
            name: 'demo-reviewer'
            ipAddressRange: '${reviewerAddress}/32'
            action: 'Allow'
          }
        ]
        traffic: [{ latestRevision: true, weight: 100 }]
      }
    }
    template: {
      containers: [
        {
          name: 'olist'
          image: image
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: [
            { name: 'OLIST_AZURE_HOSTNAME', value: hostname }
            { name: 'OLIST_SOURCE_COMMIT', value: sourceCommit }
            { name: 'OLIST_RUNTIME_DATABASE_URL', secretRef: 'olist-db-runtime' }
          ]
          probes: [
            {
              type: 'Startup'
              tcpSocket: { port: port }
              periodSeconds: 2
              timeoutSeconds: 2
              failureThreshold: 20
            }
            {
              type: 'Liveness'
              httpGet: { path: '/health/live', port: port, httpHeaders: probeHeaders }
              periodSeconds: 15
              timeoutSeconds: 3
            }
            {
              type: 'Readiness'
              httpGet: { path: '/health/ready', port: port, httpHeaders: probeHeaders }
              periodSeconds: 20
              timeoutSeconds: 5
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 1
        rules: [
          {
            name: 'http'
            http: { metadata: { concurrentRequests: '4' } }
          }
        ]
      }
    }
  }
}

output hostname string = app.properties.configuration.ingress.fqdn
