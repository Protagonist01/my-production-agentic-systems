@description('Existing private PostgreSQL Flexible Server in this resource group.')
param databaseServerName string

resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2025-08-01' existing = {
  name: databaseServerName
}

resource database 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2025-08-01' = {
  parent: postgres
  name: 'revenue_demo_recording'
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

output databaseName string = database.name
