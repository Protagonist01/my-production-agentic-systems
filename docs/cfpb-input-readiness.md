# CFPB input preparation with mapping decisions pending

On 2026-11-11 the owner explicitly chose **continue preparation; mappings remain pending**
after PR149. This continuation makes the existing 12-case private draft easier to use
correctly later. It does not run a classifier, score the proposed meanings or request more
source records. Issue #38 remains open, including its dependency on #33.

## What is complete

The private original draft remains unchanged at
`D:/document/.cache/production-agents/cfpb/scope-mapping-draft-2026-11-11-v1`.
Its externally recorded manifest hash is
`cd7a8fd8bb081405bc7b2bc83a5859d3aca75956f98c0d8ecaa3b0e30918c954`.

The new private packet is
`D:/document/.cache/production-agents/cfpb/scope-input-readiness-2026-11-11-v1`, with manifest
`7d6d2c08579f69669283f6bc3df6bd67579cba7ed69ede5dcf68496c2d8788b5`.
Preparation and separate-process readback both passed with zero Python socket/DNS attempts.
The [aggregate receipt](data/cfpb-input-readiness-v1.json) publishes counts, hashes and
readiness status only. Source utterances, individual text identities and proposals stay private.

| File | Purpose and permitted content |
|---|---|
| `inputs.json` | Exactly the existing `ComplaintInput` fields: `schema_version`, text-hash `case_id`, and unchanged `narrative`. No publisher label, proposed scope, grouping, source name or expected output. |
| `evaluator-only.json` | Private source/publisher records and pending proposals, linked to the input identity. Project partition stays unset; `qualified_reference` is false. |
| `readiness.json` | Integrity passed, but execution/export/qualification/release authorization is false. Trial count, partitions, candidate requests and operating limits remain null. |
| `manifest.json` | External draft pin, exact preparation/contract source pins and artifact hashes. It is custody metadata, not model-study authorization. |

This isolates fields by role; possession of `inputs.json` is not permission to send it to a
provider. Text hashes are identities, not a guarantee that source content is anonymous.
No original draft file was edited, accepted or repartitioned. No active Langfuse dataset,
SDK client, model gateway, API key loader or provider dispatcher is involved.

## Reproduce and verify

Install the existing locked workspace with `python dev.py setup`. Use private paths outside
Git. An output directory must be new; a complete or partial earlier packet is not overwritten.

```powershell
python docs/evaluation/prepare_cfpb_input_packet.py prepare --draft D:/private/cfpb/draft --draft-sha256 SOURCE_MANIFEST_HASH --output D:/private/cfpb/new-input-packet
python docs/evaluation/prepare_cfpb_input_packet.py verify --draft D:/private/cfpb/draft --draft-sha256 SOURCE_MANIFEST_HASH --output D:/private/cfpb/new-input-packet --packet-sha256 PRINTED_PACKET_MANIFEST_HASH
```

`project` checks the external source hash and exact source-file inventory. It hashes a
single byte snapshot of each file before parsing; a later reread cannot silently substitute
different bytes. It rejects duplicate JSON keys, invalid paths, missing/changed files,
non-training selected records, duplicate identities, accepted proposals and filled target
fields. It preserves each narrative byte-for-byte through UTF-8 text serialization. The
original intent, uncertainty and rationale never enter `ComplaintInput`.

The verifier reconstructs both projections from the pinned draft, validates the exact
input keys/contracts and compares every readiness field. Rehashing a tampered packet does
not make leaked labels, trial assignments or new authority legitimate. Tests exercise those
cases, wrong source pins, attempted source-test substitution and overwrite refusal. The
focused preparation/developer-command run passed 22 tests. Hosted final-head and merged-main
checks are recorded in the PR rather than inferred from a local checkpoint.

The four preparation source pins cover this helper, the input/base contracts and unchanged
dependency lock. They are not the future classifier/scorer/prompt/taxonomy inventory. A new
checkout with different source bytes can correctly refuse the old packet; preserve the
pinned bytes or make a separate fresh packet. Hash verification demonstrates custody and
consistency, not semantic correctness or protection from an entirely compromised host.

## What still blocks execution and release

Input integrity is complete; the record deliberately reports `blocked_for_execution`.
The outstanding decisions/evidence are:

1. Review and accept or correct the development scope mappings. They remain proposals.
2. Establish applicable semantic references for product/issue, urgency, ambiguity and
   evidence relevance. Publisher intent names and model agreement alone do not supply them.
3. Approve a representative cohort and source/parent/template groups, preserving a fresh
   evaluation partition. These twelve exposed training examples are not that cohort.
4. Freeze the taxonomy, policy, candidate/scorer/request/source/environment pins and the
   sample-size, repetition, risk/coverage, latency and cost plan. None is inferred here.
5. Authorize a bounded fresh provider scope on the existing shared ledger, retaining old
   failures and stopped/bound slots. The old stopped study is not resumed by preparation.
6. Obtain actual accepted-work and rework observations for any human-effort/value claim.
   Invented timing cannot become observed savings.
7. Satisfy dependency #33 and the remaining #38 validation, shadow, recovery and release gates.

No trial count or new attempt estimate is invented merely to populate a plan. A later
approval needs a new bound decision/study artifact; do not edit this packet's false flags or
the original draft to manufacture readiness. The current packet remains a historical
preparation result even if a later approved study proceeds.
