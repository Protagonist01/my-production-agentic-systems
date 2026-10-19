# production-agent-olist-support

Import package: `olist_support`. O2 implements pinned private Olist CSV import, one-row-per-order aggregates and conservative scoped as-of views. See [operations](../../docs/data/olist-orders.md) and [source study](../../docs/code-study-olist-orders.md). Raw/derived source rows stay outsideGit; no model call, refund policy or business action is implemented here.

O3 adds [constructed SIM-only refund proposals and private grouped cases](../../docs/olist-policy.md), with a [code walkthrough](../../docs/code-study-olist-policy.md). Proposals are not committed refunds; case labels remain provisional AI reviews.
