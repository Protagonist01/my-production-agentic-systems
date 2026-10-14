CREATE SCHEMA runtime;
REVOKE ALL ON SCHEMA runtime FROM PUBLIC;

CREATE TABLE runtime.checkpoints (
    checkpoint_key text PRIMARY KEY CHECK (checkpoint_key <> ''),
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    version bigint NOT NULL DEFAULT 1 CHECK (version > 0)
);

CREATE TABLE runtime.reviews (
    review_key text PRIMARY KEY CHECK (review_key <> ''),
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    status text NOT NULL CHECK (status IN ('pending', 'resolved')),
    version bigint NOT NULL DEFAULT 1 CHECK (version > 0)
);

CREATE TABLE runtime.ledger (
    entry_key text PRIMARY KEY CHECK (entry_key <> ''),
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object')
);
