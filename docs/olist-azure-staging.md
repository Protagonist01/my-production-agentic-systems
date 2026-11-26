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

The template requires an existing Consumption workload profile environment in
the target resource group. Place it on a network with a private route and DNS
resolution to the dedicated PostgreSQL server. Azure's public database firewall
option allowing all Azure services would admit other subscriptions, so keep that
option off. Use the environment's actual Azure region for the app parameter.
[Container Apps VNet configuration](https://learn.microsoft.com/azure/container-apps/vnet-custom).

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

From a trusted admin connection inside the selected network, create an empty
database and a restricted login role. Use `olist_demo_host.bootstrap` to add the
four application schemas. Enroll only a fictional order and scope one operator,
reviewer and customer to it via `console_auth.provision`. For one sample input,
use `olist_demo_fixtures.fixture` with the authored refund case
`olist-demo-refund-1`. Load each password privately. Keep the schema-owner
connection outside the web app. Run `olist_demo_host.preflight` with the runtime
connection to verify schema access and rejection of elevated roles.

Supply the runtime DSN with `sslmode=verify-full`, the Azure PostgreSQL DNS name
and a trusted certificate bundle. Keep the secure parameter in a private,
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
