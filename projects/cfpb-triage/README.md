# production-agent-cfpb-triage

Import package: `cfpb_triage`. C1 implements pinned historical CFPB archive ingestion, narrative-only agent storage, separate consumer-label storage and grouped temporal development/regression/holdout partitions. It does not implement classification or reviewed risk labels.

[Source acquisition, boundaries and verification](../../docs/data/cfpb-source.md) · [Code walkthrough](../../docs/code-study-cfpb.md) · [Delivery plan](../../docs/cfpb-triage.md)

C2 adds [provisional blind risk review and deterministic baselines](../../docs/cfpb-risk-baselines.md), with a [code walkthrough](../../docs/code-study-cfpb-baselines.md). Labels are AI-reviewed/provisional; consumer targets remain unverified reference selections. C2 is merged/verified after #84.

C3/C4 implement [typed Gemini classification, development-only routing and a protected durable reviewer desk](../../docs/cfpb-triage-operations.md), with a [source walkthrough](../../docs/code-study-cfpb-triage.md). The real provisional pilot required review for every case; no useful automation, human validation or domain release is established. Install the `web` extra for the local desk; live Gemini and Langfuse also require the harness `gemini` and `telemetry` extras. The locked workspace setup includes these dependencies.
