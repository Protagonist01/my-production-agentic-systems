# Requested-amount source research for Olist

Inspected2026-11-08 on `codex/olist-amount-reference-audit`, from verified main
`874579b` (#141). The executable census was frozen at `884b88b` before opening the
complete archive. This chapter covers the root research adapter, its invented tests,
two actual ABCD inventories and a historical Bitext source discovery. It does not
establish semantic references, a release cohort or model quality.

[Aggregate measurements and exact source pins](data/olist-amount-source-research-v1.json)
contain no customer messages. Private files retain source bytes, annotation positions,
hashes, operator scripts and execution receipts. Existing studies, labels and acceptance
history remain intact. No provider request was made; the read-only shared ledger remains
447consumed/0unsettled/1stop. The old study expired2026-11-07T01:37:23Z. Its remaining
bound slots are not available for another experiment.

## What has to be proved

The requested-amount field asks what amount, if any, the customer requests in the
actual input. A payment price, later action amount, status-query amount or source-policy
default answers a different question. Agreement between two numbers cannot prove that
role. An unknown reference must not become a no-amount label just because parsing failed.

The existing first delexed customer turn remains the input convention. Do not append
later dialogue, restore hidden original values or expose evaluator annotations to make a
source label fit. A separately proposed standalone-turn population would need its own
input/reference applicability decision and exposure/group accounting.

## Actual ABCD census

The [pinned publisher repository](https://github.com/asappresearch/abcd/tree/6b8700ce67c6b37b062dd7a60abc76d7ef832a97)
supplies conversation-level scenarios, original/delexed turns, an action ontology and
guidelines. `offer-refund` takes an amount; its refund-initiation guideline permits a
default50 when the customer does not know it. Neither an action argument nor equality
to50 establishes a requested amount in the first customer turn.

| Measured item | Count | Meaning |
|---|---:|---|
| Native conversations |10,042|Complete pinned archive, not selected cases|
| `offer-refund` annotations |826|788conversations; train663/dev90/test73|
| Supported numeric arguments |785|41remain unparseable/unsupported, not null labels|
| First delexed currency-value matches |2|Literal value witnesses, no semantic validation|
| Those matches also containing `refund`/`money back` |0|Narrow word check, not a language classifier|
| First original numeric matches |10|Original data cannot fill hidden delexed inputs|
| Equality to applicable policy default50 |2|Does not prove that the default was used|
| Accepted requested-amount labels |0|No role authority is manufactured|

The census retains all826annotations, including unsupported values, source exposure,
visibility mismatches and repeated first texts. Some flags overlap:132annotations share
first text across native splits;53match a known exposed first text and7belong to known
exposed source IDs. These are annotation counts, not independent customer counts.

A separate pre-action customer-turn scan found19original and7delexed currency/refund
co-occurrences. Its additional restrictive filter—one currency value, direct adjacent
refund wording, no basic ambiguity marker and the same source-policy flow—found zero
original witnesses. This is a lexical opportunity scan, not proof that every possible
amount expression or all later utterances are unusable. It selects no cohort and changes
no input. Number words, other currencies and semantic paraphrases are outside this parser.

## Follow the implementation

[`amount_source_research.py`](../amount_source_research.py) is a separate root module.
Adding it inside the frozen harness/Olist packages would change historical runtime
inventories and prevent strict readback. `dev.py` and mypy explicitly check this new file;
the runtime packages and lockfile stay unchanged.

1. `audit_amount_source` checks separately trusted archive/ontology/guideline hashes,
   the exact one-amount ontology and the known default-policy text. The supplied pins
   remain a trust boundary: the function cannot authenticate who approved a source.
2. Bound compressed bytes to64MiB and expansion to512MiB. Reject duplicate JSON fields,
   nonfinite constants, changed split inventory and repeated native conversation IDs.
   The full expanded JSON still lives in memory; this is not a streaming untrusted-data
   service or an exhaustive parser-hardening audit.
3. `_record_frames` locates the exact first delexed customer turn, checks original/delexed
   role/length alignment, then inventories every native refund action. Preserve whether
   the action occurs after that turn. Hash source records, text, arguments and spans;
   do not include raw source text or scenarios in the output contracts.
4. `_amount` accepts bounded unsigned decimal/cents forms and valid comma groups, without
   rounding. `money_witnesses` requires a dollar/USD marker. `_numbers` is a broader
   numeric comparison used only for original/later visibility diagnostics.
5. Compare each action value separately with visible money, original numbers and earlier
   original customer turns. Future turns cannot provide pre-action support. Retain
   multiple money values, negation and default equality without choosing a money role.
6. Link normalized first text across every native record, including non-refund records,
   before adding cross-split flags. `summarize` revalidates the typed audit and counts
   observations. All frames keep `requested_role_validated=false` and
   `accepted_reference=false`; the audit cannot authorize a cohort, call or release.

For an invented message `I paid $100; please refund $25.`, a native action value100
matches one visible value. The report preserves both100and25 and flags multiple values.
It never converts that numeric agreement into a requested100label. For a message with
only `Please refund <amount>.`, a hidden original25stays a visibility diagnostic.

### Reproduce from trusted private inputs

In a configured workspace, import `audit_amount_source` and supply the original archive,
ontology and guideline bytes with their external SHA-256 pins, plus the complete pinned
`ExposureIndex`. Serialize its canonical audit privately and publish only `summarize`.
The frozen operator script/plan and exact hashes are in
`D:/document/.cache/production-agents/olist/amount-source-census-2026-11-08-v1`.
Use a new exclusive output directory; do not overwrite or rerun an existing study.

The actual module hash is
`2faf76a4363696c57279c69d7d2f172967a2bd62c5b65028c4c17cf440e9ab30`.
The supplementary script and its restrictive filter are preserved separately under
`amount-source-opportunities-2026-11-08-v1`. Both are source research, not trial captures.

## Historical Bitext entity-tagged lead

The [publisher's dataset page](https://www.bitext.com/dataset-community/) describes
tagged synthetic training/evaluation data. Its two relevant GitHub links returned404
during this research. A file remains available from the official Hugging Face account
at [revision9bea5fa](https://huggingface.co/datasets/bitext/Bitext-customer-support-llm-chatbot-training-dataset/tree/9bea5faf42b8732ca8c347a80f0b5777486a18e1).
This is a different version from the already accepted27Kintent-development source.

The actual CSV has4,514rows and11columns, including instruction, intent, entity value
and offsets. Its63`refund_amount` rows all have `get_refund` intent. The historical
README's different row counts conflict; actual bytes determine this inventory.

| Mechanical check over all63amount rows | Count |
|---|---:|
| Exact entity text at zero-based, end-exclusive offsets |20|
| Exact match with any other tested conventional offset interpretation |0|
| Zero-based/end-exclusive offsets outside message bounds |16|
| Native value equals any supported currency lexeme in the message |36|
| Native value matches no supported currency lexeme |27|
| Distinct native values |5|
| Distinct normalized messages / number-masked templates |63/32|

These checks use the declared literal parser; an unmatched value does not by itself prove
that no amount was expressed. Different checks overlap. Template counts are a dependence
warning, not authenticated independent-family counts. More seriously, inspection found
a native entity value inconsistent with the visible number, and payment-price wording
among the amount-tagged instructions. Exact offsets alone cannot certify requested-money
meaning. No text/value is automatically repaired or accepted.

The pinned tree contains README, CSV and `.gitattributes`, with no explicit license file
or license declaration in its README. Licensing for this exact historical version remains
unresolved; do not inherit permission from a newer dataset card or an unofficial mirror.
There are no native split/generator-family columns. Public availability also cannot prove
absence from a model's training data.

Private discovery files and the reproducible metadata script live under
`D:/document/.cache/production-agents/olist/bitext-amount-source-discovery-2026-11-08-v1`.
Five inspected discovery messages have a separate exposure receipt; they must not later
be presented as unseen cases. No new source method or reference label has been accepted.
This does not reverse the existing limited intent-development approval.

## Next evidence work and decision boundaries

Keep ABCD action amounts and these historical Bitext entity values outside qualification
references. A usable alternative needs exact-version usage permission, utterance-level
intent/amount-role applicability, preserved unknowns, visible-input alignment, source
exposure and grouped independence checks. Repairing annotations with our own model and
then scoring that model against the repairs would not supply independent truth.

The accepted closed-language development grammar remains available for executable
amount/state/confirmation tests. It does not certify natural-language meaning. Where
applicable external references remain unavailable, the accepted v2 design permits a
separately qualified evaluator; its own representative reference test and accepted
uncertainty bounds must precede its use. Model agreement is insufficient.

The next qualification proposal must name the actual references/evaluator, all eight
required fields/slices, complete three-comparator denominators and prospective confidence
rules. Source/method decisions, a frozen cohort, provider scope and release acceptance are
distinct; this inventory supplies none of those permissions. Deployment/recovery work can
use invented fixtures and independently checked state, while host-loss RPO/RTO still need
an actual host and measured restore evidence. No weaker scope or release claim follows.

## Verification, defects and discussion prompts

[`tests/test_amount_source_research.py`](../tests/test_amount_source_research.py) has30
invented checks: exact spans/hash roundtrip, payment/request ambiguity, default equality,
hidden and future information, exposure linkage through non-action records, unsupported
money, malformed decimal fragments, negation, changed policy/pins and false acceptance
flags. The focused run passed30; mypy passed231sources. Full hosted checks and the
post-merge run must verify the final submitted tree before delivery is accepted.

**Verified and fixed lexer bug:** the first draft missed `$25.` because it treated terminal
punctuation as a decimal continuation. A focused regression now preserves sentence
punctuation while refusing malformed fractional/thousands fragments. **Observed source
defects:** historical tagged offsets/value mismatches are preserved; source labels were
not repaired. **Design limits:** lexical completeness, provenance of supplied exposure,
semantic role and true family independence remain unproved. This is not a general security
review or an end-to-end model evaluation.

The first census operator invocation failed before source execution because a script under
`artifacts` could not import the root module. Its failure log is preserved separately; the
successful invocation added the repository root to its path without changing frozen source
bytes. A discovery helper also failed to serialize tuple-keyed diagnostic counts; the
subsequent successful metadata inventory uses ordinary JSON field names. Neither failure
was a provider attempt or a benchmark result.

For an engineering discussion: why is a refund-action amount not a requested amount?
Trace the invented100/25example, then explain why zero labels after a complete census is a
useful result. A strong answer distinguishes task applicability, numerical consistency,
semantic truth, exposure and independence; shows the saved failures; and names the new
evidence needed before qualification. An offline exercise is to add a later customer25
to a first message with no amount: later-match diagnostics may change, while first-input
support and semantic acceptance must not.
