# Foundation CI — F5

The Foundation CI workflow implements the existing portable development checks and disposable Postgres acceptance checks. It runs for every pull request and pushes to main, without path filters. No live AI provider, Langfuse experiment or fresh-quality evaluation is configured. H3 adds a required pinned invented strict-replay command in each quality cell. The fake example and replay remain wiring checks; eval-record/eval-compare still return exit 2.

## Jobs and local equivalents

| Job | Required behavior | Local command |
|---|---|---|
| Quality, Ubuntu 24.04 / Windows 2025 × Python 3.12 / 3.13 | Locked setup, explicit interpreter check, shared lock/lint/format/types/import/tests, offline fake example and six-package build | `python dev.py setup/check/example/build`, individually |
| Postgres isolation, Ubuntu | F4's required two-service suite, no skips when Docker is absent | `python dev.py db-check` |
| Locked dependency audit, Ubuntu and Windows, Python 3.13 | Export all locked third-party/dev-group dependencies with hashes, omit local workspace distributions, run strict pip-audit | `python dev.py audit` |
| Repository secret scan, Ubuntu | Pinned Gitleaks action scans the selected Git history/range with full checkout history | Gitleaks 8.30.1 CLI `gitleaks git --redact --no-banner` |
| PR issue and evidence | Validate one primary issue and three substantive sections; confirm the issue exists in this repository | `python ci_checks.py pr --event-file <event.json>` with a read-only GitHub token |
| CI gate | Require success for quality, Postgres, both audits and secret scan; require PR evidence on PR events, permit only its intentional skip on push-main | `python ci_checks.py gate` with recorded job result environment |

The job uses explicit `UV_PYTHON` and `UV_PYTHON_DOWNLOADS=never` after setup-python installs the matrix interpreter. .python-version still defaults local development to 3.13, but cannot silently make every CI matrix cell run 3.13. Each quality job prints/asserts its actual interpreter version. Setup and audit need package/advisory downloads; Postgres can need the pinned image download. “Offline” means no AI-provider dependency, not an air-gapped installation.

Ordinary `check/test` intentionally excludes database execution, while lint inspects its source. CI requires the separate db-check job, so an absent Docker service or skipped database job cannot earn a gate pass. H3 replay consumes the bundled reviewed fixture without provider clients; record/compare remain unavailable. Add domain quality gates only when their cases/scorers exist, with completeness/critical-case checks and reviewed thresholds under H5/H6/H9/H10. Do not turn the fake score into an industry quality threshold.

## PR conventions and shared ownership

Use a literal line `Refs #<primary repository issue number>`, for example `Refs #14`, in the PR body. Keep all three template sections: Problem and behavior, Acceptance evidence, and Risks and remaining limits. Write concrete behavior, actual check evidence and applicable limitations; empty/template text fails. Additional dependencies may be linked elsewhere, but there is one primary task. The check confirms an issue, rather than another PR, at the fixed repository API endpoint. It does not prove claims in prose are true; reviewers must inspect linked logs, data/version evidence and code.

The integrator owns root commands/CI/lockfiles, shared contracts/migrations and Build Book. CODEOWNERS maps these paths to Protagonist01; a vertical owns its domain code/data/policy/scoring. Follow CONTRIBUTING.md and the issue acceptance checklist. Referenced implementation issues remain open through review and are closed after merge plus post-merge verification. Do not use automatic closing keywords as a substitute for that verification.

Merge only after **CI gate** and acceptance review pass. This change does not configure branch protection/rulesets or claim GitHub automatically prevents every manual merge. CODEOWNERS identifies responsibility; it does not make self-authored reviews independent. The user/integrator still performs review and accepts evidence.

## Supply-chain and trust boundaries

External Actions are pinned to verified full commit SHAs: checkout v7.0.1, setup-python v7.0.0, setup-uv v10.3.0 and Gitleaks action v3. uv is 0.11.1, Gitleaks is 8.30.1, pip-audit is 2.10.1 and the shared lock pins its dependencies. GitHub token permissions are contents/issues/pull-requests read only; checkout does not persist credentials. PR-controlled body/branch/title strings are never interpolated as shell commands. No provider credential is configured and the workflow does not use pull_request_target.

Gitleaks comments, result uploads and summary output are disabled. Findings still fail its job and require owner investigation/credential rotation; no actual credential should be inserted to test a scan. Dependency auditing fails on vulnerabilities or collection/service errors. It does not auto-fix, suppress IDs or treat an advisory outage as clear. A “no known vulnerabilities” result is time-sensitive advisory evidence, not proof every dependency/build tool or native component is safe. Gitleaks heuristics cannot detect every secret, and history/range coverage differs by event. Third-party Actions and GitHub-hosted runners remain trusted execution dependencies.

## Evidence lifecycle

F4 merged baseline d3f783c passed 64 offline tests and 11 Postgres checks before F5. Initial F5 local checks passed 77 tests, eight strict type-checked source files, Ruff, both import contracts, six builds and a hashed locked dependency audit. The [negative-control run](https://github.com/Protagonist01/my-production-agentic-systems/actions/runs/38640533520), head 9e79694, rejected the exact Olist-to-CFPB import at the architecture stage in all four quality jobs and failed CI gate. The control was removed. The [clean hosted run](https://github.com/Protagonist01/my-production-agentic-systems/actions/runs/38641578564), head 9cbc8ad024871c656357eb3ccd7d32d8ae63d407, passed all ten jobs: four quality cells, Postgres, two audits, Gitleaks, PR metadata and CI gate. Quality executed 77 tests and Postgres 11; no required database skip. Documentation refresh commits receive the same full workflow; latest-head evidence is in PR #70. A YAML file or local test run alone is not a hosted CI pass.

Primary references: [GitHub security hardening](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments), [uv CI/interpreter selection](https://docs.astral.sh/uv/guides/integration/github/), [pip-audit options](https://github.com/pypa/pip-audit) and [Gitleaks Action configuration](https://github.com/gitleaks/gitleaks-action).

## Merged foundation and H1 boundary

PR #70 merged to main 6e48011. Push-main run [38647582091](https://github.com/Protagonist01/my-production-agentic-systems/actions/runs/38647582091) passed all nine applicable jobs; PR metadata was intentionally skipped and CI gate passed. Local verification recorded a restart-wait failure, then a fresh 11/11 Postgres pass; #14, Epic F and M1 are completed. H1 adds only provider-free mock compatibility tests to ordinary CI. Live Gemini/localhost Langfuse commands remain explicitly separate; no provider credentials or live quality gate was added to the workflow.
