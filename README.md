# my-production-agentic-systems

Production-minded AI agents across five industries, with a shared evaluation harness, versioned datasets, regression testing, fault injection, observability and code-enforced action controls.

Build the real platform and usable applications together at 40 hours/week, including integration and data/evidence review. The first complete release is Olist support; all five verticals remain committed scope.

## Current status

Verified main `6bcac64` includes user-merged #96: nine applicable checks passed,936tests per quality cell and103Postgres, including clean dependency audits. The [separate O8 follow-up](docs/olist-followup-model-card.md) scored36/36correct Gemini trials with known token usage and local process timing. The [old pilot](docs/olist-model-card.md) retains its six timeouts. Four request templates repeat across splits, so the follow-up does not establish broad language robustness. Independent labels/baselines/thresholds and representative validation still gate downstream releases. Native board state is unverified.

## Setup and working commands

Install Python 3.13 and uv on PATH; verification uses Python 3.13.4 and uv 0.11.1 on Windows. The supported Python range is 3.12â€“3.13. The runner itself uses only Python's standard library, so setup works before dependencies are installed. From a fresh checkout:

```powershell
git clone https://github.com/Protagonist01/my-production-agentic-systems.git
cd my-production-agentic-systems
python dev.py setup
python dev.py check
python dev.py example
python dev.py build
```

PowerShell and the hosted CI jobs use the same `python dev.py check`: lock, lint, format-check, types, imports and tests in that order. The runner stops at the first failure and returns its exit code. It runs from its own checkout root, even when called by absolute path from another directory. No activation or Make/Bash wrapper is required.

| Command | Behavior |
|---|---|
| `setup` | Locked installation of all six workspace members and dev dependencies |
| `check` | All six checks below; never autoformats or hides a failure |
| `lock`, `lint`, `format-check`, `types`, `imports`, `test` | Run the corresponding individual check |
| `example` | F2's invented offline case; actual Git HEAD plus `+dirty` when tracked/untracked changes exist |
| `build` | Build all six source archives and wheels |
| `audit` | Audit hashed locked third-party/development requirements against public advisories |
| `integration-check` | Merged H1: pinned SDK/framework checks over a mock HTTP transport |
| `integration-live` | Merged H1: two invented Gemini requests; requires a confirmed Free project |
| `gateway-live` | Merged H4: at most two invented calls through reserved, process-bounded attempts |
| `trace-check` | Merged H1: two fresh calls, local Langfuse export and required CLI read-back |
| `db-up`, `db-status`, `db-down` | Start, inspect or stop this checkoutâ€™s isolated Postgres service |
| `trial-create`, `trial-reset`, `trial-drop` | Manage one disposable trial; require `--trial <identity>` |
| `db-check` | Required two-service database evidence; separate from offline `check` |
| `db-destroy` | Remove only this projectâ€™s volume; require its exact workspace identifier |
| `eval-replay` | H3: pinned invented model-call replay; current code, no provider transport, completion required |
| `scorecard` | H9: private JSON/Markdown from pinned journals; explicit baseline comparisons, no release decision |
| `eval-record`, `eval-compare`, `eval-release` | H10: pinned fresh captures, case regressions and independently approved release gates; see [runbook](docs/release-evidence.md) |

H6's invented isolated-trial example runs through an explicit module entrypoint; see [the trial runbook](docs/isolated-trials.md#run-the-invented-example). It records every planned trial, fresh state, independent outcome scores and incomplete evidence without a live provider.

The lockfile pins development dependencies, including mypy 2.4.0; each member pins its build backend. Setup/tool commands use `--locked --all-packages --link-mode copy`. The virtual root otherwise does not install all members. Strict type checking covers `dev.py`, `ci_checks.py`, the shared harness and domain source packages; lint/tests cover all implemented packages/tools. Full commands and the hosted CI contract are in [development commands](docs/development-commands.md). The [CI runbook](docs/ci.md) records actual Linux/Windows/Python matrix evidence and its limits.

