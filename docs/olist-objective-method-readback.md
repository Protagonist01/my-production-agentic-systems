# Objective service readback into the method audit

Prepared 2026-11-06 from verified main `894a573` (#140). This adapter connects the
accepted Olist evidence-method design to existing deterministic development captures.
It adds no metric, runtime behavior, label approval, qualification grant or release command.

## Why a separate verifier

[service_method_readback.py](../service_method_readback.py) lives outside the two frozen
runtime packages. Their complete Python/SQL inventories are bound into each recorded
candidate. Adding this adapter inside either package would change that inventory and
make the unchanged domain reader correctly refuse the old recording. The root adapter
has its own source hash and runs from the repository checkout; it is not added to an
agent wheel. Normal `dev.py` lint, formatting and mypy checks include it.

`read_method_evidence` takes a private artifact directory, the original `LoadedManifest`,
route, comparator selection, separately trusted baseline/candidate pins and an aware
readback clock. It accepts no serialized proof report or preverified object. It calls
the unchanged `service_h10.read_comparator`, which verifies the sealed journal, exact
schedule, canonical captures, observed output and recomputed scores, while retaining
the complete frozen-runtime check. The interpreter/platform must still match the capture.
This adapter supports development comparator records only; provider recordings and other
runtime versions need their own explicit reader rather than a bypass.

## Claims this reader can establish

| Existing score | Accepted objective part | What remains separate |
| --- | --- | --- |
| `truthful_confirmation` | `message_consistency` through `fixed_template` | Customer intent and whether an action should have been requested |
| `exact_state` | `authoritative_state` through `state_observation` | Independent semantic validity of the frozen expected effect |
| `duplicate_delivery` | `repeated_effect` through `state_observation` | Useful completion and other release requirements |
| `recovery` | Observation only in this adapter | A response-loss witness does not establish process death, host restore or the required crash/restart slice |

These are reference-relative checks performed by the existing independent domain scorer,
not a second implementation of that scorer. Frozen references, recorded state collection
and capture provenance remain trust inputs. A passing state check cannot validate language
or authenticate an observer. No external identity or production database is authenticated
by reading a local capture.

Project each actual input and full service scenario into a `MethodCase`. Preserve its
development split and actual manifest slices. Include declared reference, group, language,
order and normalized-input connections; these conservative keys are not authenticated
independent samples. Do not manufacture a holdout or crash/restart tag.

`ObjectiveFact` retains all three scheduled trial IDs, full row hashes and values for each
case/field. Any false value makes the part contradicted. If no trial is false but one is
unknown, the part is unresolved. Only three true values support the part. The reader
refuses missing/duplicate terminal identities and non-boolean numeric objective values.
It preserves existing scorer failures as unknown rather than treating them as passes.

The report binds the original manifest, complete baseline, candidate, captured interval,
check time and evaluator. The evaluator pin hashes the separate adapter's actual bytes
together with the captured domain-scorer pin. Exact byte/platform bindings are intentional;
an adapter or runtime change needs new verification rather than reuse of an old grant.

## Separate scope authority

With no scopes, the public API returns facts and **no claims or verified claim pins**.
The caller must obtain any scopes and their trusted hashes from a separate control plane.
Never build the trusted set from scopes in an untrusted evidence submission. There is no
public endpoint, grant registry or identity service implemented by this module.

For each supplied scope, `_claims` checks external admission, exact input/reference,
frozen source manifest/evaluator, field/part/method and slices. Those pins can be known
before execution. The finished baseline hash stays in the proof rather than in a grant
that must predate that baseline. The grant must cover the whole capture
interval and remain current at readback. Qualification scopes, semantic parts, recovery
claims, duplicate scopes and mismatched bindings are refused even if their hashes are
listed as trusted. This adapter creates development claims only.

`VerifiedObjectives.verified_claim_pins` includes contradicted/unresolved claims too, so
their disposition cannot be flipped while retaining the admitted hash. Feed these pins,
the unchanged cases/claims and separately admitted scopes into `audit_methods`; it still
requires the missing semantic parts, qualification holdouts and appropriate scope authority.
It never grants release. Serialized fact reports are review output, not reusable admission
inputs; actual artifacts must be checked again to produce another verified result.

## Actual development readback

The [v2 aggregate](data/olist-objective-method-readback-v2.json) records a new readback of the
two completed #140 baselines. No trial was rerun and no provider was called. Original
package and baseline pins match the earlier accepted preparation and sealed results.
The [first adapter's readback](data/olist-objective-method-readback-v1.json) is preserved
as history: its prospective grant source binding was corrected before merge. Neither
version supplied any actual scope or emitted a method claim.

| Per algorithm, over 18 scenarios and 54 trials | Rules | Always review |
| --- | ---: | ---: |
| Objective parts across the three supported fields | 54 | 54 |
| Supported objective parts | 50 | 50 |
| Contradicted objective parts | 4 | 4 |
| Response-loss observations, reported separately | 1 contradicted | 1 contradicted |
| Method claims emitted / qualification grants created | 0 / 0 | 0 / 0 |

Four exact-state parts fail because the unchanged baselines do not complete the expected
eligible effects. Passing confirmation/duplicate checks describes containment, not the
whole-service correctness that remained **0/54 for each algorithm**. Both response-loss
cases fail to exercise the expected completed recovery. No scopes were invented for
this readback. Five dependent groups and exposed constructed text remain development;
the missing 54 model rows and all qualification/release gaps remain unchanged.

## Verification and practice

The unit tests isolate projection, folding and scope logic with an explicitly invented
reader result and invented grants. They exercise supported/contradicted/unknown outcomes,
full interval and source bindings, semantic/recovery/qualification refusal, trusted-scope
separation, duplicate scopes and the unchanged method-audit gates. They are not actual
source authentication or SQL evidence.

The existing real PostgreSQL baseline integration tests additionally call this adapter
on actual three-trial service captures, then corrupt a capture's canonical bytes and
require readback to refuse. Hosted SQL and full delivery results are recorded only after
those checks actually finish. The private 108-row historical readback is a separate
completed check; it needs no running database or model credential.

Run `python -m pytest tests/test_service_method_readback.py tests/test_olist_evidence_methods.py -q`
in the locked environment. Full lint/type/format use `python dev.py check`; actual SQL
coverage uses `python dev.py db-check` on an isolated ready host. Do not change frozen
candidate sources to make an old recording readable.

Interview exercise: two trials pass and one fails, while another field has an unknown.
Explain both dispositions, which hash changes if a row changes, who supplies the grant,
and why all objective parts could pass while semantic qualification remains blocked.
[Build Book Entry89](../BUILD_BOOK.md#entry-89--connect-pinned-service-readback-to-objective-method-proofs)
records the implementation choices and failed fixtures.
