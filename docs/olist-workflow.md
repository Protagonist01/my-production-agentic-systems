# Controlled Olist refund workflow

O4 and O5 share one user-authorized delivery. The application reads enrolled O2 views, applies the accepted [O3 policy](olist-policy.md), and commits eligible full refunds to a local Postgres **SIM** ledger. It returns a refund confirmation only after checking the matching ledger and order balance. This is a controlled application mechanism; original Olist currency remains unknown, and no payment provider is connected.

## Install and bootstrap

Run from the repository root with Python 3.12/3.13, the locked development environment, and Docker's Linux engine running:

```powershell
python dev.py setup
uv run --locked --all-packages python -m olist_support.business_cli --root . --trial olist-workflow-demo bootstrap
```

Bootstrap starts this checkout's F4 service and creates an isolated trial database/role if absent. Admin connections create `olist` and `olist_graph` schemas; normal workflow connections use the restricted trial role. Business DDL has an immutable version/checksum; incompatible changes require an explicit migration/new trial, rather than silently changing an existing schema. The official Postgres saver owns checkpoint migrations in its separate schema.

The package's base installation supports sources, policy and business contracts without LangGraph. Install `production-agent-olist-support[workflow]` to use the graph/CLI; the root locked development group includes this extra. Pins are LangGraph 1.2.15, checkpoint-postgres 3.2.0 and LangSmith 0.14.8. The CLI is an operator entrypoint, not an authenticated public API.

## Enroll an explicitly scoped scenario

Keep source data, IDs, confirmations, contexts, grants and results outside every Git checkout. Reuse the independently pinned O2 database; do not reimport unchanged source. A trusted operator chooses a real order and an explicit source-local scenario clock. A confirmation follows `ScenarioConfirmation` in [policy.py](../projects/olist-support/src/olist_support/policy.py): exact tenant/order, availability time, declared SIM unit, confirmed payment and non-delivery, zero previous refund, and evidence reference. It is fictional scenario evidence, never observed refund history. Missing confirmation is allowed but cannot authorize a refund.

```powershell
uv run --locked --all-packages python -m olist_support.business_cli --root . --trial olist-workflow-demo enroll --source-database <external-orders.sqlite> --source-pin <independently-reviewed-file-sha256> --tenant <trusted-tenant> --order <scoped-order> --as-of-source-local 2026-10-19T00:00:00 --confirmation <external-confirmation.json>
```

Enrollment is an admin provisioning operation and refuses overwriting an existing order. O2 conservative visibility still applies; the naive scenario clock does not establish a timezone. Original view data is preserved and hashed. Business refund balance/version start at zero and subsequently belong to Postgres.

## Prepare private inputs and run

Create three external UTF-8 JSON files using the strict contracts, with no extra fields:

| File | Contract and required meaning |
|---|---|
| Request | `WorkflowRequest`: `order_id`, `text`, plus default `schema_version: 1`. Text is at most 8,192 characters and carries no permissions. |
| Grant | `CallerGrant`: trusted `tenant_id`, `actor_id`, explicit `order_ids` array, `capabilities` array containing `read` and, for a refund, `refund`. This is supplied by trusted composition, never derived from request text. |
| Context | Harness `RunContext`: distinct tenant/run/case/trial/business-event IDs; `mode: offline_fake`; aware current UTC clock and future deadline; explicit model budget/seed; code/candidate/lock versions; `versions.policy: olist-canceled-full-refund-sim-v1`; `versions.data_snapshot` equal to the enrolled view's source-manifest digest. |

For an invented unit example, request JSON is `{"schema_version":1,"order_id":"invented-order","text":"Please refund my canceled order."}`; grant JSON is `{"schema_version":1,"tenant_id":"invented-tenant","actor_id":"invented-operator","order_ids":["invented-order"],"capabilities":["read","refund"]}`. These IDs cannot locate real enrolled source records. Use the corresponding trusted identifiers for a private source demonstration.

Construct/validate a context in Python with `RunContext`, `Budget`, and `CandidateVersions` from `agent_harness.contracts`. Use `datetime.now(UTC)` and an explicit future deadline; obtain code revision from the clean checkout and the environment lock from SHA-256 of actual `uv.lock` bytes. Do not reuse the historical clock from the harness fake example as a live execution deadline. The source-local scenario clock and UTC execution deadline have different jobs.

