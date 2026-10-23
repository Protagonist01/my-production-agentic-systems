CREATE TABLE supply_app.accounts (
 username text PRIMARY KEY, password_hash text NOT NULL, principal jsonb NOT NULL,
 enabled boolean NOT NULL DEFAULT true
);
CREATE UNIQUE INDEX supply_actor_identity ON supply_app.accounts((principal->>'tenant_id'),(principal->>'actor_id'));
CREATE TABLE supply_app.sessions (
 token_hash text PRIMARY KEY, username text NOT NULL REFERENCES supply_app.accounts(username),
 csrf_hash text NOT NULL, expires_at timestamptz NOT NULL
);
CREATE TABLE supply_app.login_attempts (
 username_hash text PRIMARY KEY, window_start timestamptz NOT NULL,
 failures integer NOT NULL DEFAULT 0 CHECK(failures>=0)
);
CREATE TABLE supply_app.contexts (
 tenant_id text NOT NULL, event_id text NOT NULL, document jsonb NOT NULL,
 PRIMARY KEY(tenant_id,event_id)
);
CREATE TABLE supply_app.notices (
 notice_id text PRIMARY KEY, tenant_id text NOT NULL, event_id text NOT NULL,
 shipment_id text NOT NULL, document jsonb NOT NULL
);
CREATE INDEX supply_notice_scope ON supply_app.notices(tenant_id,event_id,shipment_id);
CREATE TABLE supply_app.notice_reads (
 username text NOT NULL REFERENCES supply_app.accounts(username),
 notice_id text NOT NULL REFERENCES supply_app.notices(notice_id),
 PRIMARY KEY(username,notice_id)
);
