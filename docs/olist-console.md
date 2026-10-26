# Local Olist support and review desk

O6 + O7 add authenticated local accounts, a support queue, durable reviewer decisions and exact-action execution to the [controlled Olist workflow](olist-workflow.md). The user approved this combined delivery on 2026-10-20 and retained the **100.00 SIM cap and existing eligibility rules**. Approval cannot override missing/conflicting facts or make an excessive refund eligible. No real payment provider or live model is connected.

## Start an owned local workspace

Use the locked checkout with Python 3.12/3.13 and Docker's Linux engine:

```powershell
python dev.py setup
uv run --locked --all-packages python -m olist_support.console_cli --root . --trial olist-desk bootstrap
```

Bootstrap creates/reuses only the named F4 trial and initializes the business, checkpoint and application schemas through admin connections. The application runs with the restricted trial role. Existing business-v1 DDL remains unchanged; the separate `olist_app` schema has its own immutable version/checksum. An incompatible schema needs an explicit migration/new trial. Never reset a shared volume to clear one case.

The package's optional `web` extra includes the existing `workflow` extra plus FastAPI 0.150.0 and Uvicorn 0.54.0. Root development setup includes it. A base Olist installation stays free of web/workflow SDKs. Source code, private configuration and enrolled source state remain separate.

## Enroll source and provision accounts

