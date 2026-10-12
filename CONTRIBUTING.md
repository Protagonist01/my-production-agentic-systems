# Contributing

Select a Ready implementation issue from the [delivery plan](docs/project-management.md); agree ownership, prerequisites and acceptance checks before work.

1. Create one issue-sized branch from reviewed main. Use an isolated worktree/service environment after the contract baseline exists.
2. Change owned paths; route shared interfaces, dependencies, CI and common migrations through the integrator.
3. Run checks appropriate to the actual implementation. Record commands and results; planned checks are not passes.
4. Open a PR linking the issue, describing behavior and including concrete acceptance evidence. Keep real/hybrid/synthetic results and replay/fresh results separate.
5. Review and merge only when prerequisites and required checks pass. Close the issue with evidence and update the planning snapshot.

Never commit credentials, raw datasets, sensitive traces or unreviewed recordings. Keep source manifests and independently reviewed evaluation labels reproducible. Append material design/debugging decisions to BUILD_BOOK.md while working.

F1 provides the direct install/test/boundary/build commands in README. Portable command wrappers remain F3 and automated CI remains F5. From the root, run `uv sync --locked --all-packages --link-mode copy` before the checks. Keep dynamic imports out of package boundaries unless reviewed explicitly; static import contracts cannot police reflective module loading.
