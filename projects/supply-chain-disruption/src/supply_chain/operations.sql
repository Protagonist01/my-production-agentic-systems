CREATE TABLE supply.budgets (
 tenant_id text NOT NULL, event_id text NOT NULL, version integer NOT NULL DEFAULT 0,
 spent_minor bigint NOT NULL DEFAULT 0 CHECK(spent_minor BETWEEN 0 AND 50000),
 replans integer NOT NULL DEFAULT 0 CHECK(replans BETWEEN 0 AND 2),
 PRIMARY KEY(tenant_id,event_id)
);
CREATE TABLE supply.shipments (
 tenant_id text NOT NULL, shipment_id text NOT NULL, version integer NOT NULL,
 document jsonb NOT NULL, PRIMARY KEY(tenant_id,shipment_id)
);
CREATE TABLE supply.proposals (
 tenant_id text NOT NULL, operation_id text NOT NULL, document jsonb NOT NULL,
 PRIMARY KEY(tenant_id,operation_id)
);
CREATE TABLE supply.ledger (
 tenant_id text NOT NULL, operation_id text NOT NULL, document jsonb NOT NULL,
 PRIMARY KEY(tenant_id,operation_id)
);
CREATE TABLE supply.confirmations (
 tenant_id text NOT NULL, operation_id text NOT NULL, payload_sha256 text NOT NULL,
 outcome text NOT NULL CHECK(outcome IN ('confirmed','confirmation_failed','confirmation_timeout')),
 actor_id text NOT NULL, recorded_at timestamptz NOT NULL,
 PRIMARY KEY(tenant_id,operation_id)
);