```powershell
uv run --locked --all-packages python -m olist_support.business_cli --root . --trial olist-workflow-demo run --context <external-context.json> --request <external-request.json> --grant <external-grant.json> --intent refund --run-limit-minor 10000 --output <new-external-result.json>
```

`--intent` is an explicit offline operator selection (`refund`, `status`, `reship`, or `review`), not a measured natural-language classifier. Optional `--requested-minor` asks for an exact full amount; an inconsistent amount requires review. Integer hundredths are used throughout: 10,000 is 100.00 SIM. The run limit is explicit, nonnegative and immutable once that tenant/run has committed spending. A limit can be lower than the per-order cap. Existing output paths are refused **before** any workflow action. A failed run may leave a private empty result file; inspect the checkpoint/business state and retry using a new output path.

Stdout reports only outcome, private result path and zero provider calls. The private result contains the verified receipt when refunded. Review/status never carries a refund receipt. Errors redact schema/DB details; inspect trusted private inputs locally. An exception or timeout means the outcome may need recovery, particularly if the transaction already committed. It does not prove rollback.

## Retry and independently verify

Keep the same tenant, business event, request, policy and source digest for recovery, even if the run ID changes. Extend the execution deadline explicitly. A new output path is required. The graph resumes its persisted state; a changed operator intent does not replace a previously checkpointed decision. Rebinding that event to another request/policy/source is rejected. A genuinely new request needs a new business event. Completed model usage, if present, retains its original execution run ID.

The refund operation key derives from the business event, independently of the run ID. An exact duplicate command returns the original receipt/actor/run. A repeated key with changed payload requires review. Concurrent new operations for the same order cannot refund twice: the locked order version and policy's previous-refund check reject the losing action. Concurrent orders sharing one run cannot overspend its locked budget. State, budget and ledger commit together.

Use a trusted admin read for independent acceptance: compare `olist.orders.refunded_minor/version`, the count/sum in `olist.refunds`, and `olist.run_budgets.spent_minor` under the relevant tenant/order/run. Do not use model text or the presence of a receipt identifier as proof. The runtime also rereads the actual ledger/payload and balance before confirming a refund or returning a saved completion.

```powershell
python dev.py check
python dev.py db-check
python dev.py build
python dev.py audit
```

Database acceptance requires real Postgres and includes an owned child process that exits immediately after commit, then recovery through a new persistent saver. Memory-saver unit tests establish routing, not restart durability. The [aggregate source drill](data/olist-workflow-drill-v1.json) reuses three eligible private hybrid O3 groups, exercising refund/status/reship and new-run completion recovery with independent SQL totals. No source rows, IDs or messages are published.

## Limits and lifecycle

Caller grants, connection factories, admin provisioning and checkpoint storage are trusted. The runtime role cannot delete/update refund ledger rows or create schema objects, but it can update order, budget, session and checkpoint tables. This is not a security boundary against malicious Python code or stolen DB credentials; no per-tenant DB RLS/authentication service exists. Schemas/checkpoints are private and unencrypted. Back up/protect the F4 local credentials and database volume accordingly.

The graph is acyclic with an eight-step recursion bound and checks execution deadlines at nodes and before business commit. `GatewayPlanner` accepts only a caller-composed H4 bounded gateway; it creates no transport. Its intent-only schema cannot select scope, change policy or execute tools. The graph disables implicit LangSmith tracing/callback exports even if tracing environment variables are set; application trace projection/integration is later work. No fresh provider or language-quality result is claimed. A crash after an intent call but before its checkpoint can repeat that model call on recovery; business idempotency protects the refund effect, not provider exactly-once execution.

Review is a durable terminal outcome here. O6 supplies reviewer decisions and exact-action approval/resume; O7 supplies authenticated API/UI. Do not mutate checkpoints to approve a review. O8 still needs held-out repeated fresh domain evaluation, independent correctness scoring and release acceptance. A tested SIM mechanism is not a complete product release or independently validated business policy.

Use existing F4 trial list/drop commands in [isolated trials](isolated-trials.md) to remove only the selected owned trial when finished; never delete a shared service/volume to reset one workflow. Re-run bootstrap only against a compatible schema. The source drill removes its own temporary trial and retains aggregate evidence.

[Code walkthrough](code-study-olist-workflow.md) · [Build history](../BUILD_BOOK.md#entry-28--transactional-refunds-and-a-bounded-langgraph-workflow)
