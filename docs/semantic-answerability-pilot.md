# Revenue semantic answerability pilot

The user authorized up to24of the existing shared180GeminiFreeattempts on2026-10-27:
12short, family-separated original CUAD contracts, publisher labels hidden from Gemini,
no paid fallback and failures included in the cap. Preparation selects six answerable and
six no-answer questions from source development only. Each inferred family contributes
one case; four calibration/eight validation cases have two trials each. All108families
from the earlier citation studies are excluded. Original source holdout and labels stay intact.

The [implementation](../projects/revenue-integrity/src/revenue_integrity/semantic_pilot.py)
accepts only original context/question for its model projection. It has no target-store API,
business tools, payment or invoice effects. It asks whether the document explicitly answers
the question: accept/reject/abstain, with literal source quotations required for accept.
No-answer judgments require full context rather than a snippet selected using hidden answers.
The output parser checks schema, route and literal quotations; that does not independently
prove the quotation supports an interpretation. Publisher-relative answerability is the
reference task; general legal meaning and normalized billing terms are outside its scope.

Prepared contexts are at most11,930characters. Categories cover ten publisher clause types;
trivial Document Name, Parties, Agreement Date and Effective Date are excluded. Selection is
balanced short-context/hash convenience sampling, not representative production traffic.
Original public references may be in model training. A twelve-family pilot cannot establish
production uncertainty or validate all categories; existing human/qualified release gates
remain active. No model judge becomes qualified through schema compliance or model agreement.

The pilot code/configuration, inputs, separate targets, two-trial schedule and explicit
diagnostic limits must be frozen before dispatch. The single shared durable180allowance
remains authoritative; an additional pilot stop permits at most24newattempts. Failures and
unknown dispatches count; no row retries, fallback, reset or cache. Use owned spawned workers
with60second parent bounds and capture raw response/accounting and process timing. Keep
unknown cost unknown; Free admission is not verified zero billing. The existing private
configuration identifies the authorized credential route; a local credential-scope hash
is not a provider-verified cloud-project identity or billing audit.

Raw contracts, labels, responses, credential/ledger identity and provider request IDs stay
private. Publish only reviewed aggregates/pins, complete scheduled denominators and actual
limits. Report calibration and validation separately and keep every missing/failed/abstained
row. Final actual capture/hosted acceptance is recorded only after execution. Current
preparation and tests do not claim a provider result or authorize a domain release.

## Actual frozen capture and independent audit

Executable `1fd39f5e25da03b577eb0d5b87ab639efd6828fa` and the complete harness/Revenue source
inventory were frozen before the24row schedule. The shared ledger is initialized once at
the private `gemini-closure-180-v1` location recorded in AGENTS. Its consumed reservations
must never be reset. All24attempts settled, none were retried, no fallback was selected and
no source/evaluator code changed during capture. There are156remaining shared attempts.
Groq remains9/12invented-only with three remaining; it was not used here.

The [safe aggregate](data/semantic-answerability-pilot-v1.json) binds plan/dataset/protocol/
study/report and code inventory hashes. Independent offline readback checks every scheduled
request/context, persisted response, ledger settlement, controlled call, gateway exchange,
parser decision and final report. It finds:

| Partition | Scheduled | Reference matches | Failed validation | Decision coverage | Conditional accuracy |
| --- | ---: | ---: | ---: | ---: | ---: |
| Calibration:4families ×2trials | 8 | 6 | 0 | 100% | 75% |
| Validation:8families ×2trials | 16 | 13 | 2 | 87.5% | 92.86% |

Scheduled validation accuracy is81.25%, not92.86%; the latter excludes failed decisions.
The validation acceptable class has five accepts, one rejection and two unresolved rows;
the no-answer class has eight correct rejections. No model abstentions, missing rows,
transport failures or observed false accepts occurred. Calibration has two reference-relative
false rejections in one family. The tiny sample and selected public labels do not establish
the absence of false accepts in production.

The result **fails qualification** for accuracy, coverage, reference-relative false rejection,
group/class sample size and uncertainty. Two of eight validation families have at least one
wrong/failed repeat; its group-error upper bound is59.07%. Repeated rows are not independent
groups. Proposed95%accuracy/5%group-uncertainty limits and72group floors are diagnostic
objectives, not accepted production thresholds.

Raw provider counts total39,716input and842output tokens, with both components known for
all24attempts. All24raw monetary costs are unknown. No price-derived zero cost or verified
zero billing is claimed; the configured Free-project attestation is an operator declaration.
Raw process timing, inputs, outputs, provider request IDs and credentials remain private.

## Error analysis without a new call or changed label

Two failed validation rows concern one License Grant case. Submitted quotes match only
after whitespace normalization, not literally; the frozen parser correctly retains them
as invalid. This diagnostic is not a successful rescore or proof of semantic support.
Preserve original outputs/references and failed rows. A future whitespace-alignment method
would need a new version that maps to exact original spans, independent tests and its own
evidence; do not silently relax the old literal requirement.

Both trials of one Minimum Commitment case reject a publisher-answerable question; one
Expiration Date validation trial also rejects an answerable question. These are disagreements
relative to publisher annotations, not newly adjudicated legal errors. No label was changed
to agree with the model, and no prompt or threshold was tuned using validation outputs.

The next appropriate work is a separate evidence-supported error review and prospective
candidate/evaluator changes. The approved24attempt pilot is complete; it cannot rerun rows
or spend further attempts merely because156remain. Legacy release gates stay blocked.
