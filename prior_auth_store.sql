-- Additive control-plane receipts. No raw rejected document or document text in metadata.
CREATE SCHEMA IF NOT EXISTS prior_auth_intake;
CREATE TABLE IF NOT EXISTS prior_auth_intake.receipts (
    tenant_id text NOT NULL,
    case_id text NOT NULL,
    document_id text NOT NULL,
    request_sha256 text NOT NULL,
    prepared_sha256 text NOT NULL,
    source_sha256 text NOT NULL,
    decision jsonb NOT NULL,
    resulting_version integer,
    created_at timestamptz NOT NULL,
    PRIMARY KEY (tenant_id, case_id, document_id)
);
CREATE TABLE IF NOT EXISTS prior_auth_intake.documents (
    tenant_id text NOT NULL,
    case_id text NOT NULL,
    document_id text NOT NULL,
    normalized jsonb NOT NULL,
    binding_sha256 text NOT NULL,
    case_version integer NOT NULL,
    note_start integer NOT NULL CHECK(note_start >= 0),
    note_sha256 text NOT NULL,
    PRIMARY KEY (tenant_id, case_id, document_id),
    FOREIGN KEY (tenant_id,case_id,document_id)
      REFERENCES prior_auth_intake.receipts(tenant_id,case_id,document_id)
);
CREATE TABLE IF NOT EXISTS prior_auth_intake.bindings (
    tenant_id text NOT NULL,
    case_id text NOT NULL,
    binding_sha256 text NOT NULL,
    PRIMARY KEY (tenant_id, case_id)
);
REVOKE ALL ON SCHEMA prior_auth_intake FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA prior_auth_intake FROM PUBLIC;
