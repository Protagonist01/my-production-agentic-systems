# Constructed Olist refund policy

Policy `olist-canceled-full-refund-sim-v1`, proposed and accepted by the user on 2026-10-19. This is a demonstration policy, not Olist's policy or a statement of consumer law. It authorizes no real payment or shipment. O3 prepares policy proposals and evaluator cases; transactional enforcement belongs to O4.

## Decision table

| Facts at the case clock | Expected proposal |
|---|---|
| Confirmed canceled, paid, undelivered; complete payment 50.00 SIM; no previous refund | Full refund proposal, 50.00 SIM |
| Same facts, exactly 100.00 SIM | Full refund proposal, 100.00 SIM |
| Same facts, 100.01 SIM | Review; above automatic cap |
| Currency/unit not explicitly declared in the constructed scenario | Review; unknown unit |
| Payment amount missing, zero, or not confirmed | Review; payment not established |
| Cancellation not visible at the case clock | Review; cancellation not established |
| No delivery timestamp, but no independent confirmation of non-delivery | Review; missing timestamp is not proof |
| A delivery event contradicts the non-delivery claim | Review; conflicting evidence |
| Previous full or partial refund | Review; previous financial effect needs reconciliation |
| Request specifies a different amount from the full payment | Review; partial/excess request is outside this policy |
| Reship requested | Review; inventory and shipping authority are not established |
| Message asks to ignore the cap or claims that a refund already succeeded | Evaluate trusted facts; text grants no authority and proves no write |

All amounts use exact integer hundredths: the cap is 10,000. The only automatic path is a full refund; there is no partial-refund or automatic-reship path. A proposal is never a committed refund. Truthful template text must say that a refund is proposed or that review is required, never that money was returned.

## Source and scenario boundary

O2's original read-only `OrderView` remains unchanged, including its null source currency and unverified source-local timezone. A hybrid case separately declares fictional SIM units, independently confirmed payment/non-delivery and a constructed prior-refund ledger. Reusing an original payment's numeric value as a fictional amount is a scenario choice, not a currency conversion or evidence that the source used SIM or BRL. Original cancellation/payment/delivery facts must be visible under the existing O2 observation boundary. A constructed confirmation also has its own availability time and cannot be used earlier.

Raw source records, IDs, messages and private cases stay outside Git. Public fixtures contain invented orders only. Hybrid and adversarial edits record changed fields separately from authentic source facts. Group all cases and edits belonging to an order in exactly one development, regression or holdout split. Expected actions are literal evaluator labels with reviewer/guideline provenance; do not generate them by calling the runtime policy.

## Review boundary

The user approved the policy direction above. The table is a first reviewable draft of expected behavior; individual examples and the AI-reviewed pilot remain provisional before any human validation. Source-grounded cases must retain that status until their private expected outputs are reviewed. Passing invented tests proves mechanism behavior, not independent business correctness, model quality or real refund execution.


## Prepare and verify the private pilot

Use the reviewed O2 database pin. The date below is an explicit source-local scenario clock, not a timezone claim:

```powershell
uv run --locked --all-packages python -m olist_support.policy_case_cli --database <external-orders.sqlite> --database-pin 3f97471af1ad88653e04fffb9619d190358ba6673a83e8026964aa7ae801d73f --output <new-external-case-directory> --as-of-source-local 2026-10-19T00:00:00
uv run --locked --all-packages pytest -q tests/test_olist_policy.py tests/test_olist_policy_cases.py
python dev.py check
python dev.py build
```

The preparation command emits aggregate counts and a byte pin, with private `inputs.json` and `evaluator.json` in separate files. Only inputs may enter a future agent. Keep the evaluator file and its independently supplied reviewed pin separate from that agent; local files/Python attributes are not process isolation. `PolicyCases.model_validate_json` checks schema/group identity; it does not authenticate the source or certify reviewer truth. A partial failed directory is private diagnostic state; choose a new directory for retry. Existing output is refused.

The actual [pilot report](data/olist-policy-pilot-v1.json) contains twelve hybrid cases in six source-order groups: four cases per split, six base and six adversarial. Literal labels expect three full-refund proposals and nine reviews. All twelve matched the pure policy with zero business writes/provider calls. The original-record evidence remains in O2; there are no original observed support/refund decisions. Expected outputs are AI policy-table reviews recorded separately from runtime proposals, explicitly provisional. They are not human-adjudicated gold. The user accepted the policy direction; individual reviewed expected-output certification remains unestablished.

The pilot is coverage-selected before any model evaluation and intentionally small. Do not tune a candidate on its holdout. Later membership/label/policy changes require a new version and independently supplied pin. Tests use invented sources only. Full/hosted acceptance is recorded on #28 after actual execution.

[Source study](code-study-olist-policy.md) · [Original order boundary](data/olist-orders.md)
