# Development commands — F3

`python dev.py <command>` is the shared PowerShell/Linux/CI entrypoint. Python 3.12–3.13 and uv on PATH are prerequisites; the exercised environment is Windows/Python 3.13.4/uv 0.11.1. No Bash, Make, shell activation or runtime service is required. F3 defines these commands; F5 still owns actual GitHub Actions jobs and Linux/Python 3.12 validation.

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
| `lint` | `python -m ruff check dev.py harness projects tests` |
| `format-check` | `python -m ruff format --check dev.py harness projects tests` |
| `types` | `python -m mypy`, using strict root configuration for dev.py and harness |
| `imports` | `lint-imports --no-cache` |
| `test` | `python -m pytest -q` |
| `build` | `uv build --all-packages` |

`check` runs the first six rows in order, with the exact same argument map as individual commands. It stops on the first nonzero child status and returns that status. Missing uv/process-start errors fail with a clear message. It never autoformats source. Changing a check means changing one map, its relevant tests and this documentation.

All commands use subprocess argument lists and `shell=False` (the default), so paths and single arguments containing spaces remain intact. Commands inherit ordinary process configuration, including intentionally selected uv environment/cache paths. They do not load .env files or print credentials. The root type-checker dependency is exactly pinned in uv.lock; no per-run extra type-checker environment is installed.

## Example and planned evaluation

`example` captures Git HEAD and porcelain status, appends `+dirty` for tracked or untracked changes, and passes the root lockfile to F2's offline CLI. Ignored environments/outputs do not dirty the source. Dirty is a warning about identity, not a content hash or reproducible dirty snapshot. Git must be available and this must be a checkout; source exports need `--code-revision <actual-source-identifier>`. An explicit value remains the caller's responsibility.

The stdout report is JSON, marked `synthetic`/`offline_fake`; lockfile SHA-256 and revision remain in its context. Store optional reports under an ignored artifacts directory outside source. A fake score of 1 is wiring evidence, not real model quality.

`eval-replay`, `eval-record` and `eval-compare` return exit 2 before finding/installing uv. Their messages name H3 #17, H10 #24 and H9 #23 respectively. Unknown commands and wrong options also fail. A future implementation must replace the explicit unavailable path and add its required behavioral tests; it must never return success with a placeholder result.

## CI contract

After F5 installs Python/uv, its job should call the same four commands in the fresh-checkout block above. There is no independent CI check list or a shell command chain that can ignore an earlier failure. F5 must still choose/install supported tools, test OS/interpreter combinations, control offline/provider boundaries and report job results. No CI pass is claimed by this document.

Design references: [uv command environments](https://docs.astral.sh/uv/concepts/projects/run/) and [locked syncing](https://docs.astral.sh/uv/concepts/projects/sync/). The exact tested commands are in dev.py, rather than inferred from current docs.

## Local services — F4

`db-up/status/down/destroy` and `trial-create/reset/drop` dispatch through the same locked uv prefix to `agent_harness.local_services`, with this runner’s absolute root. Trial commands require `--trial`; destroy requires `--confirm-workspace`. Wrong options fail before dispatch. `db-check` runs `tests/integration` with the offline pytest exclusion explicitly overridden; missing Docker is a failure, not a skip. Ordinary `test/check` exclude database execution while Ruff still inspects its code. See [local Postgres](local-postgres.md) for setup, ownership, reset and limits.
