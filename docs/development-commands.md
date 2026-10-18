# Development commands — F3

`python dev.py <command>` is the shared PowerShell/Linux/CI entrypoint. Python 3.12–3.13 and uv on PATH are prerequisites; the exercised environment is Windows/Python 3.13.4/uv 0.11.1. No Bash, Make, shell activation or runtime service is required. F3 defines these commands; F5 implements [hosted Foundation CI](ci.md) on Ubuntu/Windows with explicit Python 3.12/3.13 selection. Actual run results are recorded there and in PR #70.

## Fresh checkout

Clone the repository into a new directory, check out the reviewed main commit, then run:

```powershell
python dev.py setup
python dev.py check
python dev.py example
python dev.py build
```

Setup executes `uv sync --locked --all-packages --link-mode copy`. uv resolves the interpreter from the project, validates the existing lockfile and installs all workspace members plus development dependencies. It does not regenerate the lockfile. The shared root is virtual; omitting all-packages would leave member imports uninstalled. Package installation may contact the configured package index. The example itself contacts no provider, database or telemetry.

Every tool runs with the same locked/all-packages/copy flags, rooted at `Path(__file__).resolve().parent`; caller working directory does not select a different project. Each worktree has its own environment and project check caches. F4 adds the [local Postgres command path](local-postgres.md) for service/trial state; its required `db-check` is separate from offline `check`.

## Check map

| Runner command | Underlying command, after the uv prefix |
|---|---|
| `lock` | `uv lock --check` |
| `lint` | `python -m ruff check dev.py ci_checks.py harness projects tests` |
| `format-check` | `python -m ruff format --check dev.py ci_checks.py harness projects tests` |
| `types` | `python -m mypy`, using strict root configuration for dev.py, ci_checks.py and harness |
| `imports` | `lint-imports --no-cache` |
| `test` | `python -m pytest -q` |
| `build` | `uv build --all-packages` |

`check` runs the first six rows in order, with the exact same argument map as individual commands. It stops on the first nonzero child status and returns that status. Missing uv/process-start errors fail with a clear message. It never autoformats source. Changing a check means changing one map, its relevant tests and this documentation.

All commands use subprocess argument lists and `shell=False` (the default), so paths and single arguments containing spaces remain intact. Commands inherit ordinary process configuration, including intentionally selected uv environment/cache paths. They do not load .env files or print credentials. The root type-checker dependency is exactly pinned in uv.lock; no per-run extra type-checker environment is installed.

## Example and planned evaluation

`example` captures Git HEAD and porcelain status, appends `+dirty` for tracked or untracked changes, and passes the root lockfile to F2's offline CLI. Ignored environments/outputs do not dirty the source. Dirty is a warning about identity, not a content hash or reproducible dirty snapshot. Git must be available and this must be a checkout; source exports need `--code-revision <actual-source-identifier>`. An explicit value remains the caller's responsibility.

The stdout report is JSON, marked `synthetic`/`offline_fake`; lockfile SHA-256 and revision remain in its context. Store optional reports under an ignored artifacts directory outside source. A fake score of 1 is wiring evidence, not real model quality.

`eval-replay` now runs the [H3 pinned invented replay](replay.md), with actual current source/lock identity and no provider client. It requires complete consumption and exits nonzero on mismatch. `eval-record` and `eval-compare` still return exit 2 before finding/installing uv; their messages name H10 #24 and H9 #23 respectively. Unknown commands and wrong options also fail. A future implementation must replace the explicit unavailable path and add its required behavioral tests; it must never return success with a placeholder result.

## CI contract

F5 installs supported Python/uv and calls the same four commands in the fresh-checkout block above. The workflow selects/asserts the actual matrix interpreter instead of letting .python-version silently select every cell. Required separate db-check, hashed dependency audits, secret scan and PR evidence feed CI gate. The clean hosted implementation passed all ten jobs on Ubuntu/Windows and Python 3.12/3.13; latest-head results and limits are in [Foundation CI](ci.md). H3 adds `python dev.py eval-replay` after the invented example in each quality cell. This is synthetic model replay, not a domain quality gate. Fresh quality/release evaluation remains H9/H10.

Design references: [uv command environments](https://docs.astral.sh/uv/concepts/projects/run/) and [locked syncing](https://docs.astral.sh/uv/concepts/projects/sync/). The exact tested commands are in dev.py, rather than inferred from current docs.

## Local services — F4

`db-up/status/down/destroy` and `trial-create/reset/drop` dispatch through the same locked uv prefix to `agent_harness.local_services`, with this runner’s absolute root. Trial commands require `--trial`; destroy requires `--confirm-workspace`. Wrong options fail before dispatch. `db-check` runs `tests/integration` with the offline pytest exclusion explicitly overridden; missing Docker is a failure, not a skip. Ordinary `test/check` exclude database execution while Ruff still inspects its code. See [local Postgres](local-postgres.md) for setup, ownership, reset and limits.

## Locked dependency audit — F5

`python dev.py audit` uses the same locked uv environment to call ci_checks.py. Export all exact locked third-party/dev-group requirements with hashes, omit local workspace packages, and run pip-audit 2.10.1 with --require-hashes/--disable-pip/--strict. It queries public advisory services, returns actual failure status and never suppresses IDs or treats an outage as clear. It is separate from offline check.

## H1 provider and trace probes

Merged H1 integration-check uses the pinned SDK/frameworks on mock HTTP transport; its negative/network-boundary cases run in ordinary check. integration-live requires a user-confirmed Free Gemini project and two fresh invented requests. trace-check additionally requires dedicated local Langfuse credentials, Node/npx and successful v4 CLI read-back. These live commands are excluded from hosted offline CI. See [integration commands](integration-smoke.md) and [decision](adr/0001-first-integration.md).


## H2 shared gateway probe

`gateway-live` uses the same locked uv environment and revision/dirty detection as `example`; it dispatches agent_harness.gateway_probe with the checkout root and code revision. Source exports can pass --code-revision explicitly. It makes at most two invented Free-tier requests through ProviderGateway and GeminiTransport, preserving the signed function history and validating the final JSON. It is excluded from CI and is not a quality evaluation or durable recorder. [Scope, optional runtime installation and observed evidence](gateway.md).

On the H4 branch, gateway-live uses BoundedGateway and an owned SDK process with one attempt per request, two shared call reservations and separate observed usage. It remains explicit, credentialed and excluded from CI. H1 compatibility/live/trace probes retain their original path; see [controls](controls.md).

## H8 invented telemetry check

`python dev.py telemetry-check` sends an invented seven-observation trace to the configured local Langfuse project and independently reads it through the pinned CLI. It obtains actual source/lock identity, verifies correlation/version/source/privacy evidence and prints safe health. It uses no provider and is excluded from offline CI. The full setup, privacy distinction and failure limits are in [telemetry operations](telemetry.md). The existing H1 trace-check retains its live-model behavior.
