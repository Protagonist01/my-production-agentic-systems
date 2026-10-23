CREATE TABLE cfpb_app.accounts (
 username text PRIMARY KEY, password_hash text NOT NULL,
 principal jsonb NOT NULL, enabled boolean NOT NULL DEFAULT true
);
CREATE TABLE cfpb_app.sessions (
 token_hash text PRIMARY KEY, username text NOT NULL REFERENCES cfpb_app.accounts,
 csrf_hash text NOT NULL, expires_at timestamptz NOT NULL
);
CREATE TABLE cfpb_app.login_attempts (
 username_hash text PRIMARY KEY, window_start timestamptz NOT NULL, failures integer NOT NULL
);
CREATE TABLE cfpb_app.cases (
 tenant_id text NOT NULL, case_id text NOT NULL, version integer NOT NULL CHECK(version>0),
 complaint jsonb NOT NULL, review_ref text NOT NULL, provenance text NOT NULL,
 taxonomy jsonb NOT NULL, policy jsonb NOT NULL, result jsonb,
 status text NOT NULL CHECK(status IN ('queued','processing','classified','review_required','review_queued')),
 PRIMARY KEY(tenant_id,case_id)
);
CREATE TABLE cfpb_app.events (
 tenant_id text NOT NULL, case_id text NOT NULL, version integer NOT NULL,
 event_key text NOT NULL, kind text NOT NULL, actor_id text NOT NULL,
 metadata jsonb NOT NULL, created_at timestamptz NOT NULL,
 PRIMARY KEY(tenant_id,case_id,event_key),
 FOREIGN KEY(tenant_id,case_id) REFERENCES cfpb_app.cases
);
CREATE TABLE cfpb_app.commands (
 tenant_id text NOT NULL, case_id text NOT NULL, command_id text NOT NULL,
 payload_sha text NOT NULL, resulting_version integer NOT NULL,
 PRIMARY KEY(tenant_id,case_id,command_id),
 FOREIGN KEY(tenant_id,case_id) REFERENCES cfpb_app.cases
);
CREATE TABLE cfpb_app.jobs (
 tenant_id text NOT NULL, case_id text NOT NULL, version integer NOT NULL,
 state text NOT NULL CHECK(state IN ('pending','leased','done','obsolete')),
 lease_id text, lease_until timestamptz, attempts integer NOT NULL DEFAULT 0,
 PRIMARY KEY(tenant_id,case_id,version),
 FOREIGN KEY(tenant_id,case_id) REFERENCES cfpb_app.cases
);
CREATE INDEX cfpb_jobs_ready ON cfpb_app.jobs(state,lease_until);
