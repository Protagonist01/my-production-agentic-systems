CREATE TABLE olist_intent.challenges (
    tenant_id text NOT NULL,
    case_id text NOT NULL,
    token_hash text UNIQUE NOT NULL,
    state text NOT NULL CHECK(state IN ('pending','confirmed','consumed')),
    document jsonb NOT NULL,
    PRIMARY KEY(tenant_id,case_id),
    FOREIGN KEY(tenant_id,case_id) REFERENCES olist_app.cases(tenant_id,case_id)
);

-- Exact migration history, never a claim of retroactive customer consent.
CREATE TABLE olist_intent.legacy_refunds (
    tenant_id text NOT NULL,
    operation_id text NOT NULL,
    document jsonb NOT NULL,
    PRIMARY KEY(tenant_id,operation_id)
);
INSERT INTO olist_intent.legacy_refunds
SELECT tenant_id,operation_id,to_jsonb(r) FROM olist.refunds AS r;

CREATE FUNCTION olist_intent.lock_customer_account() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $account_guard$
BEGIN
    PERFORM pg_advisory_xact_lock(hashtextextended('olist-intent-account-v1|' || OLD.username,0));
    IF TG_OP='DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END;
$account_guard$;
CREATE TRIGGER olist_customer_account_change
BEFORE UPDATE OR DELETE ON olist_app.accounts
FOR EACH ROW EXECUTE FUNCTION olist_intent.lock_customer_account();

CREATE FUNCTION olist_intent.stamp_customer_authority() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $state_guard$
BEGIN
    IF TG_OP='INSERT' THEN
        IF NEW.state<>'pending' AND current_setting('is_superuser')<>'on' THEN
            RAISE EXCEPTION 'customer authority must begin pending' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
    END IF;
    IF OLD.state='consumed' THEN
        RAISE EXCEPTION 'consumed customer authority is immutable' USING ERRCODE='23514';
    END IF;
    IF NEW.state IN ('confirmed','consumed') THEN
        IF (NEW.document->>'expires_at')::timestamptz<=clock_timestamp() THEN
            RAISE EXCEPTION 'customer authority expired' USING ERRCODE='23514';
        END IF;
    END IF;
    IF NEW.state='confirmed' THEN
        IF OLD.state<>'pending' THEN
            RAISE EXCEPTION 'customer authority transition invalid' USING ERRCODE='23514';
        END IF;
        NEW.document=jsonb_set(NEW.document,'{confirmed_at}',to_jsonb(clock_timestamp()));
    END IF;
    IF NEW.state='consumed' THEN
        IF OLD.state<>'confirmed' THEN
            RAISE EXCEPTION 'customer confirmation missing' USING ERRCODE='23514';
        END IF;
        NEW.document=jsonb_set(NEW.document,'{consumed_at}',to_jsonb(clock_timestamp()));
    END IF;
    RETURN NEW;
END;
$state_guard$;
CREATE TRIGGER olist_customer_authority_state
BEFORE INSERT OR UPDATE ON olist_intent.challenges
FOR EACH ROW EXECUTE FUNCTION olist_intent.stamp_customer_authority();

