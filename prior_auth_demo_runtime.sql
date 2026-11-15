-- Separate additive demo composition; legacy clinical schema stays immutable.
CREATE TABLE prior_auth_demo.scopes (
    scope_id text PRIMARY KEY,
    scope_sha256 text NOT NULL,
    document jsonb NOT NULL
);
CREATE TABLE prior_auth_demo.attempts (
    scope_id text NOT NULL REFERENCES prior_auth_demo.scopes,
    work_sha256 text NOT NULL,
    tenant_id text NOT NULL,
    case_id text NOT NULL,
    case_version integer NOT NULL CHECK(case_version>0),
    criterion text NOT NULL,
    request_sha256 text NOT NULL,
    created_at timestamptz NOT NULL,
    PRIMARY KEY(scope_id,work_sha256),
    FOREIGN KEY(tenant_id,case_id) REFERENCES prior_auth_app.cases
);
CREATE TABLE prior_auth_demo.settlements (
    scope_id text NOT NULL,
    work_sha256 text NOT NULL,
    response_sha256 text NOT NULL,
    response jsonb NOT NULL,
    tokens bigint CHECK(tokens>=0),
    stop boolean NOT NULL,
    PRIMARY KEY(scope_id,work_sha256),
    FOREIGN KEY(scope_id,work_sha256) REFERENCES prior_auth_demo.attempts
);
REVOKE ALL ON SCHEMA prior_auth_demo FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA prior_auth_demo FROM PUBLIC;
