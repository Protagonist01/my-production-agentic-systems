CREATE TABLE olist_app.accounts (
    username text PRIMARY KEY,
    password_hash text NOT NULL,
    principal jsonb NOT NULL,
    enabled boolean NOT NULL DEFAULT true
);
CREATE TABLE olist_app.sessions (
    token_hash text PRIMARY KEY,
    username text NOT NULL REFERENCES olist_app.accounts(username),
    csrf_hash text NOT NULL,
    expires_at timestamptz NOT NULL
);
CREATE TABLE olist_app.login_attempts (
    username_hash text PRIMARY KEY,
    window_start timestamptz NOT NULL,
    failures integer NOT NULL DEFAULT 0 CHECK(failures >= 0)
);
CREATE TABLE olist_app.cases (
    tenant_id text NOT NULL,
    case_id text NOT NULL,
    request_hash text NOT NULL,
    actor_id text NOT NULL,
    order_id text NOT NULL,
    version bigint NOT NULL CHECK(version >= 0),
    status text NOT NULL,
    document jsonb NOT NULL,
    PRIMARY KEY(tenant_id,case_id)
);
CREATE TABLE olist_app.events (
    event_id text PRIMARY KEY,
    tenant_id text NOT NULL,
    case_id text NOT NULL,
    actor_id text NOT NULL,
    kind text NOT NULL,
    at timestamptz NOT NULL,
    detail jsonb NOT NULL,
    FOREIGN KEY(tenant_id,case_id) REFERENCES olist_app.cases(tenant_id,case_id)
);
