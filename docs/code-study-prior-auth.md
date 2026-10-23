# Prior-auth: source custody, labels and criterion support

Scope: P1–P3 branch `codex/p1-p2-p3-prior-auth`, started from merged main `1e59722`,
October 23, 2026. This chapter describes in-progress source preparation and evidence assessment.
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

The initial live development probe completed seven real Gemini requests with all seven
invented criteria supported. Deterministic tests cover privacy/citation/threshold/integrity
mechanisms. A separate six-development/six-held-out provisional cohort is frozen. Its results,
errors and actual source pins belong in the runbook and Build Book after execution. A few
synthetic families cannot establish production quality; clinical adjudication is absent.

Interview exercise: explain why a correct quote is insufficient evidence of criterion support.
Trace a negated education statement through exact citation validation and explicit-negative
support checks; then trace an uncited contradictory statement in another line. Discuss which
paraphrases the grammar misses, how a development error may justify changing it, and why
fitting the final holdout would invalidate the reported evidence.
