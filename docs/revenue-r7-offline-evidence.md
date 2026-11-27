# Revenue release evidence from existing sources

[Issue #45](https://github.com/Protagonist01/my-production-agentic-systems/issues/45) asks how reliably the agent finds governing clauses, identifies discrepancies and defers when billing facts are unresolved. This capture reruns the existing source and simulated billing scorers. It records zero provider calls and zero billing writes.

## Original agreements

The runner verifies the retained CUAD manifest and both SQLite hashes. It keeps every question in three billing-adjacent categories from the existing project holdout, after excluding families by recorded exposure, prior cohort membership or exact context hash. The result is 276 questions from 85 inferred agreement families. Of those families, 44 have at least one published answer in the selected categories.

| Publisher category | Scheduled | No answer | Published spans |
|---|---:|---:|---:|
| Minimum Commitment | 92 | 67 | 58 |
| Price Restrictions | 92 | 91 | 7 |
| Revenue/Profit Sharing | 92 | 59 | 77 |
| Total | 276 | 217 | 142 |

Always-abstain completed all 276 and matched 217, all on no-answer questions. It retrieved zero of 142 reference spans. Precision is undefined because it submitted zero spans. A model candidate has 276 missing observations and no measured score. The high abstention score shows why case agreement alone is misleading. CUAD's answers score literal clause extraction. The [billing reference inventory](revenue-r7-reference-readiness.md) shows why these answers cannot establish a customer's governing rate or expected invoice.

## Simulated billing and ablations

The same 29 authored cases and nine groups ran through all three configurations. Direction determines discrepancy detection. Exact agreement also requires the expected total and reason code. The runner maps original scenario reason labels to expected engine codes for scoring while preserving the original fixture cases.

| Configuration | Exact agreement | Discrepancy precision | Case recall | SIM amount-weighted recall | Benign false alarms | Missed required review |
|---|---:|---:|---:|---:|---:|---:|
| Full engine | 29/29 | 12/12 | 12/12 | 6,000/6,000 minor units | 0/8 | 0/9 |
| Amendments and credits removed | 16/29 | 9/16 | 9/12 | 4,500/6,000 minor units | 3/8 | 4/9 |
| Engine disabled, always review | 0/29 | Undefined, zero flags | 0/12 | 0/6,000 minor units | 0/8 | 0/9 |

Always-review gets every required-review route but supplies no specific reason or billing calculation. The amendment and credit ablation retains the base terms and uplift. It shows the effect of incomplete adjustments under this fixed simulation and policy. The figures represent simulated discrepancies.

## Reproduce and interpret

```powershell
uv run --locked --all-packages python revenue_r7_offline.py --source-dir <existing-private-revenue-cache>
```

Two runs on the same retained inputs produced identical output. The [aggregate report](data/revenue-r7-offline-v1.json) contains plan and exposure pins, per-category and per-treatment scores, and counts for missing, failed and unresolved observations. The [separate historic effect exercise](data/revenue-approved-effects-v1.json) covered 12 approved corrections with duplicate delivery and independently approved compensation. It ran on an earlier revision. The fresh replay does not execute those state changes.

The two-model public-schedule pilot establishes the unsupported-total regression and guarded replay behavior on exposed development cases. For release, #45 still needs applicable independent billing references for unfamiliar agreements, a new frozen final-candidate run, and current authorization, effect and recovery evidence linked to the release methodology. Keep the operator workflow in simulation until those checks pass. [Public-schedule pilot](revenue-public-schedule-pilot.md) · [Release evidence rules](release-evidence.md)
