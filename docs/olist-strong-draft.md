# Olist independent field scoring and stronger cohort draft

Unmerged implementation on `codex/o8-domain-evaluation`, based on main `2cc25047`.
Refs #33. Preparation only: no provider allowance, evaluation result or release approval.

## Observable fields

The new `olist_support.field_evaluation.score_fields` compares observed intent and requested
amount, action, receipt amount, actual workflow reason, truthful confirmation, exact order /
ledger / original-run budget state, duplicate delivery and controlled recovery separately.
It uses frozen evaluator-only labels and the independent state constructor, never runtime
`policy.propose`. Runtime agreement is a test consistency check, not label generation.

New `FreshRow.workflow_result` captures the reason actually returned. Older rows without it
remain unknown for reason; copying their expected reason would manufacture evidence. The old
aggregate report and capture inventory are unchanged. `to_standard_row` projects individual
verified rows into the shared standards contract, omitting unknown fields. Its caller must
first verify the capture inventory/receipt binding. It is not an H10 recording adapter or a
freshness attestation. Full H10 journaling and study/protocol sealing remain required.

`execute_trial(..., interrupt_after_commit=True)` raises a controlled evaluator exception at
the business store's after-commit hook. It collects committed state, closes/reopens durable
components and resumes with a planner that refuses another invocation. The collector retains
committed/resumed state, then tests duplicate delivery separately. The field scorer checks
all snapshots against independently expected state. A requested interruption that never
occurs records an explicit error. Required recovery without observations stays unknown.
This exercises a controlled exception and connection reopen, not OS kill, host loss or all
infrastructure failure modes. Ordinary non-fault rows explicitly mark recovery not applicable.

## Approved draft scope

The user authorized twelve cases from the existing pinned Olist/SIM source mix. The private
packet `release-o8-strong-draft-v2` excludes all eighteen groups in the three prior cohorts.
Six new order groups supply two related variants each; each group and manually assigned
language family stays in one split. Each partition has four cases and two source groups.
Twelve distinct constructed texts replace the prior four repeated templates. Manual family
assignments still require semantic-overlap review; distinct text alone proves no independence.

There are four proposed full refunds and eight proposed reviews. Constructed payment totals
of 99.99 / 100.00 / 100.01 SIM exercise cap boundaries. Partial amounts, reship requests,
missing confirmation/prior-refund facts, future confirmation/events, conflicting delivery,
an injection and one controlled recovery case exercise separate failure modes. Payment
aggregates are explicitly edited fictional totals, not currency conversions. The sealed
source DB is unchanged; source-local timezone/original currency remain unverified.

`cohort_draft.prepare(database, pin, output, excluded_groups=...)` requires an external, new
directory and nonempty prior-group exclusions. Load each prior `PolicyCases` file and union
its `entry.group_id` values; pass the independently retained source DB SHA-256. Selection
uses a versioned hash seed and visible canceled/paid/undelivered source rows. Literal policy
table judgments are authored before output and stay AI-provisional. Provider inputs contain
only opaque case identity and constructed text. Source facts and intended intent/amount never
enter that projection. The initial unreviewed v1 draft had an overbroad structured input
export; it is retained locally and superseded by v2. Neither was dispatched.

Private packet contents:

- `cases.md`: review facts and record independent decisions before opening labels.
- `proposed-labels.md` and `evaluator.json`: separate AI-provisional judgments.
- `inputs.json`: text-only model projection; `metadata.json`: fault/slice/family assignments.
- `pins.json`: exact evaluator/input/metadata byte pins, plus zero-call preparation status.

The user accepted all twelve proposed labels on 2026-10-24 and clarified that approval covers
labels only. The private acceptance sidecar binds that decision to the exact evaluator byte
pin. It records review of AI propositions, not independent blind annotation; original AI
label provenance remains intact. PR approval/merge, baseline/threshold decisions, provider
calls and release are not authorized by that acceptance.

No raw order IDs, original reviews, addresses or source facts belong in a public PR. The
packet stays outside Git. The draft is not an executed/frozen release study and has only two
holdout groups. Expand representative coverage and review source/family independence before
freezing a final study. Baseline selection, thresholds and a new bounded provider allowance
remain separate decisions. The previous 36-call cap is spent.

## Verification and remaining work

Focused tests mutate reason, scope, missing observations and recovery snapshots. The draft
test checks grouping, cap boundaries, literal-label/runtime consistency and text-only export.
Real SQL collector tests cover both rules and invented model responses with an after-commit
interruption, one ledger effect and no second model invocation. Actual final commands/results
are recorded on the review PR after completion. No live Langfuse dataset mutation occurred.

All five agents retain the shared #98 standards. Their domain adapters, reviewed labels,
representative cohorts and final evidence still need agent-specific work. This Olist addition
does not complete #33 or unblock dependent release/deployment issues.
