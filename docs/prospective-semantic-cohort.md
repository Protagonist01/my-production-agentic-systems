# Prospective semantic cohort: prepared, not dispatched

2026-10-27, branch `codex/prospective-semantic-cohort` against verified maine432655.
This advances #33/#45/#60preparation after the failed original semantic pilot and exposed
parser diagnostic. No new provider attempt, review-method acceptance or release occurs.

## Implementation and trust boundary

[`prospective_semantics.py`](../projects/revenue-integrity/src/revenue_integrity/prospective_semantics.py)
separates a private exposure inventory, selection policy, publisher-labelled cohort and
two-trial schedule. `ExposureRecord` carries prior inferred family, exact source-context
hash and optional provider-request hash. Source identity and evidence pointers bind each
inventory to its prepared source manifest. These pointers are trusted provenance inputs;
they do not discover unrecorded exposure, authenticate annotations or prove unseen training.
Long historical documents outside the pilot request limit retain context/family exclusions
without manufacturing a supported provider-request hash.

`prepare_prospective` revalidates inputs, rejects empty/duplicate/cross-source exposure
inventories and duplicate source cases, then checks publisher case identities and literal
reference spans. It considers source-development originals only, excludes trivial document/
party/date categories and applies the declared context/category limits before selection.
Prior families, exact contexts and provider-request matches all exclude a candidate. Chosen
families/contexts/requests immediately enter the exclusion sets, preventing duplicate new
documents from inflating independence even with distinct case/family IDs. Semantic near-
duplicate detection and correct issuer/template inference remain outside this mechanism.

Selection is deterministic case-hash order, six answerable/six no-answer references,
at most two cases per category. First two examples of each class become calibration; the
remaining four per class form prospective validation. Targets remain unchanged and private.
The dataset binds each reference/input plus family/context independence keys. The frozen
schedule contains exactly24requests:12cases ×2trials. Bundle revalidation detects case,
class/split, input/reference, source-family and schedule substitutions. It remains a private
preparation artifact and must never be passed wholesale to a provider.

The existing model prompt/route are unchanged; only opt-in parser v2is selected for a future
run. Both v1/v2may be reported against the same future raw responses without extra model
calls, provided that comparison is frozen in advance. Diagnostic quotation integrity still
does not establish semantic support. There is no live runner, implicit dispatch, model judge
activation, automatic baseline/threshold approval or release integration in this module.

## Actual preparation and exclusions

Recheck original manifest `b852424ab854c30bd730ccc90a799907e02d3875a3066d203aed36f842f78540`
and its two database byte pins. Construct four private exposure inventories from:

1. the first24family citation-integrity probe;
2. the separate84family citation-integrity study;
3. the12family semantic pilot;
4. the earlier12item original-Revenue reviewer packet, whose families overlap the union.

Original study plan/dataset and semantic report pins are verified against published safe
aggregates; the reviewer packet inventory is verified against its retained independent pin.
Exact input bundles reconstruct known context hashes. The union excludes120inferred families.
This covers these inspected artifacts; it is not a claim of complete organization-wide or
model-training exposure knowledge. Other historical sources must be added if discovered.

The [safe preparation aggregate](data/prospective-semantic-cohort-v2.json) records12new source-
development families/contexts, four calibration/eight validation cases, six answers/six
no-answers, eight categories and at most11,770context characters. The categories are Affiliate
License-Licensee, Cap On Liability, Governing Law, License Grant, Liquidated Damages,
No-Solicit Of Customers, Revenue/Profit Sharing and Source Code Escrow. No source text, original
IDs or expected per-case labels are published. No model has run on this prepared cohort.

The private cohort, source inventory, four exposure inventories, selection policy, schedule,
allowance snapshot and forecast are saved exclusively at
`D:/document/.cache/production-agents/revenue/prospective-semantic-cohort-2026-10-27-v2`.
Hashes of57previous artifact files remain unchanged. Original corpus splits/holdout,
reviewer packet, publisher labels and failed original semantic results are preserved.
Existing raw source databases stay read-only. Preparation has no provider SDK/credential use.

## Exact budget and uncertainty feasibility

Read the single authoritative shared ledger recorded in AGENTS:24of180consumed,156remaining,
0unsettled. A declared snapshot and exact12×2×1×1×(1+0)forecast gives24attempts. It fits the
remaining arithmetic but `dispatch_allowed` and `release_allowed`stayfalse. It neither extends
the completed first pilot's24attempt authorization nor reserves funds or creates a new ledger.
Groq remains9/12invented-only and is not a domain-review resource under that permission.

There is a material confidence/budget limit. Under the existing **proposed diagnostic**
two-sided95%zero-error upper-bound objective of5%, each reference class needs at least72
independent validation groups. Two classes therefore require at least144validation families.
With four additional calibration families and two trials each, the minimum is296attempts:
140more than the remaining156, before comparators, model judges, live faults or failures.
The oversized forecast correctly refuses. This calculation assumes independent/comparable
groups and zero observed errors; it is not an accepted production risk limit or a claim
that296attempts would guarantee qualification. Nonzero failures can require more evidence.

The prepared24attempt follow-up could test prospective parser behavior and semantic
answerability diagnostics, but cannot satisfy the stated production-quality objectives.
Do not spend remaining attempts on an implied release study or silently lower error/coverage
requirements to make the arithmetic fit. The product/risk owner must eventually accept
applicable limits; a concrete additional evidence/data/budget proposal must precede an
unaffordable capture. Lowering repetitions changes the protocol and the reliability claim.

## Verification and next decision

Tests use invented sources to verify balanced/unique selection, exact schedule/reference
pins, separate family/context/request exclusion, cross-source/duplicate inventory refusals,
missing/invalid source data, exhausted eligible populations and tampered frozen bundles.
The configured repository type/import/build checks cover packaging boundaries. No tests
fabricate a qualified human review or production threshold. Study artifacts remain private;
publication checks must screen source identifiers/quotes and both configured credentials.

Before any prospective capture, revalidate cohort/exposure/source pins and authoritative
remaining allowance, freeze the actual executable/prompt/parser/reporting protocol and
obtain the applicable new experiment scope. No per-case expected labels, split identities
or publisher answers go to the model. Use one reservation per attempt, retain failures,
and no automatic retries/fallback. The next capture would be a small diagnostic, explicitly
separate from final release acceptance. Human/qualified legacy gates remain unchanged.

[Build Book Entry64](../BUILD_BOOK.md#entry-64--freeze-a-prospective-cohort-without-recycling-exposed-families)
records the actual implementation/debugging sequence. Final exact-head hosted and postmerge
acceptance is recorded on the PR after it completes.
