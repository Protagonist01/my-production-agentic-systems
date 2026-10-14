# Contributing

Select a Ready implementation issue from the [delivery plan](docs/project-management.md); agree ownership, prerequisites and acceptance checks before work.

1. Create one issue-sized branch from reviewed main. Use an isolated worktree/service environment after the contract baseline exists.
2. Change owned paths; route shared interfaces, dependencies, CI and common migrations through the integrator.
3. Run checks appropriate to the actual implementation. Record commands and results; planned checks are not passes.
4. Open a PR linking the issue, describing behavior and including concrete acceptance evidence. Keep real/hybrid/synthetic results and replay/fresh results separate.
5. Review and merge only when prerequisites and required checks pass. Close the issue with evidence and update the planning snapshot.

Never commit credentials, raw datasets, sensitive traces or unreviewed recordings. Keep source manifests and independently reviewed evaluation labels reproducible. Append material design/debugging decisions to BUILD_BOOK.md while working.

Maintain [CODE_STUDY_GUIDE.md](CODE_STUDY_GUIDE.md) alongside the Build Book. For substantive implementation/design changes, refresh affected architecture, code walkthroughs and verified line links, tradeoffs, findings, test evidence and interview explanations. Record the inspected revision and keep planned/unmerged behavior distinct. The reusable `$code-study-guide` skill supports this workflow when installed; the guide itself defines the maintenance/evidence requirements for other contributors. Do not silently fix code or publish issues as part of a guide-only update.

Use `python dev.py setup`, then `python dev.py check` before opening a PR. Individual checks, the offline example and builds use the same [portable command runner](docs/development-commands.md) that F5's CI jobs will call. F5 implements [Foundation CI](docs/ci.md) in its review branch: both OS/Python quality matrix, required Postgres checks, hashed locked dependency audit, secret scan and PR evidence gate. Require CI gate and acceptance review before merging; hosted evidence is recorded in the implementation PR. Keep dynamic imports out of package boundaries unless reviewed explicitly; static import contracts cannot police reflective module loading.

PRs must include one primary `Refs #<issue>` line and substantive Problem and behavior, Acceptance evidence, and Risks and remaining limits sections. CODEOWNERS identifies the integrator for root commands, CI, shared contracts, lockfiles and migrations. The metadata check confirms the issue exists but does not validate prose truth; inspect logs and versions. Implementation issues stay open until merge and post-merge checks.
