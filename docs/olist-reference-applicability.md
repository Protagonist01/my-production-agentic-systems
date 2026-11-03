# Olist reference applicability and complete comparison reports

Prepared2026-11-03 on `codex/closeout-reference-evidence`, from verified main8ca35df.
This implements source auditing and project partition preparation, not label validation,
model capture or release. [Measured source inventory](data/olist-reference-applicability-v1.json)
contains aggregate counts/pins; source messages, native annotations and exposure files stay
private. Existing24development cases, owner acceptances and the stopped study are unchanged.

## Why publisher labels require an applicability check

The pinned [ABCD documentation](https://github.com/asappresearch/abcd/blob/6b8700ce67c6b37b062dd7a60abc76d7ef832a97/README.md)
describes flow/subflow as the latent task used to prompt the whole conversation. A refund
dialogue can begin with a generic return request; an account-recovery dialogue can begin
with a greeting. That annotation is not automatically an Olist first-message intent label.

`reference_audit.audit_archive` verifies a separately supplied compressed archive hash,
bounded decompression, duplicate JSON/record identities and native split inventory. It
projects only the exact first customer message into AgentInput. Scenario, turn annotations,
candidate lists and future utterances remain outside model input. Exact scope anchors and
exclusions identify cases for review; finding a word does not prove semantic support.
Unknown or conflicting cases are retained, not relabeled to make the dataset convenient.

The first actual run covered10,042conversations. After the initial18known source exposures,
the publisher test split had8refund review candidates. All12new applicability witnesses
are from publisher training data. Their exposure is preserved in the next inventory, which
contains29source IDs and39normalized text identities, including previous authored stress.
Exact-text overlap can expose many records through a shared greeting; new IDs alone are
not a freshness guarantee. No new amount labels or semantic gold are established.

## Owner-selected project partitions

The owner explicitly chose: retain publisher split metadata and create Olist project
partitions over unexposed source groups. Original source files/splits remain untouched.
`project_partitions.partition` implements that preparation instruction. A record with native
`train` metadata may therefore be in the Olist project holdout; this is not the publisher's
official test benchmark and does not establish absence from foundation-model pretraining.

Before assignment, link mapped records, excluded intermediaries and every known exposed
text by exact normalization or token-set Jaccard similarity at least4/5. Use transitive
components; quarantine any component connected to prior exposure. Native split-crossing
duplicates can remain only in one project component/partition. Unmapped goals, conflicting
visible wording and annotation mismatches remain excluded. Token overlap is a conservative
approximation, not an authenticated semantic family or author identity.

Draft assignment is fixed group-hash20%development/20%regression/60%holdout. Actual group
fractions can differ; no seed was retuned to obtain a desired benchmark score or size.
All rows retain native split, source/frame hash, component and exclusion provenance.

| Proposed project partition | Rows | Connected lexical groups |
|---|---:|---:|
| Development |198|189|
| Regression |238|189|
| Holdout |636|539|
| Excluded |8,970|Not an evaluation denominator|

The holdout proposal contains57refund/203status/376unsupported rows in49/183/307declared
lexical groups respectively. These are applicability candidates, not accepted labels or
validated independent groups. Project splitting solves a preparation constraint; it does
not establish semantic truth, amount references, reship/clarification coverage, adequate
sample size, an accepted uncertainty target or a replacement review policy.

The private12-witness review is at
`D:/document/.cache/production-agents/olist/reference-applicability-review-2026-11-03-v1/review.md`.
The project audit/partitions are in `reference-applicability-audit-2026-11-03-v2` under the
same private Olist cache. Source/metadata hashes are independently recomputed before use.
Later capture must exclude these reviewed witnesses and retain all original exposures.

## Reproduce without network or models

Use the separately pinned source archive and complete current exposure index. The optional
project stage also requires all exposed texts with their canonical pin and the owner's
preparation reference; a partial text inventory refuses lexical linkage.

```powershell
python -m olist_support.reference_audit_cli --archive <private-abcd.gz> --archive-sha256 <external-source-pin> --exposure <private-exposure.json> --exposure-sha256 <canonical-index-pin> --exposed-texts <private-texts.json> --exposed-texts-sha256 <canonical-texts-pin> --partition-preparation-ref <actual-owner-reply-ref> --output <new-private-directory>
```

The module installs the existing network-denial audit hook. It writes exclusively into a
new private directory, emits aggregate counts and refuses existing outputs. Its source
audit and project grouping can be recomputed from pinned inputs with `verify_audit` and
`verify_partitions`. Neither function authenticates the supplied exposure history or an
operator's claimed approval identity. Do not upload the private artifacts automatically.

## Service comparison and operational seam

`service_study.ServiceProtocol` binds the actual service population/manifest, three distinct
candidate/rules/always-review compositions and three trials. `assemble` projects artifacts
only after the service/H10 readers verify them. It does not authenticate a manually
constructed VerifiedEvidence object; `summarize` is a pure count calculation.

All scheduled cases/trials/variants remain in denominators, including missing baseline
variants, failed/unresolved attempts and unknown fields. Saved fallback plans cannot earn
semantic/completion credit on unresolved runs. Report exact field counts, joint intent/
amount, conditional eligible completion, required-review routing, all-repetition case
success and connected-group error bounds. Groups connect source, parent/language, input
and order identities; repeated trials or customer scripts are not independent cases.
The interval is conditional on independence assumptions that code cannot certify.

Parent trial durations include setup/execution/cleanup. Observed p95 with missing durations
is not a complete latency statistic; this timing cannot establish the API/model-decision
targets. Usage preserves missing token/cost counts, known reported currency totals and
reported calls. Unknown cost is not zero, and even a reported Free zero is not billing
proof. Preparation reports cannot approve qualification or release.

An operational audit also found that `create_app` always constructed staff-only context
IDs, even when its trusted CaseStore had a planner. It now selects the explicit model-service
identity for that trusted composition. Default staff identity and offline_fake mode remain.
HTTP callers cannot select a planner/profile/mode or enable a provider. Real authenticated
HTTP tests preserve the typed decision through submission/redelivery and exact customer
confirmation using a reconstructed customer app with no planner.

## Alternative-source finding and remaining decision boundary

The pinned [Bitext dataset card](https://huggingface.co/datasets/bitext/Bitext-customer-support-llm-chatbot-training-dataset/blob/430d1a89bd93bd1fa23c16f29dd53e73f0087443/README.md)
offers direct instruction/intent annotations, but describes hybrid synthetic seed expansion.
Its metadata declares CDLA-Sharing-1.0; [the published license](https://cdla.dev/sharing-1-0/)
sets conditions for data publication. Only publisher metadata/card were acquired in this
investigation, not its CSV. It is not added to the approved source mix. Direct annotations
or many generated rows would not, by themselves, prove independent real-customer evidence.

Keep source applicability, accepted reference method, frozen sampling/uncertainty, selected-
host readiness and explicit provider scope as separate decisions. No original source,
profile, review kind, release threshold, attempt allowance or study stop changes here.
The input/reference/metadata separation follows [Langfuse's dataset guidance](https://langfuse.com/academy/datasets).

Interview exercise: explain how10,042source conversations can yield only8native-test refund
review candidates, why project-holdout metadata does not prove pretraining novelty, and why
valid consent or a perfect three-trial mock recording cannot certify model understanding.
