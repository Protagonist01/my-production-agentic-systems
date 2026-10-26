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
