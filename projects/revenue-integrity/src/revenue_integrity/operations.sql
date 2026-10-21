CREATE TABLE revenue.records (
 tenant_id text NOT NULL, resource_id text NOT NULL, kind text NOT NULL CHECK(kind IN ('invoice','account')),
 version bigint NOT NULL CHECK(version>=0), document jsonb NOT NULL, PRIMARY KEY(tenant_id,resource_id));
CREATE TABLE revenue.proposals (
 tenant_id text NOT NULL, operation_id text NOT NULL, command_sha256 text NOT NULL, document jsonb NOT NULL,
 PRIMARY KEY(tenant_id,operation_id));
CREATE TABLE revenue.ledger (
 tenant_id text NOT NULL, operation_id text NOT NULL, ledger_id text NOT NULL UNIQUE,
 original_operation_id text, document jsonb NOT NULL, PRIMARY KEY(tenant_id,operation_id),
 UNIQUE(tenant_id,original_operation_id));
