# Instruction-level Olist reference preparation

Prepared 2026-11-03 from verified main `ffc03b4`. This adds a reproducible source adapter
and a concrete reference-method proposal for #33. The accepted ABCD/Olist benchmark,
historical labels and original stopped study remain intact. The
[aggregate inventory](data/olist-utterance-reference-v1.json) contains no source messages.

## Why use a second reference unit

The ABCD audit found latent status goals paired with first messages about addresses or
prices, and latent refund goals paired with an unwanted-item complaint. A word anchor
or whole-dialogue goal cannot settle the exact visible request. The 12 exposed training
witnesses now have separate AI-provisional applicability proposals; three remain unresolved.
No source annotation or earlier owner acceptance is rewritten.

The [Bitext publisher card](https://huggingface.co/datasets/bitext/Bitext-customer-support-llm-chatbot-training-dataset/blob/430d1a89bd93bd1fa23c16f29dd53e73f0087443/README.md)
describes individual instruction/intent pairs, hybrid synthetic NLP/NLG generation,
automated labeling and linguist curation. It declares CDLA-Sharing-1.0; the
[license text](https://cdla.dev/sharing-1-0/) governs data use/publication. This preparation
keeps raw data private and publishes aggregate findings, not a redistributed corpus.
Publisher curation is provenance, not a guarantee that every label fits this application.

## Actual source audit

The private CSV was downloaded at revision
`430d1a89bd93bd1fa23c16f29dd53e73f0087443`. Its 19,202,474 bytes match the separately
published LFS SHA-256 `6f81102b0100b97b8468eb04368033a23206bf1fde9d53500d5806ec1001a434`.
It has 26,872 rows, five native fields and 27 intents. The displayed card taxonomy omits
some actual CSV labels, so source coverage comes from the pinned CSV rather than that list.

| Native label | Native rows | Proposed Olist route |
|---|---:|---|
| get_refund | 997 | refund |
| track_order | 995 | status |
| track_refund | 998 | unsupported |
| check_refund_policy | 997 | unsupported |
| change_shipping_address | 973 | unsupported |
| recover_password | 995 | unsupported |

The adapter proposes only these six mappings; all other native intents remain unmapped.
After excluding known research-text exposures, there are 991 refund, 989 status and 3,950
unsupported intent proposals. They are neither accepted gold nor a frozen study cohort.
The 12 selected witnesses expose 25 rows through duplicate text. Existing ABCD exposure
files are not edited; a separate combined preparation index records these known exposures.
The caller-supplied index cannot authenticate the completeness of project exposure history.

Exact normalization produces 24,274 text buckets and zero conflicting native-label buckets
in this source. Slot/number normalization produces 23,827 lexical buckets. None of these
counts establishes correct semantics, author independence, representative traffic or
absence from foundation-model training. No seed/author IDs or native splits are supplied.
No project partitions or confidence claim are created for this new source.

## Follow the code

`utterance_reference.audit_csv(raw, expected_sha256, source_revision, exposure)` checks
the external raw-byte pin and 32 MiB limit, exact ordered five-column schema, row/field
bounds and nonempty content. It retains every row, including unmapped/exposed/conflicting
rows, with source revision, ordinal and a hash of all original fields. The native response
is included in that binding but is not copied into the artifact or candidate input.

`UtteranceFrame.input` contains only the unchanged instruction in AgentInput. Native intent,
category, flags, proposed mapping and missing-reference status stay outside it. Validators
refuse hidden observations, mismatched projections, foreign/reordered source rows and
fabricated mapping/gold/independence/provider-freeze/release flags. `verify` recomputes the
whole artifact from pinned source/exposure bytes; validating a hand-built object alone
does not authenticate a publisher or an approval.

Amount and coarse intent need different evidence. All 26,872 rows lack an established
requested-amount reference, and 6,670 contain unresolved source placeholders. V2 therefore
keeps **intent exclusions** separate from **full-service reference blockers**. An order-ID
placeholder need not invalidate a publisher's coarse tracking intent; it cannot silently
be replaced or supply a numeric SIM amount. Slot-free text also does not prove that
requested_minor should be null. The initial unmerged V1 prototype blanket-excluded slots;
its separate private artifact/source pin is preserved and final V2 refuses that old schema.

No native reship or clarification class is present. Do not reinterpret change_order as
reship, fill missing amount labels with null, or inherit original-label authority after
editing placeholders. Keep those fields/slices unresolved until they have a supported
reference method. Existing independent SIM policy and observed state/authority/recovery
checks remain useful conditional on their supplied inputs.

## Reproduce and review

```powershell
python -m olist_support.utterance_reference --source <private-pinned.csv> --source-sha256 <external-lfs-pin> --source-revision <pinned-revision> --exposure <private-index.json> --exposure-sha256 <canonical-index-pin> --output <new-private-directory>
```

The module installs the existing network-denial hook, refuses symlink inputs or outputs
inside a Git checkout, requires a new private output directory and prints only aggregates.
It writes audit.json, summary.json and an external audit pin. No provider configuration,
live Langfuse dataset, model transport or allowance mutation is part of this adapter.

The private 12-item source/mapping proposal, source card/metadata/LFS tree, CSV and exposure
pins are at `D:/document/.cache/production-agents/olist/reference-method-proposal-2026-11-03-v1`.
The final actual adapter run is at `utterance-reference-audit-2026-11-03-v2` under the same
cache. The owner must accept a concrete reference substitution method before release use;
this implementation does not modify legacy Review kinds, `_reviewed` or release thresholds.
Input/reference/metadata separation follows [Langfuse's dataset guide](https://langfuse.com/academy/datasets).

Interview exercise: explain why 995 native tracking labels can be useful for intent work
while all those rows still lack complete service reference fields. Show how a placeholder,
a missing annotation, a duplicate and an approval each require a different check.
