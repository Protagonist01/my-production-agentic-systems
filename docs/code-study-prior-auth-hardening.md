# Code study: local recovery and parser containment

Inspected scope is the unmerged `codex/prior-auth-demo-hardening` branch based on
merged651ff2a. Runtime clinical packages and provider history remain unchanged.
Build Book Entry113 records the design and the owner's Gemini-only/local decision.
This chapter covers root recovery/isolation and their operator integration; passing
unit checks alone do not establish actual Docker/SQL behavior.

`prior_auth_recovery.capture` first verifies explicit quiescence, private bundle
manifest/source and owned source trial. It locks the complete three-schema inventory,
checks its binding against the canonical intake case, and captures binary COPY data
in foreign-key order. Schema identity includes columns/defaults/constraints/indexes/
functions/triggers. SQLite's backup API supplies a consistent journal file; views/
triggers and incomplete desk inventories are refused. Both database and journal are
private data, never tool logs. Copying the live journal as a raw file was rejected
because it can lose WAL-backed changes.

`restore` accepts an external digest and requires a different owned target with no
PA schemas, plus new file paths. It decodes bounded pinned bytes before SQL effects,
bootstraps original schema/grants, checks exact PostgreSQL build/schema/inventory,
copies parent tables before foreign-key children and compares every row. It revokes
sessions only after comparison. Unknown attempts and payer receipts stay unknown;
restore must never resend or reconcile them implicitly. It publishes journal/bundle
before SQL commit and leaves a visible partial target on failure. This is an explicit
same-build local mechanism; it is not encrypted distributed backup or a measured
host-loss recovery guarantee. Trusted callers must stop all writers before capture.

`prior_auth_parser_isolation.command` constructs fixed Docker flags from an exact
image ID and random owned name. There are no mounts; stdin carries only bounded
document bytes and a closed format. The parent monitors bounded output/deadline,
validates returned Document pins and removes that one container after normal/deadline
exit. Killing only a Docker client would leave daemon work running, so cleanup is
separate. Daemon loss can still leave unknown state and is not reported as success.

The image reuses `prior_auth_documents.normalize` unchanged. It has native tools and
minimal hash-locked Pydantic dependencies, no keys or app database. `prepare` accepts
an explicit trusted normalizer; the authenticated operator selects either isolated
image or original native-tool configuration, never both. Authorization happens before
document access/parser execution. The parent still checks normalization pins and
extraction review; containment does not make OCR or clinical interpretation correct.

Tests exercise restore login/citation/unknown effects and actual container network/
root-write denial, seccomp/capabilities/cgroup limits, PDF/OCR and forced deadline
cleanup. The hosted Postgres job builds and checks the container, then runs SQL
recovery witnesses. Its timeout increases to25minutes to accommodate image building;
no assertion, audit or fault check is removed. No model evaluator, key, paid call or
release criterion is activated by these changes.

Interview exercise: a model reservation exists with no settlement and a payer POST
has unknown outcome when the machine stops. After restore, explain why both must
remain uncertain and why logging in again is required. Then explain why a network-
disabled container is a meaningful boundary but not a proof against kernel escape.
