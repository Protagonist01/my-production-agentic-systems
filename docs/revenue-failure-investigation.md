# Revenue failure investigation and engineering decisions

## Scope and evidence boundary

Started 2026-10-27 from merged main `95e8a1d`. The owner requested implementation of the
diagnostic recommendations and an extensive record for future employer and business
discussions. This investigation uses the already exposed, completed CUAD study. It does
not replace publisher labels, qualify a legal interpretation, or consume a fresh holdout.

Work in progress: preserve measured results separately from proposed explanations and
untested changes. The original 296-attempt study and operationally failed development run
remain authoritative historical results. New implementation and checks are recorded below
as they happen.

## Initial findings before implementation

The original validation has 288 scheduled observations: 237 correct, 28 valid but wrong,
22 rejected by citation checks and one provider failure. Those are disjoint final outcomes.
Before citation checking, 31 raw decisions disagree with the reference: three of these also
have invalid evidence. Nineteen citation-invalid responses have a reference-correct raw
decision. These overlapping diagnostic counts must not be added to the final denominator.

Across 144 validation families, 142 have the same raw decision on both trials. Fifteen
families have wrong raw decisions on both trials. Twenty-one families fail both final
trials; nine fail one. Repeated calls are not independent families, and consistency is not
correctness. Temperature zero does not establish determinism.

Inspection reveals a concrete ambiguity in the task contract. The existing prompt asks
whether the document contains an explicit answer. The publisher reference instead records
the presence of passages annotated for a category. A denial of an exclusive arrangement
answers a natural-language exclusivity question, but is not necessarily a positive
exclusivity annotation. Similarly, an express denial of third-party beneficiary rights is
an answer, yet the publisher marks the category absent. This observation supports a task
alignment hypothesis; it does not prove how much of the error rate it causes.

Some publisher-positive passages are indirect, and some publisher-negative cases contain
apparently relevant language. Treat these as reference-applicability questions, not proof
that the source is wrong or permission to relabel. No post-hoc alternative label can rescue
the original benchmark result.

## Construction log

Implementation and actual verification will be appended here. No new model-quality result
is claimed at this point.
