@description('Region that permits both the B1ms PostgreSQL SKU and Container Apps Consumption.')
param location string

@description('Name of the dedicated Container Apps environment.')
param environmentName string

@description('Globally unique PostgreSQL flexible server name.')
param databaseServerName string

@description('Trusted bootstrap administrator. The web container uses a separate restricted role.')
param databaseAdmin string

@secure()
@description('PostgreSQL administrator password from private deployment parameters.')
param databaseAdminPassword string

resource network 'Microsoft.Network/virtualNetworks@2024-05-01' = {
  name: '${environmentName}-vnet'
  location: location
  properties: {
    addressSpace: { addressPrefixes: ['10.61.0.0/24'] }
    subnets: [
      {
        name: 'apps'
        properties: {
          addressPrefix: '10.61.0.0/26'
          delegations: [{ name: 'apps', properties: { serviceName: 'Microsoft.App/environments' } }]
        }
      }
      {
        name: 'postgres'
        properties: {
          addressPrefix: '10.61.0.64/27'
          delegations: [
            {
              name: 'postgres'
              properties: { serviceName: 'Microsoft.DBforPostgreSQL/flexibleServers' }
            }
          ]
        }
      }
    ]
  }
}

resource dns 'Microsoft.Network/privateDnsZones@2024-06-01' = {
  name: '${environmentName}.postgres.database.azure.com'
  location: 'global'
}

resource dnsLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  parent: dns
  name: 'olist-network'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: { id: network.id }
  }
}

resource environment 'Microsoft.App/managedEnvironments@2025-01-01' = {
  name: environmentName
  location: location
  properties: {
    appLogsConfiguration: { destination: 'none' }
    vnetConfiguration: {
      infrastructureSubnetId: '${network.id}/subnets/apps'
      internal: false
    }
    workloadProfiles: [{ name: 'Consumption', workloadProfileType: 'Consumption' }]
  }
}

resource database 'Microsoft.DBforPostgreSQL/flexibleServers@2025-08-01' = {
  name: databaseServerName
  location: location
  sku: { name: 'Standard_B1ms', tier: 'Burstable' }
  properties: {
    createMode: 'Create'
    version: '17'
    administratorLogin: databaseAdmin
    administratorLoginPassword: databaseAdminPassword
    storage: {
      type: 'Premium_LRS'
      storageSizeGB: 32
      autoGrow: 'Disabled'
    }
    backup: {
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
    }
    highAvailability: { mode: 'Disabled' }
    network: {
      delegatedSubnetResourceId: '${network.id}/subnets/postgres'
      privateDnsZoneArmResourceId: dns.id
      publicNetworkAccess: 'Disabled'
    }
  }
  dependsOn: [dnsLink]
}

output postgresHostname string = database.properties.fullyQualifiedDomainName
output appEnvironmentName string = environment.name

resource demoDatabase 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2025-08-01' = {
  parent: database
  name: 'olist_demo'
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

output databaseName string = demoDatabase.name
