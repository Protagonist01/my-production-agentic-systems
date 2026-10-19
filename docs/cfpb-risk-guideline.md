# Provisional narrative risk review

Guideline `cfpb-narrative-risk-v1`, 2026-10-19. The user asked Codex to review the first batch. These are **AI-reviewed provisional labels**, not human or qualified financial/legal judgments. No human reviewer availability is established. Risk means priority for a later reviewer under this rubric; it does not establish alleged events, legal violations or actual consumer harm.

## Review procedure

Select four distinct exact-text groups per existing temporal split using SHA-256 of a fixed seed and group ID, then select a fixed-hash representative within each group. Selection does not inspect consumer product/issue labels, risk keywords or candidate outputs. Shuffle presentation by another fixed hash. Keep group/split/source metadata in a separate evaluator file; the blind packet contains only case IDs and full narratives. Do not truncate narratives or expose baseline predictions before recording labels.

Record reviewer identity/kind, guideline version, time, narrative digest, risk, ambiguity, exact supporting spans and rationale. Review each complete narrative before calculating any baseline output. Freeze the completed review file's byte digest before baseline execution. A signature/hash identifies recorded judgments, not human validation or factual truth. One AI reviewer supplies no inter-reviewer agreement measurement; disagreements remain unassessed unless an additional reviewer supplies separate labels. Never record zero disagreements as evidence of agreement when only one review exists.

## Labels

| Dimension | Value | Rule |
|---|---|---|
| risk | elevated | Narrative explicitly alleges ongoing/imminent loss of housing, essential living funds or access to necessities; active unauthorized identity/account access; or time-sensitive threats/coercion requiring prompt review. Record the concrete passage. |
| risk | routine | Enough context to assess the rubric, with none of those explicit triggers. This means no identified trigger in the text, not proof of low actual risk. Ordinary billing disputes, historical credit-report errors and general dissatisfaction are not elevated solely because money or the word fraud appears. |
| risk | uncertain | Missing/conflicting/redacted context prevents a defensible elevated/routine judgment. Record what is missing. Do not turn uncertainty into routine. |
| ambiguity | clear | The main allegation/request and relevant sequence are understandable, even though its truth is unverified. |
| ambiguity | ambiguous | Competing interpretations, conflicting sequence or key missing/masked details prevent a single defensible interpretation. Multiple understandable issues alone do not require this label. |

The rubric intentionally differs from a keyword baseline. Negation, quotation, historical versus current events and indirect language require reading the complete text. Evidence spans use Python Unicode character offsets and must exactly match the sealed narrative. For routine/uncertain judgments, the rationale explains the absence/insufficiency; spans need not pretend to prove a negative.

## First batch and evaluation

The user-selected first batch is 12 original narratives: four development, four regression, four March holdout. It is a small mechanism/review pilot, not a representative estimate or a release benchmark. Blind evaluation review of holdout labels does not authorize candidate tuning on the holdout. Publish aggregate counts and baseline denominators; keep narratives, individual judgments and evidence outside Git. Do not upload a live Langfuse dataset or make fresh provider calls.

Majority baseline fits development labels only; a separately versioned fixed rules baseline is deliberately simple. Both operate on narrative-only inputs. Consumer-selected product/issue targets remain unverified reference labels and must be reported separately from provisional risk judgments. A baseline's risk agreement is not validated high-risk recall or harm reduction. Later human/adjudicated labels require a new version and fresh evidence; provisional results cannot silently become release gold.
