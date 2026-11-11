# CFPB baseline execution and next reference decision

Prepared 2026-11-11 from mainbf6426d (#146). These are actual executions of the unchanged
deterministic algorithms on the existing 16 exposed authored training examples. They are
not held-out model results, independent semantic truth, an adversarial service exercise,
accepted human work or release evidence. The full release issue #38 remains open, including
its dependency on #33. The shared provider stop remains intact.

## What ran

Run the fixed `routing_experiments.baseline` function for `rules` and `always_review`, three
times per case. Preserve case text, labels, training designation and 10 declared families.
All six variants remain in the full schedule: 16 × 6 × 3 = 288 slots. There are 96 actual
baseline outputs; the other 192 slots remain missing. Deterministic repetitions establish
repeatability of these inputs, not 48 independent families per comparator.

| Comparator | Observed / scheduled | Classified | Review required | Missing |
|---|---:|---:|---:|---:|
| Rules | 48 / 48 | 12 | 36 | 0 |
| Always review | 48 / 48 | 0 | 48 | 0 |
| TF-IDF/logistic regression | 0 / 48 | — | — | 48 |
| Cheap model only | 0 / 48 | — | — | 48 |
| Strong model only | 0 / 48 | — | — | 48 |
| Cheap-first cascade | 0 / 48 | — | — | 48 |

Against the pack's **constructed** references, rules have 18 unnecessary-review observations
and always-review 30. Both miss zero declared required reviews among their observed rows.
Rules assign the in-scope category to the negated unrelated example on all three trials:
one case/group, not three independent failures. Its action remains review-required, so this
is a scope false-positive, not an observed automatic rejection/refund/account operation.

Every observed baseline row has unknown evidence relevance, actual security effect and
monetary cost. An exactness flag emitted by the frozen lexical algorithm is preserved as
its own claim; this run adds no independent quote-relevance judgment. Consequently composite
success is not established for any observed row. That is not a finding that all 96 answers
are semantically wrong. Likewise, zero observed attacker-goal successes without effect
observations cannot establish attack resistance. No human savings or error-repair cost was
measured. Function-only timing is private diagnostic data, not service or human latency.

The result makes the trade-off concrete: rules reduce review routing relative to always-
review on this pack but still mishandle a negation at the scope field. Neither result tells
us whether the candidate models improve the trade-off, meet risk limits or save money.
The algorithms were not tuned after seeing these outputs.

## Reproduce and verify

The private run is at
`D:/document/.cache/production-agents/cfpb/diagnostic-baselines-2026-11-11-v1`.
Its externally recorded manifest pin is
`a7537ce1760b9c4a4636c7d888a359eb76f131858e3a32dd74c7faa691098e96`.
The [public aggregate](data/cfpb-diagnostic-baseline-results-v1.json) contains counts and
custody pins; full references/inputs/observations stay outside Git.

```powershell
python docs/evaluation/run_cfpb_diagnostic_baselines.py --output D:/private/cfpb/fresh-run
python docs/evaluation/read_cfpb_diagnostic_baselines.py --run D:/private/cfpb/fresh-run --manifest-sha256 HASH_PRINTED_BY_RUNNER
```

Install the unchanged locked workspace first with `python dev.py setup`. A fresh output
directory must not exist, and its parent must be private and outside Git. The runner pins
the harness/CFPB Python and SQL inventory, lock and both scripts before execution, then
rechecks source bytes afterward. Capture files are exclusive-create and fsynced. A Python
audit hook denies socket/DNS operations; observed network attempts were zero. No model
gateway is constructed and no key/configuration is loaded.

The separate reader checks the externally supplied manifest pin, every artifact/source
hash, exact case/variant/trial inventory, unchanged baseline outputs and complete metrics.
It independently counts routes and unknown effects. It shares the pinned scorer and
baseline implementation: this is custody/consistency verification, not a second financial
judge or cryptographic attestation against a fully compromised trusted host. Local timing
bytes make fresh captures different; old files are not replaced.

For this capture, exact source bytes are also preserved in the separate private
`diagnostic-baselines-2026-11-11-v1-source-snapshot` directory beside the run. Each copied
file was checked against the capture's pin. A fresh checkout with different line endings
can correctly refuse readback even at the same Git revision: use the pinned source bytes
or generate a new exclusive capture. Do not rewrite the old hashes to make a changed
checkout pass. This byte-custody safeguard does not add semantic validity.

Tests alter copies to remove a row, change a prediction, invent a known-safe effect, forge
a score and change the manifest pin. Another test recomputes a forged manifest and still
refuses a security field the algorithm never observed. Capture refuses an existing output.
The focused run passed 22 tests including developer-command wiring. Hosted final-head and
main delivery checks are recorded in the PR rather than presumed from this checkpoint.

## Why TF-IDF stays missing

Every case in this pack is marked `training`. Fitting vocabulary/IDF/coefficients and scoring
those same cases would not measure generalization. The implementation deliberately refuses
training/family/parent/text overlap. Do not change the split values to evade that guard.
The [scikit-learn evaluation guide](https://scikit-learn.org/stable/modules/cross_validation.html)
explains the separation between training, selection and final evaluation. A grouped
cross-validation method could be proposed, but it would still be exposed development and
needs its own explicit grouping/reference protocol. No such method was executed here.

## External reference applicability audit

Only README, license and intent-name metadata were fetched; no utterance file, source test
record, provider export or live Langfuse dataset was created. Exact revisions, paths, byte
hashes and retrieval URLs are in the [metadata manifest](data/cfpb-reference-metadata-v1.json).
The local copies remain in
`D:/document/.cache/production-agents/cfpb/reference-metadata-2026-11-11-v1`.

| Source | Verified metadata | Applicable role / unresolved mapping |
|---|---|---|
| CLINC150 at `828f8093932c8fe6ca7936c3d2e52903b1c523de` | 10 domains / 150 intent names; README describes English, crowdsourced, single-intent examples and separate train/validation/test data. Repository license declares CC BY 3.0. | Useful candidate material for unrelated-intent detection. Its original `oos` label means outside its own 150 intents, not outside CFPB complaint scope. Banking/card queries also need item-level workflow mapping. It does not establish urgency, multi-intent handling or injection resistance. |
| BANKING77 at `57ec275d8078af65b7731c2a98be812d844a6d6b` | 77 intent names; README reports 10,003 train / 3,080 test examples. README explicitly points dataset licensing to its CC BY 4.0 LICENSE. | Useful financial-topic and hard-negative candidates. `cancel_transfer`/`terminate_account` describe intents, not account-action authority. `compromised_card`/`transaction_charged_twice` alone cannot establish urgency, ongoing harm or the CFPB product/issue taxonomy. |

Primary sources: pinned [CLINC README](https://github.com/clinc/oos-eval/blob/828f8093932c8fe6ca7936c3d2e52903b1c523de/README.md)
and [license](https://github.com/clinc/oos-eval/blob/828f8093932c8fe6ca7936c3d2e52903b1c523de/LICENSE);
pinned [BANKING README](https://github.com/PolyAI-LDN/task-specific-datasets/blob/57ec275d8078af65b7731c2a98be812d844a6d6b/README.md)
and [license](https://github.com/PolyAI-LDN/task-specific-datasets/blob/57ec275d8078af65b7731c2a98be812d844a6d6b/LICENSE).
These are publisher declarations and an applicability audit, not blanket legal approval or
accepted project-label meanings. Retain attribution and identify derived mappings if used.

## Approved preparation — mapping review remains pending

Prepare a 12-example **training-split-only review draft**, preserving original labels and
split metadata: four CLINC non-financial intent examples, four banking operations/information
examples and four complaint-like banking examples. This is purposive diagnostic sampling,
not a representative population or qualification cohort. Keep source utterance/input separate
from publisher label, proposed CFPB scope mapping, mapping rationale and uncertainty. Preserve
entire source text for context, inspect masking, and do not open source test records.

Review item-level applicability before accepting any mapping. Do not equate an unsupported
financial request with an unrelated request, or a complaint-like intent with a supported
CFPB taxonomy pair. Items that cannot be mapped defensibly remain uncertain rather than
receiving fabricated gold labels. Risk/urgency/ambiguity meanings need separate applicable
evidence; these source annotations do not solve those fields. Existing authored adversarial
examples stay explicitly constructed.

The owner approved this preparation after seeing the concrete source mix/schema proposal.
The private 12-case review is now at
`D:/document/.cache/production-agents/cfpb/scope-mapping-draft-2026-11-11-v1/review.md`.
Original text/publisher labels, proposed mappings, provenance and license notices are bound
in its manifest. The [public preparation receipt](data/cfpb-mapping-draft-preparation-v1.json)
records aggregate counts and exact source pins without publishing utterances.

The proposals are four unrelated, three unsupported-operation/information and five
insufficient-context cases. One source sentence has a typo where its intent label suggests
PIN; the proposal retains uncertainty rather than silently repairing the input. Complaint-
like card examples lack facts needed for a supported product/issue pair. Product, issue,
priority and ambiguity targets remain unset, including when possible unauthorized access
is mentioned. These proposals are not executable in-scope reference labels or accepted gold.

CLINC distributes multiple splits in one JSON container. The preparer scans non-training
values as bytes, decodes/saves only `train`, and stops; source test records were not decoded
or selected. BANKING uses its separate training CSV. Original source Git blob identities
and SHA-256 hashes are checked/recorded. Selection is the lowest text/label hash per fixed
intent, not a post-output choice. Training index, original text hash and masking flags remain
private. Obvious contact/long-number/URL flags were empty; that is not a general PII guarantee.
Tests demonstrate that unrelated split values can contain undecodable bytes without being
decoded, and `test`/`oos_train` cannot substitute for `train`.

No active dataset, reference policy, original split, allowance or release gate changed.
Preparation authorizes neither accepted mappings, TF-IDF calibration nor provider calls.
After mapping review, propose an applicable group-separated training /
calibration / untouched evaluation protocol, with required slices, sample support, operating
limits and exact input/request/source/scorer pins. Only then seek a bounded fresh model
study, using the same shared ledger without reusing bound stopped slots. This sequence
addresses the missing evidence without claiming weaker references satisfy the release bar.
