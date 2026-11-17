# Code study: the final demo regression and local reference process

Inspected branch: `codex/prior-auth-local-closeout-20261116`, based on merged1e1b8fe.
This chapter covers root regression/reference-service helpers and their tests.
Build Book Entry116 records decisions and actual setup failures. The frozen clinical
packages, complete-citation prompt, earlier provider captures and ledger are unchanged.

Trace `Witness` → `source` → `imported` → `prepare` → deliberately positive `Claim`
→ `assess` → declared-reference comparison. The input dataclass carries no expected
state/route. The separate map provides software-test expectations, never clinical
gold. Three changed-note cases retain both facts in the document but cite only one
half of the adult/test/order requirement. Exact source occurrence passes integrity;
the unchanged checker still returns insufficient support. This distinguishes quote
identity from entailment, without claiming general medical reasoning.

`source` serializes selected C-CDA/FHIR narratives with an ignored header canary.
`prepare` checks source and normalized hashes, trusted relevance/subject/policy
bindings and explicit redactions. A rejected input returns no note. The SQL witness
then requires no canonical case for it; accepted inputs go through the durable worker
and source cards, with no new work on restart. Root reports count19mechanical cases;
companion SQL, crash, PDF/OCR and real-provider witnesses have separate denominators.

`run` compares all seven states and the disposition instead of just counting the
number of met findings. It exposes each actual/expected result, keeps every scheduled
case and labels no-model-quality/no-clinical-validation. The tests pin input/reference
manifests independently. This is an exposed authored regression suite, not a fresh
held-out clinical cohort or a valid estimate of model injection robustness.

Follow `build` in `prior_auth_reference_service.py`: verify the upstream commit and
unchanged server/library/license bytes, refuse an existing output record, then build
the minimal pinned-image container. No app key or case data enters that build context.
`start` validates the exact local image revision label and checkout-owned name/labels;
it checks binding, mounts and network mode before adopting any existing container.
Only a verified stopped owned container can restart. Port occupancy causes refusal,
not termination of an unrelated process. New containers publish only to loopback.

Readiness checks actual FHIR metadata from the independent Java service, bounded by
eight minutes. A failed/exited service remains inspectable; nothing deletes or resets
its container. Its H2 state is transient, so the application journal's consumed/unknown
history must survive it. The launcher does not call submit/inquire and cannot create
a clinical approval. Those effects remain under the existing scoped operator desk.

**Design limits:** immutable base/source IDs do not freeze remote Maven dependencies
at a historical point; record the resulting image ID. Docker containment trusts its
daemon/kernel. The reference is not a commercial insurer. **Not established:** broad
live-model quality, clinical reference qualification or remote-host recovery.

Interview exercise: an exact quotation is incomplete, a patient binding is wrong,
and the payer restarts after a received submission. Explain which boundary refuses
each case and why no model vote or fresh journal is allowed to erase uncertainty.

The November 17 local HTTP witness exercised the real saved version-3 case against
the packaged Java payer: received submission, identical repeated receipt, correlated
A3 inquiry and logout refusal. Read-only journal inspection found one attempt,
packet and inquiry. No note text was exported and no provider attempt was consumed.
Its first eight-minute readiness check timed out under memory pressure; retained
logs show startup completed in about 795 seconds. Treat this as an operational
limit rather than dropping the timeout or reporting a response-time target met.
