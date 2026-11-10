CREATE TABLE cfpb_eval.participants (
 tenant_id text NOT NULL, actor_id text NOT NULL, PRIMARY KEY(tenant_id,actor_id)
);
CREATE TABLE cfpb_eval.cases (
 tenant_id text NOT NULL, case_id text NOT NULL, version integer NOT NULL DEFAULT 1,
 family text NOT NULL, actor_id text NOT NULL, arm text NOT NULL CHECK(arm IN ('manual','assisted')),
 complaint jsonb NOT NULL, taxonomy jsonb NOT NULL, policy jsonb NOT NULL,
 review_ref text NOT NULL, measurement_basis text NOT NULL
 CHECK(measurement_basis IN ('human_attested','invented','estimated')),
 created_at timestamptz NOT NULL,
 result jsonb, final_result jsonb, accepted_at timestamptz,
 work_started timestamptz, work_kind text CHECK(work_kind IN ('review','correction','oversight')),
 active_seconds double precision NOT NULL DEFAULT 0,
 PRIMARY KEY(tenant_id,case_id), UNIQUE(tenant_id,actor_id,family),
 FOREIGN KEY(tenant_id,actor_id) REFERENCES cfpb_eval.participants
);
CREATE TABLE cfpb_eval.jobs (
 tenant_id text NOT NULL,case_id text NOT NULL,version integer NOT NULL,
 state text NOT NULL CHECK(state IN ('pending','leased','done')),
 lease text,lease_until timestamptz,attempts integer NOT NULL DEFAULT 0,
 PRIMARY KEY(tenant_id,case_id,version),
 FOREIGN KEY(tenant_id,case_id) REFERENCES cfpb_eval.cases
);
CREATE TABLE cfpb_eval.events (
 tenant_id text NOT NULL,case_id text NOT NULL,command_id text NOT NULL,
 actor_id text NOT NULL,payload_sha256 text NOT NULL,version integer NOT NULL,
 kind text NOT NULL,created_at timestamptz NOT NULL,metadata jsonb NOT NULL,
 PRIMARY KEY(tenant_id,case_id,command_id),
 FOREIGN KEY(tenant_id,case_id) REFERENCES cfpb_eval.cases
);
CREATE INDEX cfpb_eval_pending ON cfpb_eval.jobs(state,lease_until);
