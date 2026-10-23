# CFPB provisional review and deterministic baselines

C2 #35, unmerged `codex/c2-risk-baselines`, 2026-10-19. C1 #82 is merged and verified on main `2988428`: 625 local tests and nine applicable hosted jobs. The user selected O3+C2 and asked Codex to label the first twelve complaints. This work implements blind sampling, explicit provisional reviewer evidence, deterministic majority/rules baselines and aggregate reports. It implements no model classifier, calibrated router, live Langfuse dataset or released application.

## Review evidence

The [guideline](cfpb-risk-guideline.md) defines elevated/routine/uncertain risk and clear/ambiguous meaning. Four distinct exact-text groups per existing split were selected by the fixed seed `cfpb-c2-blind-pilot-v1`; neither consumer labels, keywords nor predictions selected membership. A narrative-only packet was read completely before any baseline ran. One Codex reviewer recorded exact evidence spans and rationale, then sealed the review bytes. The labels are **AI-reviewed provisional judgments**: nine routine, one elevated, two uncertain; ten clear and two ambiguous. No qualified human review, factual validation or inter-reviewer agreement is established.

The public [pilot report](data/cfpb-risk-pilot-v1.json) contains aggregate results and byte pins. Per-case narratives, selections, judgments and spans stay outside Git. The review pin identifies recorded judgments, not validated truth. Holdout review was an evaluator step, not authorization to tune a model or keyword list on those cases. An independent human/adjudicated review requires a new version.

| Split | Cases | Majority risk matches | Rules risk matches | Majority review count | Rules review count | Provisional elevated cases |
|---|---:|---:|---:|---:|---:|---:|
| Development | 4 | 4 | 1 | 0 | 3 | 0 |
| Regression | 4 | 3 | 2 | 0 | 2 | 0 |
| March holdout | 4 | 2 | 2 | 0 | 2 | 1 |

The majority fits development judgments only and always predicts routine/clear in this pilot. It misses the sole provisionally elevated holdout case. Rules route that case to review, but have false positives from generic unauthorized/fraud/legal wording and cannot resolve the uncertain cases. Elevated-review recall is undefined where there are zero elevated labels; it is not reported as a perfect score. One positive case cannot validate high-risk recall. Review fraction is actual routed cases divided by all four cases, including uncertain examples. No baseline tuning followed these results.

## Complete consumer-reference baseline

The separate [complete-cohort report](data/cfpb-consumer-baselines-v1.json) covers 260,738 prepared narratives: 139,732 development, 71,859 regression and 49,147 holdout. These targets are consumer-selected product/issue references, not the independently reviewed truth about events or risk. Majority product and conditional issue choices fit development only, with a lexical tie rule. Fixed keyword product rules take only narrative text; issue predictions use that product's development majority, falling back to the overall development majority if the product was unseen.

Report product and joint product/issue agreement separately. Macro-F1 includes the union of reference and predicted classes, assigning zero F1 to classes with no correct support; per-class recall/precision remain null when their denominators are zero. The report publishes every class's support, prediction count and correct count. This is agreement with source selections, not a deployed classifier or harm-reduction result. Its large reference population does not repair the twelve-case risk pilot's small, provisional labels.

## Commands and private files

```powershell
python dev.py setup
uv run --locked --all-packages python -m cfpb_triage.review_cli packet --prepared <external-prepared-directory> --manifest-pin 48c74ce291e0be372118ad8de2c29688004c54fc43ebd8fd2b2e3eda58c24f18 --output <new-external-review-directory>
uv run --locked --all-packages python -m cfpb_triage.review_cli pilot --packet <external-blind.json> --packet-pin <reviewed-byte-pin> --selection <external-selection.json> --selection-pin <reviewed-byte-pin> --reviews <external-reviews.json> --reviews-pin <reviewed-byte-pin> --reviewer <recorded-reviewer-id> --output <new-aggregate-report.json>
uv run --locked --all-packages python -m cfpb_triage.review_cli consumer --prepared <external-prepared-directory> --manifest-pin 48c74ce291e0be372118ad8de2c29688004c54fc43ebd8fd2b2e3eda58c24f18 --output <new-aggregate-report.json>
```

The packet command creates `blind.json` with case IDs/narratives only and `selection.json` with evaluator-only group/split/provenance. Review files must match the closed `Review` schema: reviewer ID/kind, UTC-aware review time, guideline version/digest, narrative digest, risk/ambiguity, exact Unicode evidence spans and rationale, provisional status and `predictions_seen=false`. Software checks the record structure and pins; identity, independence and truthful assertions remain trusted. Keep the rubric text whose digest is recorded with private review evidence. Predictions must not be available to a reviewer before recording their labels.

The first packet exposed the same Windows intended-text versus written-byte hash issue as O3. Its original packet and reviews were preserved. A new evaluator metadata file corrected only the packet byte digest and added the guideline pin; no membership, source text, split or judgment changed. Current packet generation writes explicit UTF-8/LF and tests its actual file-byte digest. Original selection and repaired selection pins remain in private evidence.

No-overwrite output protects existing review/report artifacts. Errors from closed review schemas are redacted at the CLI so Pydantic does not print source narratives. Raw/prepared/review files are rejected below any Git ancestor; Windows inherits restricted private parent ACLs. These local files and Python objects are not process or tenant security sandboxes. Run with trusted local artifacts and independently reviewed pins.

## Verify and interpret

```powershell
$env:TEMP = '<private-temporary-directory-outside-any-Git-checkout>'
$env:TMP = $env:TEMP
uv run --locked --all-packages pytest -q tests/test_cfpb_review.py tests/test_cfpb_baselines.py
python dev.py check
python dev.py build
```

Twenty-one focused invented tests passed, including hash-selection stability, cross-split groups, reviewer completeness, exact spans, missing positives, fit isolation, hand-counted macro-F1 and pinned source-to-packet checks. Strict types passed 59 source files after a heterogeneous dictionary inference issue was repaired with an explicit numeric F1 accumulator. A final bounds witness rejects an evidence end beyond the narrative length even when Python would clamp the slice. Full/current-head hosted evidence is recorded on #35 after execution.

Guideline design follows the separation of [inputs, expected outputs and metadata](https://langfuse.com/academy/datasets). No live dataset mutation or provider call occurred. Release claims still require independently reviewed labels, more cases/coverage, model implementation, declared thresholds and fresh release evidence. C2 does not supply a human-validated risk release baseline.

[Code walkthrough](code-study-cfpb-baselines.md) · [C1 source boundary](data/cfpb-source.md) · [Delivery plan](cfpb-triage.md)
