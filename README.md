# my-production-agentic-systems

Production-minded AI agents across five industries, with a shared evaluation harness, versioned datasets, regression testing, fault injection, observability and code-enforced action controls.

Build the real platform and usable applications together at 40 hours/week, including integration and data/evidence review. The first complete release is Olist support; all five verticals remain committed scope.

## Current status

The [GitHub delivery project](https://github.com/users/Protagonist01/projects/2) contains a [root tracker](https://github.com/Protagonist01/my-production-agentic-systems/issues/1), eight epics and 53 task sub-issues, organized into seven milestones. F1, O1, F2 and F3 are merged and verified on main ce8334c. F4 adds checkout-specific Postgres services and isolated trial databases on its review branch. Provider-backed agents, domain importers, workflow adapters, CI jobs and deployment remain subsequent work.

## Setup and working commands

Install Python 3.13 and uv on PATH; verification uses Python 3.13.4 and uv 0.11.1 on Windows. The supported Python range is 3.12–3.13. The runner itself uses only Python's standard library, so setup works before dependencies are installed. From a fresh checkout:

```powershell
git clone https://github.com/Protagonist01/my-production-agentic-systems.git
cd my-production-agentic-systems
python dev.py setup
python dev.py check
python dev.py example
python dev.py build
```

PowerShell and the planned CI job use the same `python dev.py check`: lock, lint, format-check, types, imports and tests in that order. The runner stops at the first failure and returns its exit code. It runs from its own checkout root, even when called by absolute path from another directory. No activation or Make/Bash wrapper is required.

| Command | Behavior |
|---|---|
| `setup` | Locked installation of all six workspace members and dev dependencies |
| `check` | All six checks below; never autoformats or hides a failure |
| `lock`, `lint`, `format-check`, `types`, `imports`, `test` | Run the corresponding individual check |
| `example` | F2's invented offline case; actual Git HEAD plus `+dirty` when tracked/untracked changes exist |
| `build` | Build all six source archives and wheels |
| `db-up`, `db-status`, `db-down` | Start, inspect or stop this checkout’s isolated Postgres service |
| `trial-create`, `trial-reset`, `trial-drop` | Manage one disposable trial; require `--trial <identity>` |
| `db-check` | Required two-service database evidence; separate from offline `check` |
| `db-destroy` | Remove only this project’s volume; require its exact workspace identifier |
| `eval-replay`, `eval-record`, `eval-compare` | Explicitly unavailable: exit 2 with the prerequisite issue |

The lockfile pins development dependencies, including mypy 2.4.0; each member pins its build backend. Setup/tool commands use `--locked --all-packages --link-mode copy`. The virtual root otherwise does not install all members. Type checking currently covers `dev.py` and the shared harness; lint/tests cover all implemented packages/tools. Full commands and the future CI contract are in [development commands](docs/development-commands.md). Linux/Python 3.12 and actual CI jobs remain F5 verification.

| Package directory | Python import | Runtime dependencies |
|---|---|---|
| `harness` | `agent_harness` | Pydantic 2.14.1; Psycopg binary 3.3.6 |
| `projects/olist-support` | `olist_support` | Harness |
| `projects/cfpb-triage` | `cfpb_triage` | Harness |
| `projects/revenue-integrity` | `revenue_integrity` | Harness |
| `projects/prior-auth` | `prior_auth` | Harness |
| `projects/supply-chain-disruption` | `supply_chain` | Harness |

The import checker rejects direct and indirect harness-to-domain and cross-domain imports. It checks static Python imports, including relative and type-checking imports; reflective imports/plugin loading are not a security boundary and need explicit review if introduced. Tests use temporary source copies to prove bad import paths fail without modifying the working packages.

Copy `.env.example` to an ignored `.env` only when an implementation needs configuration. Its empty values are reserved names, not working integrations. Raw datasets belong outside this checkout. The [F2 fake case](docs/shared-contracts.md) needs no services or credentials and proves contract wiring, not model quality. Its result is explicitly synthetic/offline_fake; scheduled faults and live/replay modes fail clearly. The example wrapper hashes the lockfile and marks a dirty tree rather than claiming HEAD describes uncommitted code. For a source export without Git, provide `python dev.py example --code-revision <actual-source-identifier>`. F4 service commands require Docker; see [local Postgres and state ownership](docs/local-postgres.md). On main until F4 merges, use its PR branch for these commands. Real model evaluation and CI jobs remain later harness/domain/F5 tasks.

## Applications

| Application | Source input | Delivered behavior |
|---|---|---|
| Olist support | Historical Brazilian commerce orders | Scoped support, controlled refunds, durable review and recovery |
| CFPB triage | Published consumer complaints | Classification, calibrated routing and review |
| Revenue integrity | Authentic commercial contracts | Cited extraction plus separately reported simulated reconciliation and approved corrections |
| Prior auth | Selected policies and illustrative notes | Criterion evidence assessment, recommendation and qualified review |
| Supply chain | Shipping observations and weather snapshots | Simulated interventions, budget allocation and approval/confirmation workflows |

The software/API/UI is real; business write backends are controlled environments. Evaluation reports distinguish original data, hybrid workflows and synthetic/adversarial cases. No real recovered revenue, clinical outcome or freight-saving claim follows from simulation.

## Delivery and evidence

Start repository foundation and Olist source acquisition. Verify minimal shared contracts, then implement gateway, evaluation and Olist in bounded worktrees. Each release needs independent scoring, required-case/fault checks and fresh candidate evidence. Replay checks current software against captured dependencies; fresh evaluation measures candidate quality; monitoring observes served traffic.

[Delivery plan](docs/project-management.md) · [Backlog](docs/backlog.json) · [Architecture and data plans](docs/README.md) · [Build Book](BUILD_BOOK.md) · [Code study guide and interview preparation](CODE_STUDY_GUIDE.md)

[F1 PR #63](https://github.com/Protagonist01/my-production-agentic-systems/pull/63), [O1 integration PR #65](https://github.com/Protagonist01/my-production-agentic-systems/pull/65) and [F2 PR #66](https://github.com/Protagonist01/my-production-agentic-systems/pull/66) are merged and verified. O1 source remains outside Git: [handling/acquisition](docs/data/olist-source.md), [aggregate manifest](docs/data/olist-v7-manifest.json). F2 defines [shared contracts](docs/shared-contracts.md) and the offline fake case. [F3 PR #68](https://github.com/Protagonist01/my-production-agentic-systems/pull/68) is merged and verified on ce8334c. [F4 PR #69](https://github.com/Protagonist01/my-production-agentic-systems/pull/69) references issue #13 and uses the attached worktree on `codex/f4-postgres-isolation`, with independently checked disposable database state.
