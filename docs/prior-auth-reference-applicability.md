# Prior Auth clinical-reference applicability audit

Metadata/source-method audit, November13,2026. No new benchmark task corpus, gated
clinical record or external judge was downloaded or executed. This audit does not
change the running owner-approved constructed study or its proposed labels. Keep
all eight required clinical fields and slices; an uncovered cell remains uncovered.

## What the sources can establish

| Source | Evidence it can support | What this audit has not established |
| --- | --- | --- |
| CMS NCD240.4v3 | Authoritative national coverage prose and applicability dates | Patient-level evidence labels or a qualified translation of every clinical phrase |
| CMS LCD L33718 | Local coverage definitions, explicit short-study counts, contractor applicability | Automatic authority to replace our national-policy compilation or every plan's rules |
| CMS provider-compliance example | Agency-authored example of insufficient sleep-test documentation | A seven-criterion initial-CPAP gold case or representative qualification cohort |
| Synthea | Published illustrative synthetic document/source families | Independently qualified patient-level CPAP annotations |
| Accepted authored fact method | Inspectable predicate boundaries on supplied constructed facts | Natural-note fact truth, representative patient independence or clinical qualification |
| MedNLI | A candidate independent clinical-entailment reference, subject to its access/use terms | Access permission, Free-provider export permission or CPAP-policy coverage |
| NLI4CT | A candidate clinical-trial entailment reference | Direct applicability to patient CPAP evidence or all eight required fields |
| HealthAdminBench | Expert-designed administrative workflows with explicit state and rubric checks | Qualified CPAP criterion labels for our notes or a validated substitute clinical judge |
| CHI-Bench | A candidate provider/payer workflow reference with separate task/content identity | Gated data/handbook access, compatible use rights, CPAP applicability or judge qualification |

The original CMS, Synthea and authored-fact rows are current development/source evidence.
The newly identified examples and benchmarks are research candidates. None has been
silently promoted into the clinical label set.

The [CMS provider-compliance example](https://www.cms.gov/training-education/medicare-learning-networkr-mln/compliance/medicare-provider-compliance-tips/cpap-devices-accessories)
is a useful narrow candidate: the agency describes missing sleep-test documentation
and the resulting documentation error. Its example bills a bi-level device, however;
that overall payment outcome must not become the gold disposition for our narrower
initial-CPAP assistant. At most, a reviewed mapping could support the missing-document
concept. It does not supply qualified states for the remaining criteria or solve the
representative-cohort requirement. No new reference label or provider input was added.

## Two newer workflow candidates

[HealthAdminBench](https://github.com/som-shahlab/health-admin-bench/tree/b88844c8c3e42af717742d795b2c100e646b9b2b)
was inspected at commitb88844c8c3e42af717742d795b2c100e646b9b2b. Its
[paper](https://arxiv.org/abs/2604.09937) describes expert-defined synthetic healthcare
administration tasks. The repository separates deterministic state checks from
LLM-judge rubrics. Its
[scoring preregistration](https://github.com/som-shahlab/health-admin-bench/blob/b88844c8c3e42af717742d795b2c100e646b9b2b/scoring_preregistration.md)
explicitly distinguishes failed checks, infrastructure failures and missing evaluation
rows, and warns against selecting a favorable rubric. Its v2/v3 inventories differ.

This is relevant to document gathering, submission, halt decisions, durable notes and
RFI workflows. That is an applicability inference, not a completed evaluation. A
repository Apache2.0 license is not by itself an audit of every bundled asset or
proof of clinical annotation validity. We did not open task JSONs, visit/log into
its hosted payer portals, run a judge or send our notes to those systems. Separate
workflow-state evidence from the semantic judgment portions before considering reuse.

[CHI-Bench](https://github.com/actava-ai/chi-bench/tree/9d5a48277d4f5867e70e171d9a670d4c1bd19b5a)
was inspected at commit9d5a48277d4f5867e70e171d9a670d4c1bd19b5a; the associated
[paper v4](https://arxiv.org/abs/2605.16679v4) is dated October29,2026. It covers
provider prior authorization, payer utilization management and care management.
The current README requires separately gated task fixtures and a gated managed-care
handbook. Its prescribed judge/simulator configuration also uses providers outside
the current Gemini study grant. No such provider was activated.

Its runtime/version labels and content identities are separate, and documented local
task repairs can change the evaluated fixture bytes. This reinforces our need for
explicit source hashes and isolation of development edits. It does not establish
that any uninspected task gives correct labels for our seven CPAP criteria. A future
import needs actual permitted access, asset-level use terms, an applicability matrix,
grader provenance and separate study authorization. No task outputs or headline scores
were imported into our evaluation.

## Clinical interpretation details to resolve

[CMS L33718](https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=33718)
uses different denominators for AHI and RDI and constrains which respiratory events
count. Therefore a future reference should record measure, unit, sleep/recording
interval, event definition, test method and policy applicability, not just an isolated
number. It should distinguish two measurements from one study, observations across
different studies, and genuinely competing values.

Our constructed fact table has a generic `recorded_events` field and controlled note
wording. It does not qualify the clinical meaning of that count or its relationship
to every reported rate/duration. For a clinical cohort, check derivational consistency
and explicitly identify deliberate conflicts; do not manufacture clinical truth by
combining ambiguous counts, rounded rates and unmatched time intervals. Preserve the
running development packet and report this limitation instead of changing labels
after seeing model outputs.

The local30/10event explanation must stay a separate proposal from the national
short-study interpretation until its applicability/method is accepted. Likewise do
not invent a rounding convention for fractional values between14and15. An exact
quote proves text identity; it cannot settle these clinical/policy judgments.

## Concrete acceptance path

1. Keep executable source/state/arithmetic/privacy/recovery witnesses separate from
   semantic qualification. Retain their actual outputs and failure cases.
2. For each required clinical field/slice, identify a permitted independent reference
   and explain why the reference represents that exact judgment. Record unresolved
   coverage rather than counting a broad healthcare benchmark name as a match.
3. If using a separate evaluator, qualify it against those independent references,
   blinded to candidate answers. Freeze its prompt/version/limits and measure its
   false-positive, false-negative and abstention behavior with uncertainty. AI consensus
   without independently grounded references is still not qualification.
4. Freeze the final application cohort and risk-owner acceptance limits before new
   qualification outputs. Keep source families/edits in one split. Repetitions increase
   stability evidence; they do not create new independent patient groups.
5. Evaluate the unchanged assistive application scope across all required fields and
   slices, including unsupported-met containment and useful completion. A passing
   workflow benchmark or a successful reference-payer HTTP exchange cannot waive
   missing clinical evidence or authorize production release.

This is the route toward an external-reference alternative to recruiting reviewers
for every new label. Access, applicability and evaluator qualification still have to
be demonstrated; this audit supplies no shortcut approval.
