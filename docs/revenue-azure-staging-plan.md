# Revenue Integrity on Azure

Use Azure Container Apps for Revenue, as for Olist. Keep the shared harness in the build and reuse the Olist deployment workflow as a template. Give Revenue its own container app, managed identity, database role and data store. Shared tooling lets each agent use the same deployment and monitoring practices. Separate identities and scoped roles let each app reach only its own resources. [Azure Container Apps environments](https://learn.microsoft.com/en-us/azure/container-apps/environment) · [Managed identities](https://learn.microsoft.com/en-us/azure/container-apps/managed-identity)

## First deployment

1. Package the Revenue walkthrough as a separate immutable image. Bind the trusted host and HTTPS origin in the Azure composition. Preserve the loopback CLI for local use. Require authenticated ingress and per-role access to the app. Validate configuration, permissions and schema at startup. Readiness should fail when the database cannot serve the walkthrough.
2. Stage with the existing fictional invoices and agreements. The existing SIM PostgreSQL journey gives a starting checkpoint. Verify it over Azure HTTPS with separate operator and reviewer accounts. Check that the operator cannot approve their own proposal, that duplicate delivery returns the same receipt and that a new revision preserves the ledger.
3. Restore the staging backup into an isolated target and reconcile the proposal, approval and receipt. Rehearse traffic rollback to the previous image digest. Record observed recovery time, the restore point and the checks performed before resuming traffic.

The existing Azure infrastructure and workflow are Olist-specific. Inspect the subscription, target resource group, network and actual cost before applying a Revenue deployment. Keep raw agreement text out of deployment logs and telemetry. [Olist Azure staging](olist-azure-staging.md) · [Revenue walkthrough](revenue-walkthrough.md)

## Evidence for the billing rollout

Use the four verified public schedules to test explicit rates, eligibility and deferral. Use the 29 fictional billing worlds for arithmetic and the existing approval tests for workflow regression. The pinned CUAD census identifies 44 holdout families with related published clause labels. Those labels support a clause retrieval test. The audited stores contain zero independently supported answers for customer-specific billing amounts. [Reference inventory](revenue-r7-reference-readiness.md) · [Pilot results](revenue-public-schedule-pilot.md)

Start with private staging and complete recovery verification there. Before enabling analysis of real customer agreements, freeze the final guarded candidate and establish billing references through controlling order terms or independently checked annotations. Begin the production rollout with read-only analysis and route unresolved terms to review. Verify the agreed quality and timing limits on fresh representative packets before enabling any billing effects. [Revenue release](https://github.com/Protagonist01/my-production-agentic-systems/issues/45)
