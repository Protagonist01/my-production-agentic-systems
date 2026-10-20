CREATE TABLE olist.orders (
    tenant_id text NOT NULL,
    order_id text NOT NULL,
    source_view jsonb NOT NULL,
    confirmation jsonb,
    source_pin text NOT NULL,
    version bigint NOT NULL DEFAULT 0 CHECK(version >= 0),
    refunded_minor bigint NOT NULL DEFAULT 0 CHECK(refunded_minor >= 0),
    PRIMARY KEY(tenant_id,order_id)
);
CREATE TABLE olist.run_budgets (
    tenant_id text NOT NULL,
    run_id text NOT NULL,
    limit_minor bigint NOT NULL CHECK(limit_minor >= 0),
    spent_minor bigint NOT NULL DEFAULT 0 CHECK(spent_minor >= 0 AND spent_minor <= limit_minor),
    PRIMARY KEY(tenant_id,run_id)
);
CREATE TABLE olist.refunds (
    tenant_id text NOT NULL,
    operation_id text NOT NULL,
    order_id text NOT NULL,
    payload_sha256 text NOT NULL,
    receipt jsonb NOT NULL,
    amount_minor bigint NOT NULL CHECK(amount_minor > 0 AND amount_minor <= 10000),
    PRIMARY KEY(tenant_id,operation_id),
    FOREIGN KEY(tenant_id,order_id) REFERENCES olist.orders(tenant_id,order_id)
);
CREATE TABLE olist.sessions (
    tenant_id text NOT NULL,
    event_id text NOT NULL,
    request_sha256 text NOT NULL,
    PRIMARY KEY(tenant_id,event_id)
);
