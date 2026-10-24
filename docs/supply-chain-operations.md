# Supply-chain simulator and controlled SIM operations

S2 #53, S3 #54 and S4 #55 are implemented together on `codex/s2-s3-s4-supply-chain`, based on user-merged #89 main `77b98df`. This is offline mechanism work. S5 operations UI/notification delivery and S6 fresh release evaluation remain later issues. No shipping provider, paid model or real spend is contacted.

## Constructed policy approved for this batch

All amounts are integer minor units of **SIM**, with 100 units per SIM. Each action is capped at 100.00; one incident/run has a 500.00 ceiling that survives new workflow run IDs. Costs above 25.00 require a different reviewer. Approvals and confirmations last at most 30 minutes; earlier source expiry shortens approval validity. Missing, conflicting, future or expired observations block paid interventions. Two stale proposal supersessions are allowed across an incident; this conservative shared limit survives process restarts.

The bounded server catalog is wait (0.00), expedite (20.00), reroute (80.00). Estimated delay reductions are respectively zero, three and ten hours. These prices, delay estimates and effects are invented test assumptions, not DataCo/NWS facts or carrier promises. A capacity-zero shipment has only the wait option. Approval never overrides availability, freshness or caps.

## Independent worlds and baselines

`simulator.suite()` creates 20 portfolios: eight development worlds (four families, seeds 11/23) and twelve holdout worlds (six families, seeds 97/193). Expired-alert and correlated-delay families are absent from development. Holdout uses four shipments instead of three and a nonlinear congestion/changed-efficacy formula, including a reroute downside. Seed hashing also includes split/family namespaces. These are explicit synthetic stress slices, not a representative shipment distribution or calibrated causal model.

Each scenario holds `observed` public shipments and evaluator-only `hidden` realized delays. `agent_input()` serializes only shipments; it omits split, seeds, templates and targets. Policies receive that public tuple, never a Scenario. This is a validated API boundary within a trusted Python process, not an adversarial sandbox against introspection.

The do-nothing policy waits; rules choose interventions from declared delay thresholds and available budget; the exact multiple-choice knapsack minimizes **estimated** intervention plus delay cost. The evaluator independently prices the selected actions against hidden outcomes. Changing hidden targets leaves planner input and choices unchanged but changes scores. The estimate solver is not an oracle for realized cost.

Every row records scenario ID, split, family, seed, template, outcome model, denominators, intervention cost, delay cost, unsafe actions and unresolved decisions. Total realized simulated cost is their monetary sum. Differences are solver cost minus do-nothing cost; normalized difference divides by do-nothing cost and is null at zero. Negative differences are simulated improvements only. Delay-cost sensitivity is explicit (50%, 100%, 200% in the published mechanism report); no actual freight savings, production accuracy or model quality is claimed.

## Source boundary

S1's pinned reader remains the source of DataCo observations and independent current NWS alerts. `source_adapter.hybrid_observation` accepts only a `ShipmentFact`, an explicit clock/age allowance, opaque operational IDs and separately supplied invented delay/cost assumptions. It rejects observations before capture or after the declared allowance. It retains the source-key reference and hybrid label, and drops historical order timestamps whose timezone/online availability is unverified.

It does not read ShipmentTarget, infer intervention labels from delivery outcomes, map contemporary US weather to historical international shipments or claim carrier integration. Use S1's full source-to-store verification before trusting a source store; constructing a ShipmentFact alone does not prove its origin. The published simulator report is entirely invented and contains no private source rows.

## Durable state and authorization

Postgres owns incident budget/version/replan count, shipment versions, proposals, immutable effect receipts and first terminal confirmation. LangGraph owns a bounded assessment invocation. Inngest owns fanout/wakeup/wait scheduling. Neither framework duplicates the SQL approval state.

Trusted service code composes a Grant with tenant, actor, explicit incident IDs, shipment IDs and capabilities. These objects are not authentication tokens and must never be accepted from HTTP JSON. S5 must bind them to authenticated server identities. The runtime database role is a trusted service identity shared across application scopes; there is no claim of per-tenant SQL row-level security or resistance to a compromised service credential.

All mutations lock budget first and shipment second. A command binds incident/shipment identity, selected action and both expected versions. The server computes the option and a fingerprint including command, price and expiry. Review binds that fingerprint and a separate reviewer; changed versions demand a new proposal and new approval. Rejecting or expiring a proposal is terminal for that operation. A trusted external fact refresh must update document and version together; there is no public administrative refresh endpoint in this batch.

The permanent effect key hashes tenant, incident and shipment. Command acceptance atomically debits budget, advances versions and inserts one receipt. Same-command retries return that receipt; changing command/version/action under a committed key fails. New workflow run IDs do not reset incident limits or create new effects. A fault before commit rolls back all state; an exit after commit leaves the receipt recoverable.

