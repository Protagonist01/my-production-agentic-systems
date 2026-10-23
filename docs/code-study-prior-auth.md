# Prior-auth: source custody, labels and criterion support

Scope: P1–P3 branch `codex/p1-p2-p3-prior-auth`, started from merged main `1e59722`,
October 23, 2026. Inspected implementation commit: `0e5953cd4dbb36512452b11d766e769301f2d188`
(clean at candidate freeze); this chapter's later documentation changes do not change candidate code.
The implementation is merged/verified through [PR #92](https://github.com/Protagonist01/my-production-agentic-systems/pull/92).
P4 workflows, P5 UI and P6 release are excluded. No production clinical claim is made.

`prepare.main` loads independent manifest-file byte pins, then `prepare` validates external
source custody before parsing. `source.ccda_narratives` hashes the same buffer opened as ZIP,
bounds expansion, rejects duplicate/path-traversal/encrypted entries and XML DTD/entities,
and extracts section narratives without the header demographics. Oversized narratives are
omitted and counts are explicit. `cms_policy` isolates the selected national-policy prose;
`compile_policy` requires exact known section anchors and stores source quote offsets.

The contracts split note input from evaluator labels. `NoteInput` contains text, its digest,
service date, policy pin and provenance. Its closed schema rejects hidden expected decisions.
`EvaluationCase` separately contains family/split membership and AI-provisional expected
criterion/disposition labels. `validate_cohort` rejects duplicate case IDs, cross-split note
duplicates and edits without a same-family parent. The candidate receives a detached NoteInput,
never this evaluator object.

`redact` uses explicit reviewed spans and replaces each character with a mask while preserving
newlines and offsets. It validates exact source text and rejects overlapping spans.
`segments` splits long C-CDA narrative lines into bounded exact units. No automatic general
PHI discovery is claimed. A new note source needs a reviewed identifier mapping before dispatch.

`retrieve` is a term-based recall stage. Its candidate spans and the entire redacted note
enter `candidate.extract`, which sends one structured request per criterion through an injected
ModelGateway. Invalid responses, provider errors and wrong criterion IDs fail closed. The
CLI constructs the existing bounded gateway rather than calling Gemini directly, with one
attempt per criterion and one shared run budget/deadline across cases.

`check_claim` verifies quote identity first, then checks meaning with narrow explicit rules:
units and thresholds for AHI/RDI, event requirements for studies shorter than two hours,
positive permitted studies and documented evaluation/education/order. A model cannot choose
the policy or thresholds. Scanning the full visible note for supported contradiction patterns
prevents cherry-picking one positive span while hiding a separately explicit negative.
Unknown paraphrases remain insufficient, a conservative recall limitation. These checks do
not establish source truth, clinical suitability or general medical entailment.

`assess` revalidates contracts and binds case/policy/date before aggregating. Stale policy,
unsupported request scope and invalid model output route to qualified review. Missing support
requests information. All-supported evidence produces evidence complete for review, never an
authorization. `score` compares to separate labels and counts missing results in the full
denominator. The CLI records model completion separately so abstention after a provider failure
cannot appear as successful model reasoning.

The first frozen held-out evaluation completed 42 fresh requests, matching all six provisional
case labels and 42 criterion labels. No provider error or unsupported met state was observed.
The [runbook](prior-auth-evidence.md) preserves the failed development v1/v2 results and
the [aggregate packet](data/prior-auth-p1-p3-evidence.json) records exact pins. Local full
regression passed 881 tests; the isolated installed base wheel prepared the same source/policy
without a Google SDK or network access. A few synthetic families cannot establish production
quality; clinical adjudication is absent.

## Follow an invented case through the code

Start with a permitted synthetic note containing `CPAP education was not completed.` and a
separate positive education statement. The CLI validates policy/cohort byte pins before it
loads the model route, and creates a fresh run with one shared call budget and deadline.
It detaches only `NoteInput` from the evaluator case. At
[`extract`](https://github.com/Protagonist01/my-production-agentic-systems/blob/0e5953cd4dbb36512452b11d766e769301f2d188/projects/prior-auth/src/prior_auth/candidate.py#L42),
case, tenant and policy hashes must match the run context. An empty retrieval yields an
insufficient claim without dispatch; a nonempty retrieval allows one structured model call.

Suppose the model returns the positive quote and `met`. The model supplies text, not offsets.
[`matching_spans`](https://github.com/Protagonist01/my-production-agentic-systems/blob/0e5953cd4dbb36512452b11d766e769301f2d188/projects/prior-auth/src/prior_auth/source.py#L118)
finds every exact occurrence, including overlaps, capped at four per quote. This avoids the
v1 offset error and v2 duplicate-quote abstention without choosing an arbitrary occurrence.
An absent quote, fifth occurrence or typed response error aborts the candidate and records
its phase. This is a Python Unicode character offset; it is not a UTF-8 byte offset.

[`check_claim`](https://github.com/Protagonist01/my-production-agentic-systems/blob/0e5953cd4dbb36512452b11d766e769301f2d188/projects/prior-auth/src/prior_auth/assessment.py#L132)
checks each span against the exact note. It rejects masked evidence and an omitted negative
prefix, then checks the criterion's narrow grammar. Even a supported positive education quote
cannot hide the explicit negative elsewhere in this example: the full visible-note scan
returns conflict. `assess` routes that conflict to qualified review. Missing criteria request
information; stale policy, wrong scope or missing candidate also prevent evidence completion.

[`score`](https://github.com/Protagonist01/my-production-agentic-systems/blob/0e5953cd4dbb36512452b11d766e769301f2d188/projects/prior-auth/src/prior_auth/evaluation.py#L71)
binds result identity/pins to the independent evaluator case and compares all seven states plus
the final disposition. A missing model result contributes zero correct criteria to a denominator
of seven. The CLI writes raw exchanges and per-case diagnostics only to external private paths;
the committed aggregate includes counts and hashes. No external clinical action follows.

## Evidence and limits to keep visible

- **Verified development bugs, corrected before freeze:** model-generated offsets failed length
  validation; the next uniqueness guard rejected valid repeated quotes. Exact quote alignment
  retaining every bounded context replaces both. Regressions cover invented/over-repeated
  quotes and repeated positive/negative contexts in `tests/test_prior_auth.py`.
- **Design limitation:** support checks recognize a narrow English grammar. Unknown or subtly
  qualified medical wording can abstain or escape the represented negation patterns. Exact
  citations are necessary but do not establish general medical entailment. Qualified review
  and broader independently adjudicated cases are needed before expanding the scope.
- **Design limitation:** `validate_labels` checks completeness, exact expected quotes and
  disposition consistency. It cannot prove clinical label truth. The held-out split separates
  source families, but uses related edited templates and AI-provisional labels.
- **Privacy scope:** explicit reviewed spans preserve offsets; this is not automatic PHI
  detection. The CLI accepts already reviewed permitted illustrative content. A production
  ingress/redaction policy and protected reviewer service are unimplemented P4/P5 work.
- **Not assessed:** clinical utility, real patient data, full coding catalogs, local payer rules,
  general medical entailment and production authorization. This chapter is a focused execution
  walkthrough, not an exhaustive security or clinical audit.

The focused tests exercise Unicode redaction, hidden-label rejection, threshold units,
short-study counts, source pins/XML entities, conflicting statements, policy/date/scope pins,
quote alignment, no-evidence zero dispatch and grouped evaluator consistency. Existing harness
tests cover shared admission and process deadlines; no live provider is called by CI.

Interview exercise: explain why a correct quote is insufficient evidence of criterion support.
Trace a negated education statement through exact citation validation and explicit-negative
support checks; then trace an uncited contradictory statement in another line. Discuss which
paraphrases the grammar misses, how a development error may justify changing it, and why
fitting the final holdout would invalidate the reported evidence.
