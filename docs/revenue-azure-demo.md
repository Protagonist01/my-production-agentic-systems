# Revenue Integrity Azure recording demo

Run the constructed walkthrough on a distinct Container App in the existing Azure staging environment. Use fictional inputs, a separate PostgreSQL database named `revenue_demo_*`, separate least-privilege roles, and separate operator and reviewer passwords. The runtime has no external billing integration. Add the OpenRouter secret only to the model-enabled demo revision. The model evaluation is recorded in [the signed public reference report](revenue-r7-signed-public-records.md).

The [shared operating plan](azure-agent-database-operations.md) names `revenue_demo_recording` on the existing private server. Use [the database template](../deploy/revenue-azure/database.bicep) for that logical database. Restrict the runtime role to eight database connections and verify cross-agent connection denial before serving. The Azure liveness route continues serving while database readiness returns 503 during a database outage.

1. Run the Revenue recording image workflow for the verified main commit. Use the digest from its GitHub Actions summary in the deployment. Verify the Azure app can pull that package before deploying it.
2. Create the dedicated database and runtime login through an authorized database administrator. Use the same private network as the Container Apps environment. Both connections must verify the database hostname. Supply the appropriate CA through the libpq connection configuration. Keep the Olist database, roles and credentials out of this runtime.
3. Run the image once as a trusted bootstrap job with the `bootstrap` argument. Provide `REVENUE_DEMO_ADMIN_DSN`, `REVENUE_DEMO_RUNTIME_ROLE`, `REVENUE_DEMO_OPERATOR_PASSWORD` and `REVENUE_DEMO_REVIEWER_PASSWORD` through job-scoped secrets. Bootstrap refuses existing Revenue schemas. The serving revision receives only its own runtime DSN.
4. Compile and preview [the Azure template](../deploy/revenue-azure/demo.bicep). Use the existing Canada Central environment and the dedicated Revenue app name. The public portfolio setup allows any network to reach the HTTPS sign-in page. Provide `reviewerAddress` only for an IP-restricted session. Supply the runtime DSN as a secure parameter.
5. Verify the HTTPS walkthrough and anonymous invoice-route denial. Sign in separately as operator and reviewer. Ask for a correction to the constructed invoice, approve it with the reviewer, apply it with the operator, then replay the same operation and confirm the same receipt and one ledger change. Keep both passwords off-screen. See the [walkthrough](revenue-walkthrough.md).

The model comparison remains a development evaluation. Customer billing and production release are tracked in [#45](https://github.com/Protagonist01/my-production-agentic-systems/issues/45).

## Bounded model rollout

Run `python -m revenue_azure_demo enable-model` once in a private migration job with
the existing Revenue migration credentials and runtime role. It creates the
insert-only attempt and receipt tables without changing billing records.
Set `REVENUE_DEMO_MODEL_REQUIRED=1` and map `REVENUE_DEMO_OPENROUTER_KEY` from an
Azure secret on the demo app. Leave migration credentials out of the web app.

The signed-in workflow can send the exact registered fictional agreement to
NVIDIA Nemotron through its OpenRouter Free route. Edited documents, arbitrary
questions and ineligible workflows do not reach the provider. PostgreSQL limits
the rollout to 12 attempts across all revisions and replicas, including failed
requests. The workflow checks the model's exact quotations and parsed facts
against registered evidence before accepting an assessment. A timeout, refused
route or incorrect evidence sends the case to review. The operator needs a
verified assessment to request a correction, and a separate reviewer still
approves the correction before it can be applied to the demo ledger.
