# Olist on Azure

Azure supersedes the earlier Render hosting plan. The first deployment is an
IP-restricted staging workspace. It uses fictional orders, SIM funds, provisioned
accounts and the console's operator-selected request type. It serves both the
support desk at `/` and customer confirmation at `/customer`. This staging
image makes zero provider calls.

## Verify the subscription before creating resources

In Azure Cost Management, verify the subscription offer, spending limit, expiry
and region. Check the exact PostgreSQL Flexible Server offer, including compute,
storage and backup allowances. Check networking, image storage, observability
and the second database server used during the recovery exercise separately.
Container Apps Consumption grants apply per subscription. Budget alerts report
spend and can arrive after usage. Keep the existing trial spending protection.
[Consumption charges](https://learn.microsoft.com/azure/container-apps/billing) ·
[Free account expiry](https://learn.microsoft.com/azure/cost-management-billing/manage/subscription-disabled) ·
[Budget alerts](https://learn.microsoft.com/azure/cost-management-billing/costs/tutorial-acm-create-budgets).

The staging template requires a Consumption workload profile environment in
the target resource group. Use `deploy/olist-azure/foundation.bicep` to preview
a dedicated network, private DNS, environment and PostgreSQL Flexible Server.
Pass the same region and environment name to the staging deployment. The
database has its own delegated subnet and public access disabled. The environment
uses a separate delegated subnet and exposes only the app's restricted HTTPS
ingress. Private DNS and the public ingress infrastructure can have costs apart
from the database and Container Apps free allowances. Verify the actual offer,
regional capacity and charge estimate before deployment.
[Container Apps VNet configuration](https://learn.microsoft.com/azure/container-apps/vnet-custom).

The database template requests PostgreSQL 17, Burstable `Standard_B1ms`, 32 GiB
of Premium SSD, seven days of local backup retention and an empty `olist_demo`
database. Azure's portal may select Premium SSD v2 and General Purpose by
default. That storage type prevents selecting Burstable in the setup form.
The Azure trial permitted Canada Central in the form but refused West Europe.
The exact B1ms SKU and Container Apps region still need validation on that
subscription. Keep high availability, geo-redundant backups and storage
autogrowth disabled for this single development instance.

Compile and preview the foundation from the selected resource group before
app setup. The private parameter file supplies `location`, `environmentName`,
`databaseServerName`, `databaseAdmin` and `databaseAdminPassword`.

```powershell
bicep build deploy/olist-azure/foundation.bicep --stdout
az deployment group what-if --resource-group <staging-resource-group> --template-file deploy/olist-azure/foundation.bicep --parameters '@<private-foundation-parameters-file>'
```

From the plan, verify the two subnet delegations, private DNS link, exact
database SKU and storage, and the Consumption profile. The plan previews
resource changes. Use Azure Cost Management to estimate billable meters.

## Prepare the staging application

Build from the selected commit. Run the packaged smoke check before publishing
the image to the chosen registry. The Bicep template accepts an anonymously
pullable image so the stage requires no ACR or registry secret. Use its immutable
`@sha256:…` reference after publication.

```powershell
docker build --platform linux/amd64 -f containers/olist-azure/Dockerfile -t olist-azure:staging .
docker run --rm --network none olist-azure:staging
```

The second command should exit 1 with the generic configuration refusal. The
container runs as UID 65532 with the locked Olist web dependencies. Its build
context excludes local secrets and artifacts.

Deploy `bootstrap.bicep` against the foundation's empty `olist_demo` database.
The manual job uses the same image with `olist_azure_bootstrap` as its entrypoint.
It accepts two private DSNs for the same database. One identifies the schema
administrator and the other names the new login `olist_runtime`. Use five
distinct passwords for the administrator, runtime login, operator, reviewer
and customer. The last three go into the private `demoAccounts` JSON parameter
under `operator`, `reviewer` and `customer`.

The job has zero automatic retries and no ingress. Its code holds a PostgreSQL
advisory lock during initialization. It creates the restricted runtime role,
calls the existing schema bootstrap and enrolls one 37.25 SIM order with three
scoped accounts. It exits successfully only after the runtime DSN passes
preflight. A repeat or a partially initialized database refuses bootstrap.
Inspect any failed execution before a new attempt. The job's successful
completion can be checked through its execution status without log export.
Remove the temporary job and its admin secret after successful initialization,
keeping the runtime DSN only in the web app. The administrator secret remains
under operator custody for intentional administration.

```powershell
bicep build deploy/olist-azure/bootstrap.bicep --stdout
az deployment group what-if --resource-group <staging-resource-group> --template-file deploy/olist-azure/bootstrap.bicep --parameters '@<private-bootstrap-parameters-file>'
az deployment group create --resource-group <staging-resource-group> --template-file deploy/olist-azure/bootstrap.bicep --parameters '@<private-bootstrap-parameters-file>'
az containerapp job start --resource-group <staging-resource-group> --name <environment-name>-bootstrap
az containerapp job execution list --resource-group <staging-resource-group> --name <environment-name>-bootstrap --output table
```

The accounts are `demo-operator`, `demo-reviewer` and `demo-customer`. Enter a
37.25 SIM full-refund request for `SIM-ORD-1042` as the operator and request
review. Use the separate reviewer and customer accounts to finish the flow.

Supply both DSNs with `sslmode=verify-full`, the Azure PostgreSQL DNS name
and `sslrootcert=/etc/ssl/certs/ca-certificates.crt`, the system trust bundle
in the image. Verify the actual Azure certificate chain before starting the
job. Keep the secure parameter in a private,
untracked deployment parameter file or an approved secret store. Bicep wires one
Container Apps secret to the runtime. It sends health probes with the exact app
Host header because the console rejects unexpected hosts. Ingress requires TLS
and allows one operator IPv4 address. The app scales between zero and one replica.
[Probe configuration](https://learn.microsoft.com/azure/container-apps/health-probes).

Compile the template and run Azure Resource Manager what-if before creating the
revision. The parameter file must provide `environmentName`, `location`,
`appName`, `image`, `sourceCommit`, `reviewerAddress` without a CIDR suffix,
and the secure `runtimeDatabaseUrl`. Check that the plan creates only the
dedicated staging app with the chosen image, network and limits.

```powershell
bicep build deploy/olist-azure/staging.bicep --stdout
az deployment group what-if --resource-group <staging-resource-group> --template-file deploy/olist-azure/staging.bicep --parameters '@<private-parameters-file>'
az deployment group create --resource-group <staging-resource-group> --template-file deploy/olist-azure/staging.bicep --parameters '@<private-parameters-file>'
```

Verify the Azure hostname, HTTPS, cold startup and database readiness. Walk the
complete flow with three separate accounts. Save the one matching receipt,
restart the app and check the same receipt and one ledger row. Check acceptance
from the selected IP and refusal from outside it before increasing access.

## Recovery and the live model

Exercise Azure PostgreSQL point-in-time restore into a new server with the
approved network and resource allowance. Verify restored cases, authority,
sessions and receipts and record recovery time and the last recovered commit.
Keep an encrypted, portable copy outside the app's failure domain. Azure's managed
snapshots restore within its service. The existing application binary archive
requires the same database build and schema. Test a portable logical restore
separately if the database build differs. [Azure backup and recovery](https://learn.microsoft.com/azure/postgresql/backup-restore/concepts-backup-restore).

The live candidate still needs a completed evaluation and a hosted provider
composition with persistent call accounting. Verify rate and concurrency limits,
visitor isolation, budget exhaustion, restart and fail-closed behavior before
turning on Gemini for visitors. The local SQLite study allowance governs the
frozen study only. Cloud release also needs an actual clean-target recovery drill.
