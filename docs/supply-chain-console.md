# Supply operations console (S5)

This unmerged S5 implementation provides a loopback SIM workbench with provisioned operator,
reviewer, confirmer and viewer accounts. Notices are durable in-app message previews only.
There is no freight adapter, external notification sender or production release acceptance.
S6 remains behind the pending Olist release gate.

Install the workspace development dependencies with `uv sync --locked --all-packages`.
Use an existing isolated local-service workspace with a copy of `compose.yaml`, initialized
by `bootstrap`, which creates its private configuration automatically. Keep that workspace outside Git.

```powershell
python -m supply_chain.console_cli --root D:/private/supply --trial supply-demo bootstrap
python -m supply_chain.console_cli --root D:/private/supply --trial supply-demo seed-demo --tenant demo --event incident --clock 2026-10-23T12:00:00+00:00
python -m supply_chain.console_cli --root D:/private/supply --trial supply-demo account --principal D:/private/operator.json
python -m supply_chain.console_cli --root D:/private/supply --trial supply-demo serve --port 8877
```

Run these commands in the installed workspace environment (`uv run --locked` or its Python).
The seed clock must be explicit and current for action eligibility. Seed enrollment never
resets an existing incident. The four invented shipments have delays of 1, 4, 12 and 8 hours;
the last has missing facts. Their observations expire after 30 minutes.

An account document has this shape. Provision separate accounts and actor IDs for each role;
the CLI prompts for a password without placing it in shell arguments.

```json
{"username":"demo-operator","tenant_id":"demo","actor_id":"operator","role":"operator","scopes":[{"event_id":"incident","shipment_ids":["incident-shipment-1","incident-shipment-2","incident-shipment-3","incident-shipment-4"]}]}
```

Open `http://127.0.0.1:8877`. Assessment may commit eligible actions at or below 25.00 SIM.
Actions above that amount require approval of their exact fingerprint by a different reviewer,
then an operator applies the approved proposal. A confirmer records SIM acceptance or failure.
Neither operation confirms shipment delivery. Refresh reconciles proposal/confirmation expiry.
Debits survive failures and timeouts. The policy permits 100.00 SIM/action, 500.00 SIM/incident,
30-minute approval/confirmation windows and two incident-wide stale proposal supersessions.

Each account receives only its incident/shipment notices. Marking one read affects that
account only. Notices retain capture timestamps; old pending notices are historical evidence,
not the current shipment state. The table is the current state. Duplicate refreshes reuse
notice IDs. If a notice write fails after a commit, refresh reconstructs it from the receipt;
retrying an action cannot create a second debit for the same incident/shipment.

Optional context is provisioned with `context --input D:/private/context.json`. Invented
context is labeled invented. Real context requires `source_kind: s1-public-observation`,
`--source-directory`, `--manifest-sha`, `--alert-key` and an explicit aware `--clock`.
The command replaces supplied alert content with the hash-verified S1 public reader result.
Stale/unavailable alerts are refused; later expiry is shown in the UI. This independent alert
context establishes no weather-to-shipment causal relationship and cannot override shipment
fact eligibility.

Accounts use hashed passwords, opaque hashed 30-minute sessions, CSRF and same-origin checks.
Runtime credentials cannot provision accounts or delete notices. Session disable/scope changes
are checked on every request. HTTP cookies are appropriate only for this loopback entrypoint;
remote hosting, production identity, carrier confirmations, retention/archival and outbound
delivery require separate release work.

Verify with `pytest tests/test_supply_console.py`,
`pytest -o addopts='' tests/integration/test_supply_console_state.py` and
`node tests/supply_console_session_test.cjs`. SQL tests require Docker. See the
[code study chapter](code-study-supply-console.md) for the trust and recovery boundaries.
