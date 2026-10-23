# production-agent-cfpb-triage

Import package: `cfpb_triage`. C1 implements pinned historical CFPB archive ingestion, narrative-only agent storage, separate consumer-label storage and grouped temporal development/regression/holdout partitions. It does not implement classification or reviewed risk labels.

[Source acquisition, boundaries and verification](../../docs/data/cfpb-source.md) · [Code walkthrough](../../docs/code-study-cfpb.md) · [Delivery plan](../../docs/cfpb-triage.md)

C2 adds [provisional blind risk review and deterministic baselines](../../docs/cfpb-risk-baselines.md), with a [code walkthrough](../../docs/code-study-cfpb-baselines.md). Labels are AI-reviewed/provisional; consumer targets remain unverified reference selections. No model classifier or human-validated release baseline exists.