Use the existing [enrollment command](olist-workflow.md#enroll-an-explicitly-scoped-scenario) against the same trial. Reuse the independently pinned O2 database and declared source-local clock; supply fictional SIM confirmations separately. Enrollment is trusted admin provisioning, not an HTTP feature. Original Olist currency/timezone stay unverified. Support text and scenario facts do not grant permissions.

Create an external UTF-8 JSON principal file for each account. This invented example is the complete shape; replace IDs with the operator's explicitly assigned tenant/orders:

```json
{
  "schema_version": 1,
  "username": "desk-operator",
  "tenant_id": "invented-tenant",
  "actor_id": "invented-operator",
  "role": "operator",
  "order_ids": ["invented-order"]
}
```

Create a distinct reviewer principal with role `reviewer`, its own username/actor, and explicit order scope. An account supports at most 1,000 assigned IDs. Usernames are 3–64 lowercase letters/numbers/underscore/dot/hyphen and begin with a letter/number. Provisioning is exclusive; it will not overwrite an existing account.

```powershell
uv run --locked --all-packages python -m olist_support.console_cli --root . --trial olist-desk account --principal <external-operator.json>
uv run --locked --all-packages python -m olist_support.console_cli --root . --trial olist-desk account --principal <external-reviewer.json>
uv run --locked --all-packages python -m olist_support.console_cli --root . --trial olist-desk serve --port 8765 --run-limit-minor 10000 --telemetry-output <new-external-private-summary.json>
```

The account command prompts twice with hidden input for a 15–128-character password; never put it in command-line arguments or tracked files. Only a salted PBKDF2-SHA256 hash is stored. No public registration, client-supplied role or tenant selection exists. Accounts/grants are trusted local administration. Disabling an account through trusted administration immediately blocks its sessions; changing a password should also delete that account's session rows. Role/scope changes are read on each authenticated request.

Open [the local desk](http://127.0.0.1:8765). The supported server binds to loopback, ignores proxy identity/address headers and disables automatic access logging. The root and trial identify local F4 state; code/lock metadata comes from the checkout, with `+dirty` when applicable. No remote deployment, TLS termination, SSO, MFA, account recovery or production traffic is claimed.

The required telemetry path has a prepared private parent and must be new and outside Git.
See [shutdown and recovery](olist-operations-recovery.md#shutdown-and-private-telemetry)
for drain, flush and failure behavior.

## Complete a request and decision

1. Sign in as an operator. Select **New request**, choose an enrolled order in that account's scope and enter the customer's text. Request type is an explicit offline operator choice, not measured language classification.
2. For a manual approval demonstration, select **Send for a reviewer's decision before any refund**. Submit persists a case before running the workflow. Its idempotency key survives a retry of that draft. A new draft is a new business event; the business backend still prevents refunding an already-refunded order.
3. Sign out, then sign in as a distinct reviewer. Open the case. Inspect original recorded order evidence, explicitly fictional scenario confirmations, the proposed exact SIM amount and decision history. A source snapshot is historical, not a claim about live delivery status.
4. Enter a rationale and approve or reject. Approval binds tenant/order, full amount, policy, source/confirmation digest, order version, submitting actor, reviewer and case version. An ineligible case has no approvable command. Reship remains review-only; rejection never invokes a refund.
5. **Approved · not executed** means consent is saved and no refund is claimed. The same reviewer can choose **Execute approved … SIM**. The business tool rechecks current eligibility/version/run limit. Its trusted commit recorder updates the receipt, case completion and audit event in the same transaction as order/budget/ledger changes.
6. **Committed** requires a matching actual receipt and balance. Detail and queue reads reverify saved receipts. A stored proposal, approval, identifier or model message is insufficient.

The submitter cannot approve their own request, including after a role change. Operators cannot record reviewer decisions; reviewers cannot submit new support actions. Other tenants/orders cannot inspect the case or invoke its actions. Client JSON cannot supply a principal/grant, override policy or change the amount. Role visibility in the UI supplements server enforcement.

## Stale evidence and interrupted execution

If current record/version or evidence differs from the approved snapshot, execution makes no new refund and marks the case for reevaluation. **Reevaluate current evidence** clears the old approval and creates a new decision snapshot/digest/version. Inspect it and obtain new consent. The console does not edit source facts or scenario confirmations; unresolved evidence needs trusted upstream provisioning/correction first. Reevaluation alone cannot fill unknown facts or lift the cap.

A timeout/disconnection does not prove rollback. Refresh the case first. **Needs recovery** allows an operator to retry the saved request/checkpoint safely. An approved action may be retried by its recorded reviewer; the stable business key returns the original effect. After commit, receipt/case/audit already agree even if the response was lost. A new process uses the same Postgres state and session digests. Do not edit checkpoint JSON or case documents to manufacture approval.

The supplied run limit is nonnegative integer hundredths; 10,000 is 100.00 SIM. A new approved execution has its own run ID; an identical completed retry retains the original ledger receipt/run and consumes no additional refund. Changing the configured limit does not change the accepted per-order cap.

## HTTP surface and safeguards

| Route | Behavior |
|---|---|
| `POST /api/login`, `GET /api/session`, `POST /api/logout` | Provisioned credentials, opaque session lookup, revocation. No credentials/token in JSON responses or browser storage; the CSRF-cookie name is returned. |
| `GET /api/orders`, `GET /api/cases`, `GET /api/cases/{id}` | Account-scoped order choices, most recent 100 cases, private evidence/history and verified completion. |
| `POST /api/cases` | Operator-only strict `Submission`: event key, order, text, intent and manual-review flag. Trusted context/grant are server-created. |
| `POST /api/cases/{id}/decision` | Reviewer-only exact case version/action digest and rationale. Separate approve/reject consent. |
| `POST /api/cases/{id}/resume` | Operator request recovery or recorded-reviewer approved execution; exact digest required for the latter. |
| `POST /api/cases/{id}/reevaluate` | Scoped fresh decision snapshot; old consent is cleared. |
| `GET /health` | Aggregate storage readiness only, no account/order/connection details. |

Mutations require the configured exact Origin, JSON content type and a session-bound CSRF header (login requires same-origin JSON before a session exists). Sessions use random opaque tokens, store only token/CSRF digests, expire after 30 minutes and are revoked on logout. Session cookies are HttpOnly and SameSite Strict; the separate readable CSRF cookie supplies the header. Cookies use local HTTP because this delivery is loopback-only. Do not expose it as a remote service without a reviewed HTTPS/session deployment configuration.

Per-account failed sign-in is limited to five attempts in five minutes; a serialized global admission allows at most 100 attempts in that window before expensive password hashing. Expired counters and sessions are pruned during sign-in. Requests have a 16 KiB body cap in addition to text/field bounds (8,192 text characters); multibyte/escaped JSON may reach the byte cap first. The server admits 16 concurrent requests; this is a resource control, not a measured capacity guarantee.

Validation/DB failures return bounded generic errors, never echoed passwords/source payloads. The page uses same-origin static assets, a restrictive CSP, no-store responses, no framing, and text-only insertion for untrusted content. It writes no credentials to local/session storage. Native loading/empty/error/pending/stale/rejected/committed states and mobile/reduced-motion layouts are implemented. Implicit LangSmith exports remain disabled by the underlying workflow. The private decision audit is available in the UI; a complete serving-trace/Langfuse deployment integration remains later work.

These controls follow [OWASP password storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html), [session management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html) and [FastAPI security guidance](https://fastapi.tiangolo.com/tutorial/security/). They do not establish an exhaustive security audit. DB administrators/runtime credentials and local Python remain trusted; no tenant DB RLS boundary is claimed. Protect private source, passwords, sessions, checkpoint/case data and backups.

## Acceptance and cleanup

```powershell
python dev.py check
python dev.py db-check
python dev.py build
python dev.py audit
```

Public tests use invented records. Required real Postgres tests cover exact consent, races, cap/missing-fact refusal, stale reapproval, atomic rollback, lost response, a hard-exit child process, scoped HTTP roles/tenants, session expiry/revocation/throttling and denied audit/account mutation. Browser checks exercise operator→reviewer→approval→owned service restart→verified refund→reload, desktop/mobile rendering and an inert HTML-injection canary. They are automated mechanism checks, not human business adjudication or live model evaluation.

The [source drill aggregate](data/olist-approval-drill-v1.json) reuses three pinned private hybrid O3 groups. Three approvals produced zero refunds before execution, then three verified refunds and three committed audit events; independent ledger/order/budget totals all equal 19,116 minor SIM. Duplicate resumes created no second effects. The temporary source trial was removed. Only pins/counts are published; no source IDs/narratives, credentials or per-case labels enter Git. Existing provisional AI policy-table labels remain provisional. Final exact-head local/hosted evidence is maintained on #31/#32.

Stop only the owned console process when finished; verify the port owner/process command before termination. Use [F4 trial commands](isolated-trials.md) to remove only the selected trial. Keep service/volume state needed by other trials. For an incompatible application schema, preserve private evidence/backups and use an explicit migration/new trial rather than silently overwriting DDL.

[Source walkthrough](code-study-olist-console.md) · [Original workflow](olist-workflow.md) · [Build history](../BUILD_BOOK.md#entry-29--exact-action-approval-behind-a-scoped-local-console)
