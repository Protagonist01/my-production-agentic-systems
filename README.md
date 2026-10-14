# my-production-agentic-systems

Production-minded AI agents across five industries, with a shared evaluation harness, versioned datasets, regression testing, fault injection, observability and code-enforced action controls.

Build the real platform and usable applications together at 40 hours/week, including integration and data/evidence review. The first complete release is Olist support; all five verticals remain committed scope.

## Current status

The [GitHub delivery project](https://github.com/users/Protagonist01/projects/2) contains a [root tracker](https://github.com/Protagonist01/my-production-agentic-systems/issues/1), eight epics and 53 task sub-issues, organized into seven milestones. F1 and O1 are merged into main and verified. F2 provides validated shared contracts and an executable offline fake case on its review branch. Real provider-backed agents, domain importers, database migrations, CI and deployment remain subsequent work.

## Working foundation commands

From the repository root, with Python 3.13 and uv 0.11.1 (the versions exercised here):

```powershell
uv sync --locked --all-packages --link-mode copy
uv run --locked pytest -q
uv run --locked lint-imports --no-cache
uv run --locked ruff check harness projects tests
uv run --locked ruff format --check harness projects tests
uv build --all-packages
$revision = git rev-parse HEAD
uv run --locked python -m agent_harness.offline_example --code-revision $revision --lockfile uv.lock
```

The lockfile pins development dependencies; each package pins its build backend. The allowed Python range is 3.12–3.13; verification so far is Windows/Python 3.13.4. `--link-mode copy` avoids cross-drive hardlink warnings. `uv sync` without `--all-packages` does not install the six workspace members because the root is virtual.

| Package directory | Python import | Runtime dependencies |
|---|---|---|
| `harness` | `agent_harness` | Pydantic 2.14.1 |
| `projects/olist-support` | `olist_support` | Harness |
| `projects/cfpb-triage` | `cfpb_triage` | Harness |
| `projects/revenue-integrity` | `revenue_integrity` | Harness |
| `projects/prior-auth` | `prior_auth` | Harness |
| `projects/supply-chain-disruption` | `supply_chain` | Harness |

The import checker rejects direct and indirect harness-to-domain and cross-domain imports. It checks static Python imports, including relative and type-checking imports; reflective imports/plugin loading are not a security boundary and need explicit review if introduced. Tests use temporary source copies to prove bad import paths fail without modifying the working packages.

Copy `.env.example` to an ignored `.env` only when an implementation needs configuration. Its empty values are reserved names, not working integrations. Raw datasets belong outside this checkout. The [F2 fake case](docs/shared-contracts.md) needs no services or credentials and proves contract wiring, not model quality. Its result is explicitly synthetic/offline_fake; scheduled faults and live/replay modes fail clearly. Portable command wrappers, services, real model evaluation and CI remain F3/F4/F5 and harness/domain tasks. Use a clean committed checkout for the revision command above; identify uncommitted changes explicitly when experimenting.

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

[Delivery plan](docs/project-management.md) · [Backlog](docs/backlog.json) · [Architecture and data plans](docs/README.md) · [Build Book](BUILD_BOOK.md)

[F1 PR #63](https://github.com/Protagonist01/my-production-agentic-systems/pull/63) and [O1 integration PR #65](https://github.com/Protagonist01/my-production-agentic-systems/pull/65) are merged and their tasks closed after verification. O1 acquired and profiled the original version-7 source outside Git: [handling and acquisition](docs/data/olist-source.md), [aggregate manifest](docs/data/olist-v7-manifest.json). [F2 PR #66](https://github.com/Protagonist01/my-production-agentic-systems/pull/66) defines [shared contracts](docs/shared-contracts.md) and the fake end-to-end case, and is open for review. Parallel implementation worktrees await the reviewed, merged F2 baseline.
