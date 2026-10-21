CREATE TABLE revenue_app.accounts (
    username text PRIMARY KEY,
    password_hash text NOT NULL,
    principal jsonb NOT NULL,
    enabled boolean NOT NULL DEFAULT true
);
CREATE UNIQUE INDEX revenue_actor_identity ON revenue_app.accounts((principal->>'tenant_id'),(principal->>'actor_id'));
CREATE TABLE revenue_app.sessions (
    token_hash text PRIMARY KEY,
    username text NOT NULL REFERENCES revenue_app.accounts(username),
    csrf_hash text NOT NULL,
    expires_at timestamptz NOT NULL
);
CREATE TABLE revenue_app.login_attempts (
    username_hash text PRIMARY KEY,
    window_start timestamptz NOT NULL,
    failures integer NOT NULL DEFAULT 0 CHECK(failures >= 0)
);
