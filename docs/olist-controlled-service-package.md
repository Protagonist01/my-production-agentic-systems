# Constructed references in the customer-confirmed service evaluator

Continue from verified main `1d20801` and the owner-accepted
[constructed reference method](olist-controlled-field-references.md). This preparation
carries the exact twelve messages and meanings through the existing service manifest,
policy table, customer/reviewer script model and state scorer. It does not turn the
development references into a qualification cohort or authorize provider calls.

## Reference loading and explicit wire format

[`controlled_service_reference.py`](../projects/olist-support/src/olist_support/controlled_service_reference.py)
adds `ControlledServiceReference`, version `olist-controlled-service-reference-v1`.
It retains the original ControlledReference, including spec, exact input, amount roles,
span offsets and historical proposal flags. Its text and expected-plan properties expose
the service evaluator's existing interface without reformatting `SIM 99.99` or changing
the older suffix-only RoutingReference contract. No method-acceptance flag in the original
proposal is rewritten.

`bind_accepted` checks the actual raw owner-acceptance, method and reference files against
three separately fixed pins, verifies the development scope and reconstructs all twelve
original meanings. Appended whitespace, reordered/replaced references and stale bytes
refuse. Wrapper membership is restricted to these twelve accepted examples; accepting the
method does not silently approve an expanded numeric cohort. Standalone wrapper tags are
documentary provenance, not authenticated owner identity. A study must still verify its
entire prepared package, source bindings and authority before admitting observations.

RoutingCase opts into this new version explicitly. Controlled references require synthetic
provenance, development split, the original conservative group, declared family and original
reference-file pin. They cannot be relabelled as hybrid source evidence or fresh holdout.
Old routing/stress reference bytes and validators remain intact; StressDraft explicitly
refuses the new service wrapper. Existing service composition fingerprints already bind
every Olist Python/SQL source, including the two new modules.

## Eighteen dependent preparation scenarios

[`controlled_service_package.py`](../projects/olist-support/src/olist_support/controlled_service_package.py)
builds wholly fictional canceled/visible/confirmed-undelivered orders, each paid 100.00 SIM,
with no prior refund. Each of five original parent groups has one fictional order. These
are test fixtures, not actual customer/order associations or added source records. The
independently written policy table validates conditional expected effects when RoutingCase
is constructed. Workflow reasons remain explicit preparation declarations.

| Scenarios | Meaning and scripted actors | Count |
|---|---|---:|
| Original twelve | Original accepted messages; customer withholds consent | 12 |
| Exact customer choice | At-cap numeric refund and unspecified full-payment refund; confirm 100.00 SIM | 2 |
| Separate staff approval | At-cap request; reviewer approves, customer confirms 100.00 SIM | 1 |
| Staff rejection | At-cap request; reviewer rejects despite scripted customer willingness | 1 |
| Different customer amount | At-cap request; customer script specifies 99.99 SIM | 1 |
| Response-loss recovery | At-cap request; confirm 100.00 SIM, interrupt after commit, reconstruct reader | 1 |

Four scenarios expect a committed refund conditional on their scripts. One requires
after-commit recovery. All variants retain their source/parent/order links; five declared
connected groups remain five, not eighteen independent cases. Scripts are mechanism inputs,
not real customer consent or independent semantic labels. All original twelve withholding
scenarios expect no effect even when a policy proposal would otherwise be eligible.

All payment totals are 100.00 SIM. The 99.99 SIM request is therefore a partial request;
the 100.01 SIM request differs from the full payment before a cap predicate could admit it.
This packet does not claim separate below/above-payment-cap, missing/conflicting facts,
prompt injection or natural-language coverage. Existing stress/operational evidence covers
other mechanisms separately and must not be silently merged into an independent denominator.

## Scoring, empty comparisons and authority boundaries

The unchanged service scorer compares original intent and requested amount separately
from policy action, exact SQL state, proposal isolation, customer authority, audit,
duplicates and recovery. A wrong model-like refund proposal withheld by a scripted
customer can pass state safety while failing semantic correctness. A customer script
does not retrospectively make that original prediction correct.

Preparation round-trips every scenario through `service_h10.eval_case/private_scenario`.
Only the exact original AgentInput reaches the candidate; source labels, acceptance pins,
policy expectations and actor scripts stay evaluator-side, following the
[Langfuse input/expected-output/metadata separation](https://langfuse.com/academy/datasets).
No live dataset is uploaded. `ControlledServicePackage.reconstruct` independently rebuilds
the declared fixtures/scripts and refuses changed or missing scenarios.

The private diagnostic plan binds three fake-only candidate/rules/always-review composition
pins and three trial IDs: **18 x 3 x 3 = 162 descriptive rows**, all initially missing.
These are completeness denominators, not budget reservations, dispatched attempts or
measured 0% model accuracy. No candidate or baseline quality result is produced by compilation.
The [aggregate](data/olist-controlled-service-preparation-v1.json) marks every release,
qualification, independence and provider-freeze claim false.

## Verification and reproducibility

The private packet is
`D:/document/.cache/production-agents/olist/controlled-service-preparation-2026-11-04-v1`.
It contains package, manifest, separate inputs, fake comparator specs, preparation protocol,
complete missing-row plan, read-only ledger status and byte pins. From the matching checkout:

```powershell
.venv\Scripts\python.exe D:\document\.cache\production-agents\olist\controlled-service-preparation-2026-11-04-v1\reproduce.py --verify
```

The original method/reference files used CRLF; their raw hashes are authoritative. Portable
test fixtures reconstruct those exact bytes explicitly, rather than weakening the loader
by normalizing an incoming file. The owner receipt used LF and remains a separate immutable
record. A source/host change must be represented in a future preparation/freeze, not
silently accepted under a different set of hashes.

Unit tests exercise byte-pin refusal, all eighteen input/manifest round-trips, dependent
grouping, distinct script/eligibility denominators, altered fixtures, unaccepted amounts,
incomplete/reordered sets, old-format refusal and the selected scenario's tenant binding.
Real-SQL tests use invented gateway decisions on original accepted messages: exact commit,
prefix/partial review, wrong amount/intent with consent withheld and after-commit recovery.
A three-trial H10 mock recording/readback checks the new reference format and owned cleanup.
These are mechanism tests, not actual generation or qualification results. Actual outcomes
and required PR/main acceptance are recorded in the delivery note after verification.

Future release work still needs an applicable accepted qualification-reference/sampling
method, a complete frozen service/provider package and selected-host readiness, separately
approved attempt allocation and fresh results under unchanged gates. The old stopped
experiment is never resumed or edited. No keys or allowance changes are needed here;
read-only accounting remains 447/614, zero unsettled and one original stop as last checked.