CREATE FUNCTION olist_intent.require_customer_authority() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $refund_guard$
DECLARE customer_name text;
BEGIN
    IF EXISTS(SELECT 1 FROM olist_intent.legacy_refunds l
        WHERE l.tenant_id=NEW.tenant_id AND l.operation_id=NEW.operation_id
        AND l.document=to_jsonb(NEW)) THEN RETURN NEW; END IF;
    SELECT ch.document->'customer'->>'username' INTO customer_name
      FROM olist_intent.challenges ch
      WHERE ch.tenant_id=NEW.tenant_id
        AND ch.document->'command'->>'business_operation_id'=NEW.operation_id;
    IF customer_name IS NULL THEN
        RAISE EXCEPTION 'customer transaction authority missing' USING ERRCODE='23514';
    END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended('olist-intent-account-v1|' || customer_name,0));
    IF NOT EXISTS(
        SELECT 1 FROM olist_intent.challenges ch
        JOIN olist_app.cases c ON c.tenant_id=ch.tenant_id AND c.case_id=ch.case_id
        LEFT JOIN olist_app.accounts a ON a.username=customer_name
        WHERE ch.tenant_id=NEW.tenant_id AND ch.state='consumed'
        AND ch.document->'customer'->>'role'='customer'
        AND ch.document->'customer'->>'tenant_id'=NEW.tenant_id
        AND (ch.document->'customer'->'order_ids') ? NEW.order_id
        AND ((ch.document->>'consumed_at')::timestamptz<transaction_timestamp()
            OR (a.enabled AND a.principal=ch.document->'customer'))
        AND ch.document->'command'=c.document->'command'
        AND ch.document->>'policy_version'='olist-canceled-full-refund-sim-v1'
        AND c.document->'context'->'versions'->>'policy'=ch.document->>'policy_version'
        AND ch.document->'command'->>'tenant_id'=NEW.tenant_id
        AND ch.document->'command'->>'order_id'=NEW.order_id
        AND ch.document->'command'->>'business_operation_id'=NEW.operation_id
        AND (ch.document->'command'->>'amount_minor')::bigint=NEW.amount_minor
        AND (ch.document->'command'->>'expected_version')::bigint
            =(NEW.receipt->>'order_version')::bigint-1
        AND ch.document->'consumed_receipt'=NEW.receipt
        AND ch.document->>'confirmed_at' IS NOT NULL
        AND (ch.document->>'consumed_at')::timestamptz
            >=(ch.document->>'confirmed_at')::timestamptz
        AND (ch.document->>'consumed_at')::timestamptz
            <(ch.document->>'expires_at')::timestamptz
        -- Previously consumed history may be copied by the isolated admin restore.
        -- New consumption is DB-stamped within this transaction and must still be fresh.
        AND ((ch.document->>'consumed_at')::timestamptz<transaction_timestamp()
            OR (ch.document->>'expires_at')::timestamptz>clock_timestamp())
        AND c.version=(ch.document->>'case_version')::bigint+1
        AND c.document->>'action_digest'=ch.document->>'action_digest'
        AND c.document->>'record_pin'=ch.document->>'record_pin'
        AND c.status='committed' AND c.document->'result'->'receipt'=NEW.receipt
        AND (NOT (c.document->'request'->>'require_review')::boolean
            OR (c.document->>'approved_by' IS NOT NULL
                AND (c.document->>'approval_version')::bigint
                    =(ch.document->>'case_version')::bigint))
        AND EXISTS(SELECT 1 FROM olist_app.events e
            WHERE e.tenant_id=c.tenant_id AND e.case_id=c.case_id
            AND e.kind='committed' AND e.detail->>'ledger_id'=NEW.receipt->>'ledger_id')
    ) THEN
        RAISE EXCEPTION 'customer transaction authority incomplete' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END;
$refund_guard$;
CREATE CONSTRAINT TRIGGER olist_customer_authority_commit
AFTER INSERT ON olist.refunds DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION olist_intent.require_customer_authority();

CREATE FUNCTION olist_intent.require_customer_order_effect() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $order_guard$
BEGIN
    IF NEW.refunded_minor<>OLD.refunded_minor THEN
        IF OLD.refunded_minor<>0 OR NEW.refunded_minor<=0 OR NEW.refunded_minor>10000
            OR NEW.version<>OLD.version+1
            OR NOT EXISTS(SELECT 1 FROM olist.refunds r
                WHERE r.tenant_id=NEW.tenant_id AND r.order_id=NEW.order_id
                AND r.amount_minor=NEW.refunded_minor-OLD.refunded_minor
                AND (r.receipt->>'order_version')::bigint=NEW.version) THEN
            RAISE EXCEPTION 'refund balance requires matching receipt' USING ERRCODE='23514';
        END IF;
    END IF;
    RETURN NEW;
END;
$order_guard$;
CREATE CONSTRAINT TRIGGER olist_customer_order_effect
AFTER UPDATE ON olist.orders DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION olist_intent.require_customer_order_effect();
