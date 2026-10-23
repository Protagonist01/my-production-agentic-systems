CREATE TABLE prior_auth_app.accounts (
 username text PRIMARY KEY, password_hash text NOT NULL,
 principal jsonb NOT NULL, enabled boolean NOT NULL DEFAULT true
);
CREATE TABLE prior_auth_app.sessions (
 token_hash text PRIMARY KEY, username text NOT NULL REFERENCES prior_auth_app.accounts,
 csrf_hash text NOT NULL, expires_at timestamptz NOT NULL
);
CREATE TABLE prior_auth_app.login_attempts (
 username_hash text PRIMARY KEY, window_start timestamptz NOT NULL, failures integer NOT NULL
);
CREATE TABLE prior_auth_app.cases (
 tenant_id text NOT NULL, case_id text NOT NULL, version integer NOT NULL CHECK(version>0),
 note jsonb NOT NULL, policy jsonb NOT NULL, candidate jsonb, result jsonb,
 status text NOT NULL CHECK(status IN ('assessing','waiting','request_information','qualified_review','evidence_complete_for_review')),
 wait_criteria jsonb NOT NULL DEFAULT '[]', deadline timestamptz,
 PRIMARY KEY(tenant_id,case_id)
);
CREATE TABLE prior_auth_app.events (
 tenant_id text NOT NULL, case_id text NOT NULL, version integer NOT NULL,
 event_key text NOT NULL, kind text NOT NULL, actor_id text NOT NULL,
 metadata jsonb NOT NULL, created_at timestamptz NOT NULL,
 PRIMARY KEY(tenant_id,case_id,event_key),
 FOREIGN KEY(tenant_id,case_id) REFERENCES prior_auth_app.cases
);
CREATE TABLE prior_auth_app.commands (
 tenant_id text NOT NULL, case_id text NOT NULL, command_id text NOT NULL,
 payload_sha text NOT NULL, resulting_version integer NOT NULL,
 PRIMARY KEY(tenant_id,case_id,command_id),
 FOREIGN KEY(tenant_id,case_id) REFERENCES prior_auth_app.cases
);
CREATE TABLE prior_auth_app.jobs (
 tenant_id text NOT NULL, case_id text NOT NULL, version integer NOT NULL,
 criteria jsonb NOT NULL, state text NOT NULL CHECK(state IN ('pending','leased','done','obsolete')),
 lease_id text, lease_until timestamptz, attempts integer NOT NULL DEFAULT 0,
 PRIMARY KEY(tenant_id,case_id,version),
 FOREIGN KEY(tenant_id,case_id) REFERENCES prior_auth_app.cases
);
CREATE INDEX prior_auth_jobs_ready ON prior_auth_app.jobs(state,lease_until);