| Package directory | Python import | Runtime dependencies |
|---|---|---|
| `harness` | `agent_harness` | Pydantic 2.14.1; Psycopg binary 3.3.6 |
| `projects/olist-support` | `olist_support` | Harness |
| `projects/cfpb-triage` | `cfpb_triage` | Harness |
| `projects/revenue-integrity` | `revenue_integrity` | Harness |
| `projects/prior-auth` | `prior_auth` | Harness |
| `projects/supply-chain-disruption` | `supply_chain` | Harness |

The import checker rejects direct and indirect harness-to-domain and cross-domain imports. It checks static Python imports, including relative and type-checking imports; reflective imports/plugin loading are not a security boundary and need explicit review if introduced. Tests use temporary source copies to prove bad import paths fail without modifying the working packages.

For H1, copy the selected placeholders from `.env.example` to ignored `.env.local`; do not put keys in chat or Git. Live probes require a confirmed Free Gemini project and dedicated local Langfuse keys. [Integration commands](docs/integration-smoke.md) distinguish offline checks, two-call smoke tests and required trace read-back. Raw datasets belong outside this checkout. The [F2 fake case](docs/shared-contracts.md) needs no services or credentials and proves contract wiring, not model quality. Its result is explicitly synthetic/offline_fake; the plain fake entrypoint rejects scheduled faults and live/replay modes; H7 fault drills use explicit separate composition. The example wrapper hashes the lockfile and marks a dirty tree rather than claiming HEAD describes uncommitted code. For a source export without Git, provide `python dev.py example --code-revision <actual-source-identifier>`. F4 service commands require Docker; see [local Postgres and state ownership](docs/local-postgres.md). F5 CI/audit commands are merged. H1 commands are merged. H2 adds the optional [Gemini runtime extra and gateway-live probe](docs/gateway.md); real model-quality evaluation remains later harness/domain work.

## Applications

| Application | Source input | Delivered behavior |
|---|---|---|
| Olist support | Historical Brazilian commerce orders | Scoped support, controlled refunds, durable review and recovery |
| CFPB triage | Published consumer complaints | Classification, calibrated routing and review |
| Revenue integrity | Authentic commercial contracts | Cited extraction plus separately reported simulated reconciliation and approved corrections |
| Prior auth | Selected policies and illustrative notes | Criterion evidence assessment, recommendation and qualified review |
| Supply chain | Shipping observations and weather snapshots | Simulated interventions, budget allocation and approval/confirmation workflows |

Olist has a local authenticated console and controlled SIM refund backend. Revenue adds read-only SIM reconciliation; its billing write backend and the remaining domain applications await their later tasks. Evaluation reports distinguish original data, hybrid workflows and synthetic/adversarial cases. No real recovered revenue, clinical outcome or freight-saving claim follows from simulation.

## Delivery and evidence

Start repository foundation and Olist source acquisition. Verify minimal shared contracts, then implement gateway, evaluation and Olist in bounded worktrees. Each release needs independent scoring, required-case/fault checks and fresh candidate evidence. Replay checks current software against captured dependencies; fresh evaluation measures candidate quality; monitoring observes served traffic.

[Delivery plan](docs/project-management.md) Â· [Backlog](docs/backlog.json) Â· [Architecture and data plans](docs/README.md) Â· [Build Book](BUILD_BOOK.md) Â· [Code study guide and interview preparation](CODE_STUDY_GUIDE.md)

