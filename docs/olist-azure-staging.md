# Olist on Azure

Azure supersedes the earlier Render hosting plan. The first deployment is an
staging workspace. It uses fictional orders, SIM funds, provisioned
accounts and the console's operator-selected request type. It serves both the
support desk at `/` and customer confirmation at `/customer`. The default runtime uses the operator-selected request type. The model-backed runtime has separate activation steps below.

## Verify the subscription before creating resources

In Azure Cost Management, verify the subscription offer, spending limit, expiry
and region. Check the exact PostgreSQL Flexible Server offer, including compute,
storage and backup allowances. Check networking, image storage, observability
and the second database server used during the recovery exercise separately.
Container Apps Consumption grants apply per subscription. Budget alerts report
spend and can arrive after usage. Keep the existing trial spending protection.
[Consumption charges](https://learn.microsoft.com/azure/container-apps/billing) Â·
[Free account expiry](https://learn.microsoft.com/azure/cost-management-billing/manage/subscription-disabled) Â·
[Budget alerts](https://learn.microsoft.com/azure/cost-management-billing/costs/tutorial-acm-create-budgets).

The staging template requires a Consumption workload profile environment in
the target resource group. Use `deploy/olist-azure/foundation.bicep` to preview
a dedicated network, private DNS, environment and PostgreSQL Flexible Server.
Pass the same region and environment name to the staging deployment. The
database has its own delegated subnet and public access disabled. Omit the
Container Apps log export configuration for this sandbox. Azure preflight
rejects the literal destination 'none' for the pinned environment API.
The environment
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
`@sha256:â€¦` reference after publication.

```powershell
docker build --platform linux/amd64 -f containers/olist-azure/Dockerfile -t olist-azure:staging .
docker run --rm --network none olist-azure:staging
```

The second command should exit 1 with the generic configuration refusal. The
container runs as UID 65532 with the locked Olist web dependencies. Its build
context excludes local secrets and artifacts.

### Publish the reviewed staging image

Run **Publish Olist staging image** in GitHub Actions on `main`. Set
`source_sha` to the exact merged commit selected for Azure. The workflow
checks its successful main CI run, builds the Linux amd64 image from that
commit, verifies both Python entrypoints under the image's non-root user
and checks that startup refuses missing private configuration. The job
summary records the source commit and immutable registry digest.

The first GitHub Container Registry upload creates a private package.
Once the owner approves public image distribution, make only this
dedicated package public and verify an anonymous pull of the exact digest.
Use that digest for both the bootstrap job and the staging app.
[GitHub Container Registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).


### Enable continuous delivery to the existing staging app

Create the GitHub environment `olist-azure-staging` and restrict deployments
to `main`. Configure a dedicated Azure identity with an OpenID Connect
federated credential for the subject
`repo:Protagonist01/my-production-agentic-systems:environment:olist-azure-staging`
and audience `api://AzureADTokenExchange`. Use the issuer
`https://token.actions.githubusercontent.com`. Set `AZURE_CLIENT_ID`,
`AZURE_TENANT_ID` and `AZURE_SUBSCRIPTION_ID` as environment variables in
GitHub's environment settings. Never store the PostgreSQL DSN there.

Scope the Azure role assignment to `olist-portfolio-stage`. Start with a
custom role allowing `Microsoft.App/containerApps/read`,
`Microsoft.App/containerApps/write` and `Microsoft.App/containerApps/revisions/read`
and verify the CLI with that scope. The identity can alter the app revision, so
protect the main branch and the deployment workflow. See
[Microsoft's GitHub OIDC setup](https://learn.microsoft.com/azure/developer/github/connect-from-azure-openid-connect).

After the identity is ready, set the repository Actions variable
`OLIST_AZURE_AUTO_DEPLOY` to `true`. The next successful Foundation CI run for
a push to `main` builds the image and deploys the digest to the existing app.
The workflow checks that the tested source is still the tip of `main` before
writing the app. Its summary records the previous ready revision and the
outcome. Confirm `/health/ready` and smoke-test from the allowed IP, since
the GitHub runner verifies readiness through Azure's control plane.

To pause continuous delivery, clear `OLIST_AZURE_AUTO_DEPLOY` and check for
active runs before making any manual revision change. To roll back application
code, copy the last known good revision in Azure. Restore or migrate the
database separately when a schema change prevents the older image from running.

### Initialize PostgreSQL and demo accounts

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

Use the `jobName` deployment output. For longer environment names, the template
derives a short, deterministic name from the environment resource ID to fit the
Container Apps job name limit.

```powershell
bicep build deploy/olist-azure/bootstrap.bicep --stdout
az deployment group what-if --resource-group <staging-resource-group> --template-file deploy/olist-azure/bootstrap.bicep --parameters '@<private-bootstrap-parameters-file>'
$jobName = az deployment group create --resource-group <staging-resource-group> --template-file deploy/olist-azure/bootstrap.bicep --parameters '@<private-bootstrap-parameters-file>' --query properties.outputs.jobName.value --output tsv
az containerapp job start --resource-group <staging-resource-group> --name $jobName
az containerapp job execution list --resource-group <staging-resource-group> --name $jobName --output table
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

The Gemini evaluation allowance governs the frozen study. The first hosted
Nemotron demonstration uses a separate PostgreSQL ledger. A clean-target
Azure recovery drill is still required for hosted recovery evidence.

### Run the first model-backed portfolio demo

Nemotron runs when Azure supplies the dedicated `OLIST_OPENROUTER_API_KEY`
secret and the runtime login can read the existing PostgreSQL attempt ledger.
Run the bootstrap image with the existing administrator DSN and
`python -m olist_azure_bootstrap --install-model-ledger` first. The installer
creates the budget boundary separately from order and account provisioning.
Reapplying it preserves existing attempt records.

The operator selects a built-in fictional request. The server rejects other
text before the case starts. The planner reserves a case-specific slot before
dispatch, pins the NVIDIA free route, and verifies the response route and zero
reported cost. No more than 30 reservations can exist. An interrupted call
still occupies its slot. A deployment restart leaves the ledger in PostgreSQL.
The model proposes meaning. The existing policy, actor approval and customer
confirmation continue to govern refunds.

In Azure, add the new key through the portal as a Container Apps secret and
reference it from the environment variable of the same name. Keep the Azure
ingress choice, private database, existing runtime secret and exact image digest.
After activation, record a built-in case's model proposal and, separately,
its receipt or review outcome. Check the attempt count readback without
printing the key, request text or provider response.