`awaiting_confirmation` means only that the simulated command committed. A scoped confirmer must bind the receipt fingerprint. Confirmation failure/timeout preserves the debit and receipt; it never rolls back business actions or reports delivery success. First terminal confirmation wins, and late/opposite/duplicate signals cannot rewrite it. There is no real carrier confirmation adapter; production needs authenticated provider events and reconciliation.

## Orchestration and limits

`SupplyWorkflow.run` assesses at most twelve scoped shipments, excludes committed keys from replanning, then reads current budget/versions for each action. Current pending proposals remain pending; canonical rejected/expired/confirmed/failure/timeout states are retained. Replan attempts and the two-supersession SQL limit bound stale conflicts. Large bursts may end safely unresolved; this is deliberately not a completion guarantee.

`events.build_functions` returns an incident fanout, a shipment-wait handler and a five-minute sweep. Incident bursts are limited to 100 unique configured shipment IDs. Events contain only opaque tenant/actor/incident/shipment identifiers. Request event IDs are deterministic; repeat review/confirmation wakeups get new IDs. Matching waits include tenant, incident and shipment. Every wakeup rereads authenticated canonical state; a forged review event does not approve a proposal. Sweeps recover lost/early wakeups by reading the trusted incident registry. The registry must be provisioned durably by the hosting application.

SDK mocked steps and real SQL tests verify composition and restart boundaries. They do not establish hosted Inngest durability, platform delivery latency, a deployed schedule or production traffic behavior. LangGraph is re-created after each restart and needs no second checkpoint database because the authoritative domain state is in Postgres. Tracing is disabled for the graph so private facts/grants are not exported implicitly.

## Reproduce the checks

From the repository root, install with `python dev.py setup`, then:

```powershell
uv run --locked --all-packages --link-mode copy python -m supply_chain.simulator
uv run --locked --all-packages --link-mode copy python -m pytest -q tests/test_supply_simulator.py
uv run --locked --all-packages --link-mode copy python -m pytest -q tests/integration/test_supply_operations.py -o addopts=--strict-markers
python dev.py check
python dev.py db-check
python dev.py eval-replay
python dev.py build
```

The database test fixture starts its own checkout-keyed disposable Postgres service, installs the immutable `operations.sql` schema and restricted role, enrolls invented incidents, and removes its owned trial/service afterward. It includes a child process that exits immediately after commit, then reopens connections and verifies the original receipt and debit.

For application composition, trusted administrator code calls `operations.setup(admin_connection, runtime_role)` once and `enroll(admin_connection, incident_id, shipments)` without upserts. Compose `OperationStore(connect_runtime, clock=aware_clock)`, a scoped operator Grant, and `SupplyWorkflow(store)`. Call `run(grant, incident_id, run_id)`; use separately scoped reviewer/confirmation identities through `store.review` and `store.confirm`. Never use a planner response or an Inngest event as the grant. No real database URI or password belongs in a command example, report or Git.

The optional package extra is `production-agent-supply-chain[workflow]`. It reuses the existing locked LangGraph/Inngest versions. The changed environment identity requires an explicit invented replay capture; historical recordings remain immutable. Fresh provider release acceptance stays pending under the user's offline-only instruction.


## Review evidence

[PR #90](https://github.com/Protagonist01/my-production-agentic-systems/pull/90), source head0406e82: all ten jobs passed in [run39864242079](https://github.com/Protagonist01/my-production-agentic-systems/actions/runs/39864242079). Actual logs verify846tests in each quality cell and86Postgres tests, alongside package, replay, type, audit and secret checks. The installed-wheel network-denial probe verified52harness/11Supply source/resource files. Local focused30simulator/18Postgres tests passed. Local full offline tests passed846cases666.16seconds after selecting external TEMP/TMP. The local full database run passed85/86; the sole private-path failure passed separately32.80seconds with external output. The clean86-test single-run result is hosted evidence, not a claim that the first local run passed.

On hosts with a Git marker above the default temporary directory (this host has C:\.git), raw-source tests correctly fail there. Set TEMP/TMP to a private directory outside every checkout before running source/full tests. Do not remove a Git marker, weaken the guard or put raw-source fixtures inside repository artifacts just to make a test pass. The inventory and code-study anchors pin the source snapshot; final review-head results are attached to the PR/issues.


## Stronger evaluation requirements — 2026-10-24

[Shared standards](evaluation-standards.md) and the [five-agent readiness inventory](evaluation/readiness.json) apply to the next release study. S6 needs budget/approval/state/recovery checks plus changed-model and cost-sensitivity evidence. Qualification stays simulation-only and cannot establish causal freight savings. Existing sealed pilots are unchanged. Missing reviews, approved pre-output thresholds, grouped unseen inputs, complete field scores/accounting or H10 evidence block release. No additional provider run or release approval is inferred.
