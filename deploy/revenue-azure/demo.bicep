@description('Existing Container Apps environment name in this resource group.')
param environmentName string
param location string
param appName string
@description('Revenue image pinned by linux/amd64 digest.')
param image string
@description('Single recording workstation IPv4 address without a prefix.')
param reviewerAddress string
@secure()
@description('Restricted runtime PostgreSQL DSN with sslmode=verify-full.')
param runtimeDsn string

resource environment 'Microsoft.App/managedEnvironments@2025-01-01' existing = {
  name: environmentName
}

var hostname = '${appName}.${environment.properties.defaultDomain}'

resource app 'Microsoft.App/containerApps@2025-01-01' = {
  name: appName
  location: location
  tags: {
    purpose: 'revenue-sim-recording'
  }
  properties: {
    environmentId: environment.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      maxInactiveRevisions: 2
      secrets: [{ name: 'revenue-runtime-dsn', value: runtimeDsn }]
      ingress: {
        external: true
        allowInsecure: false
        targetPort: 8080
        transport: 'auto'
        ipSecurityRestrictions: [
          {
            name: 'recording-workstation'
            ipAddressRange: '${reviewerAddress}/32'
            action: 'Allow'
          }
        ]
      }
    }
    template: {
      containers: [
        {
          name: 'revenue'
          image: image
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: [
            { name: 'REVENUE_DEMO_HOSTNAME', value: hostname }
            { name: 'REVENUE_DEMO_RUNTIME_DSN', secretRef: 'revenue-runtime-dsn' }
          ]
          probes: [
            {
              type: 'Readiness'
              httpGet: {
                path: '/walkthrough'
                port: 8080
                httpHeaders: [{ name: 'Host', value: hostname }]
              }
              periodSeconds: 10
              timeoutSeconds: 3
            }
          ]
        }
      ]
      scale: { minReplicas: 0, maxReplicas: 1 }
    }
  }
}

output walkthrough string = 'https://${app.properties.configuration.ingress.fqdn}/walkthrough'
