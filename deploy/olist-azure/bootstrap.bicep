@description('Existing Container Apps environment from the foundation deployment.')
param environmentName string

@description('Azure region of the existing Container Apps environment.')
param location string

@description('Public OCI image pinned to the verified linux/amd64 digest.')
param image string

@secure()
param adminDatabaseUrl string

@secure()
param runtimeDatabaseUrl string

@secure()
@description('JSON object holding the separate operator, reviewer and customer passwords.')
param demoAccounts string

resource environment 'Microsoft.App/managedEnvironments@2025-01-01' existing = {
  name: environmentName
}

resource job 'Microsoft.App/jobs@2025-01-01' = {
  name: '${environmentName}-bootstrap'
  location: location
  properties: {
    environmentId: environment.id
    workloadProfileName: 'Consumption'
    configuration: {
      triggerType: 'Manual'
      replicaRetryLimit: 0
      replicaTimeout: 180
      manualTriggerConfig: {
        replicaCompletionCount: 1
        parallelism: 1
      }
      secrets: [
        { name: 'olist-admin-db', value: adminDatabaseUrl }
        { name: 'olist-runtime-db', value: runtimeDatabaseUrl }
        { name: 'olist-demo-accounts', value: demoAccounts }
      ]
    }
    template: {
      containers: [
        {
          name: 'provision'
          image: image
          command: ['/app/.venv/bin/python', '-m', 'olist_azure_bootstrap']
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: [
            { name: 'OLIST_ADMIN_DATABASE_URL', secretRef: 'olist-admin-db' }
            { name: 'OLIST_RUNTIME_DATABASE_URL', secretRef: 'olist-runtime-db' }
            { name: 'OLIST_DEMO_ACCOUNTS', secretRef: 'olist-demo-accounts' }
          ]
        }
      ]
    }
  }
}

output jobName string = job.name
