# Fictional monthly billing worlds

R2 #40, 2026-10-20. This prepares **29 invented cases in nine grouped families** for the separately reported SIM billing experiment. The user approved the policy below. The labels are AI-authored provisional references, checked with literal rational arithmetic; they are **not human-reviewed billing gold**. Original CUAD contexts and published annotations remain a [separate source corpus](data/revenue-source.md).

## Policy and boundary

Monthly whole-seat charges use SIM integer hundredths. There is no tax or proration. A billing period is one half-open calendar month, with first-day start and next-month first-day end. Changes/credits apply only at explicit month boundaries. Missing or conflicting terms require review. An annual uplift applies only when an express basis-point rate and first uplift date are both given; it applies on that date and yearly afterward. Fractional minor-unit results require review because no rounding policy has been approved.

Dated seat ramps, explicit price amendments and credits are legitimate terms. They are first-class correct examples, with matching under/overbilling controls. A sequence identifies an amendment version; it does not resolve contradictory same-date instructions. Same-date price amendment plus uplift, negative totals after credits, and midmonth effects require review. The R4 engine owns normalized-term interpretation and reconciliation; fixture generation does not call it.

`BillingInput` contains an invented tenant/account/subscription identity, period, base subscription terms, dated amendments, dated credits and an issued invoice amount. It contains no expected amount, disposition, family, split or reviewer metadata. The input invoice is observed simulated state, not the should-be invoice. Every input declares `source_kind="synthetic"`, `unit="SIM"` and policy `revenue-monthly-whole-seat-sim-v1`. No Maven data, CUAD-derived commercial facts, real customer/account history or real payments are used.

## Literal case coverage

The first six families each include an exact correct invoice, an invoice 500 minor units below the literal expected amount, and an invoice 500 above it. Negative differences are overbilling; positive differences are underbilling. No autonomous billing change is executed.

| Family | Literal expected minor units | Correct interpretation |
|---|---:|---|
| Seats | `8 × 1250 = 10000` | Eight whole seats at the stated price |
| Price | `4 × 3000 = 12000` | Four seats at the stated price |
| Annual uplift | `5 × (2000 × 11000 / 10000) = 11000` | Express 1,000 basis points at the first declared anniversary |
| Seat ramp | `12 × 1250 = 15000` | Dated seat amendment changes eight seats to twelve |
| Credit | `8 × 1250 − 1000 = 9000` | Dated credit is a benign reduction |
| Price amendment | `8 × 1000 = 8000` | Dated amended price replaces the old stated price |

Two additional correct annual-uplift controls expect 10000 before the first uplift date and 12100 at the second anniversary (`5 × 2000 × 1.1 × 1.1`). The other nine cases require review: missing seats, missing price, missing uplift anchor, explicit conflicting terms, contradictory same-date seat amendments, a midmonth amendment, fractional minor-unit uplift, a credit larger than the charge and same-date price amendment/uplift ambiguity.

This makes **eight correct, six underbilled, six overbilled and nine review** references. References are authored as literal amounts/reasons in source. A separate safe arithmetic walker evaluates only integer constants and `+`, `−`, `×`, `/` using exact rational numbers, then checks literal amount and signed difference. It never imports the production reconciler or derives labels from extracted terms. This provides a reproducible second arithmetic check; it does not substitute for independent human review of business meaning.

## Grouping, provenance and stores

The fixed seed is `revenue-fictional-monthly-cohort-v1`. Hashing the seed plus invented family/treatment gives opaque stable keys. The nine families were assigned before candidate evaluation: seat, price-amendment and missing-term families are development; price, ramp and conflict families are regression; uplift, credit and rounding/ambiguity families are holdout. This produces **9 development / 9 regression / 11 holdout cases**. All related invoice perturbations and all periods of the same invented subscription stay in their original family/split. This is a small mechanism cohort, not a statistically representative production benchmark or secret task distribution.

`inputs.sqlite` has only `inputs(case_id, document)`, with strict public `BillingInput` JSON. `evaluator.sqlite` has `cases(case_id, document)` with complete private `BillingCase` references. The evaluator store includes the literal should-be amounts, reasons, arithmetic, split, group and AI review declaration. A candidate receives individual public inputs through the scoped reader. Never give it the evaluator path or arbitrary filesystem access and claim those files are protected by the DTO.

The [aggregate manifest](data/revenue-billing-worlds-v1.json) records policy, seed, as-of date, case/group/split/disposition counts and byte hashes of both stores. Tracked code contains invented fixtures only. Generated databases and the full private material remain outside every Git checkout. An exclusive output directory prevents silent overwrite. A failed preparation leaves an incomplete directory for owner inspection and publishes no final manifest.

The shared R3 `BillingGrant` binds a trusted tenant, actor, exact world IDs and read/reconcile capabilities. `read_world(database, case_id, grant)` checks `read` authority before opening the file, validates the allowed schema, then checks the returned case and tenant before releasing the strict public projection. Account/subscription identities are facts within the scoped world; they do not independently grant authority. Reconcile-only permission does not grant read. This trusted in-process grant is not HTTP authentication, OS isolation, or an authorization service.

## Run offline

From the repository root, choose a new external directory:

```powershell
$billingWorlds = 'D:/document/.cache/production-agents/revenue/billing-worlds-r2-v1'
uv run --locked --all-packages --link-mode copy python -m revenue_integrity.billing_worlds_cli prepare `
  --output $billingWorlds
```

Review the generated `manifest.json` and retain its SHA256 independently. Do not silently calculate a replacement pin for unreviewed changed stores. Verify that pinned snapshot:

```powershell
uv run --locked --all-packages --link-mode copy python -m revenue_integrity.billing_worlds_cli verify `
  --output $billingWorlds `
  --manifest-sha256 <reviewed-manifest-sha256>
```

The verifier checks both store hashes and SQLite integrity, permits only exact expected schema objects, and compares every stored input/reference with the literal authored cohort. It recomputes group/count/review provenance. A repinned modified view, target, input or extra row still fails. Generic CLI errors omit source/target payloads.

The completed local preparation/verification produced the [aggregate snapshot](data/revenue-billing-worlds-v1.json), with manifest pin `97d4193e8339af5164dedc284b6b45d53fce4cb936e809ba76769adc4d104730`. Verification returned `verified: true`, 29 cases and nine groups. Its inputs/evaluator store hashes identify the actual prepared snapshot; another SQLite build may need a separate reviewed prepared-manifest pin even for identical logical records.

Focused invented checks cover literal arithmetic, blocked executable expressions, group/split or identity evasion, expected-target mutations, public/evaluator isolation, denied scope before file access, wrong tenant/case rejection, unexpected SQL views/triggers, repinned store mutations and exclusive/private output. See the [code study](code-study-revenue-billing.md) for verified implementation links. Parent integration owns the combined engine tests, full suite, packaging and hosted CI. This cohort does not prove real billing accuracy, reviewed numeric truth, live extraction quality or revenue recovered.