[F1 PR #63](https://github.com/Protagonist01/my-production-agentic-systems/pull/63), [O1 integration PR #65](https://github.com/Protagonist01/my-production-agentic-systems/pull/65) and [F2 PR #66](https://github.com/Protagonist01/my-production-agentic-systems/pull/66) are merged and verified. O1 source remains outside Git: [handling/acquisition](docs/data/olist-source.md), [aggregate manifest](docs/data/olist-v7-manifest.json). F2 defines [shared contracts](docs/shared-contracts.md) and the offline fake case. [F3 PR #68](https://github.com/Protagonist01/my-production-agentic-systems/pull/68) is merged and verified on ce8334c. [F4 PR #69](https://github.com/Protagonist01/my-production-agentic-systems/pull/69) is merged and verified on d3f783c. [F5 PR #70](https://github.com/Protagonist01/my-production-agentic-systems/pull/70) is merged and verified on 6e48011: push-main CI, 77 offline checks, dependency audit, six builds and 11 local database checks after recording/retrying one restart-wait failure. [H1 PR #71](https://github.com/Protagonist01/my-production-agentic-systems/pull/71) is merged and verified on 0a859bb: main CI, 97 offline tests, exact-main example, offline integration, six builds and audit passed. H2 #72 is merged/verified on 9282d87: 151 offline tests, strict types/imports/Ruff/lock and nine applicable hosted jobs passed. H3 reuses the attached worktree on its own branch.

H7 #77 is merged and verified on main 487242f. H8 adds [correlated redacted telemetry](docs/telemetry.md) and an invented-only `python dev.py telemetry-check` export/read-back command. [Source walkthrough](docs/code-study-telemetry.md) follows the privacy and exporter-health boundaries. H8 #22 is completed after merge #78 on verified main 21a5720. H9 #23 adds [private scorecards and case-level comparisons](docs/scorecards.md); H10 #24 adds [fresh recording and release gates](docs/release-evidence.md), verified offline only. No domain release baseline exists.


O2 adds [private Olist order aggregates and conservative historical views](docs/data/olist-orders.md), with exact source-grain checks and preserved unknown currency/timezone. C1 source preparation proceeds independently in the user-selected parallel batch. Refund rules, business actions and domain model-quality evidence remain subsequent work.


C1 adds [pinned CFPB archive preparation](docs/data/cfpb-source.md): narrative-only agent storage, separate consumer-selected targets and exact-text grouped temporal partitions from the user-selected complete September 2023â€“March 2024 archive. [Source walkthrough](docs/code-study-cfpb.md) explains the boundaries. Raw records stay outside Git; this supplies data preparation, not a classifier or reviewed risk labels.


O6/O7 are merged and verified through #86: the [scoped local support desk](docs/olist-console.md) provides durable exact-action approval under the unchanged 100.00 SIM cap. The next user-authorized batch adds [offline Olist state reports](docs/olist-release.md) and [original CUAD contract preparation](docs/data/revenue-source.md), implemented in parallel and integrated for one review. Fresh provider/first-release acceptance remains pending by user instruction. C2 #84 is now merged and verified.

C2 #84 adds [provisional blind AI review and deterministic CFPB baselines](docs/cfpb-risk-baselines.md), with a [source study](docs/code-study-cfpb-baselines.md). It is merged/verified as95397c4; human adjudication and domain release evidence remain pending.

Supply-chain S2/S3/S4: [simulator, budgeted SIM actions and waits](docs/supply-chain-operations.md), [source walkthrough](docs/code-study-supply-operations.md). Invented mechanisms remain separate from S1 source observations and S6 release claims.

S5 #56 adds the [scoped Supply workbench and durable in-app previews](docs/supply-chain-console.md), with [scope and recovery walkthrough](docs/code-study-supply-console.md). SIM only; S6 remains behind the pending Olist fresh-release gate.

Prior Auth P1/P2/P3 adds [pinned CMS/Synthea preparation and evidence-checked Gemini assessment](docs/prior-auth-evidence.md), with [a source walkthrough](docs/code-study-prior-auth.md). The frozen six-case illustrative holdout matched all provisional labels; no clinical validation or authorization effect is claimed. P4/P5 extend this merged slice with document waits and a reviewer UI.

The user-selected P4/P5 extension adds [durable document requests and a protected local reviewer desk](docs/prior-auth-review.md), with a [recovery/access walkthrough](docs/code-study-prior-auth-review.md). Model failures remain qualified review, not completed clinical decisions. P6/O8 release gates remain separate.


CFPB C3/C4: [typed triage and durable reviewer operations](docs/cfpb-triage-operations.md), [source walkthrough](docs/code-study-cfpb-triage.md) and [aggregate pilot evidence](docs/data/cfpb-triage-evidence-v1.json). This is an unmerged implementation with AI-provisional labels and all-review results; no domain release.
