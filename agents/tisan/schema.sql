-- J4: submission is approval; only item identifiers/quantities and email are kept.
CREATE TABLE IF NOT EXISTS agent_tisan.quote_requests (
    tenant_id uuid NOT NULL,
    id uuid NOT NULL,
    contact jsonb NOT NULL CHECK (jsonb_typeof(contact) = 'object'),
    items jsonb NOT NULL CHECK (jsonb_typeof(items) = 'array'),
    state text NOT NULL CHECK (state IN ('draft','submitted','acknowledged','quoted','accepted','declined')),
    mail_state text NOT NULL DEFAULT 'pending'
        CHECK (mail_state IN ('pending','sending','sent','uncertain')),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,id)
);
CREATE INDEX IF NOT EXISTS quote_requests_tenant_created
    ON agent_tisan.quote_requests (tenant_id,created_at DESC,id DESC);
CREATE TABLE IF NOT EXISTS agent_tisan.quote_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id uuid NOT NULL,
    request_id uuid NOT NULL,
    from_state text,
    to_state text NOT NULL,
    actor text NOT NULL CHECK (length(btrim(actor)) BETWEEN 1 AND 256),
    happened_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (tenant_id,request_id) REFERENCES agent_tisan.quote_requests (tenant_id,id),
    CHECK (from_state IS NOT NULL OR to_state='draft'),
    CHECK ((from_state IS NULL AND to_state='draft') OR
        (from_state='draft' AND to_state='submitted') OR
        (from_state='submitted' AND to_state='acknowledged') OR
        (from_state='acknowledged' AND to_state='quoted') OR
        (from_state='quoted' AND to_state IN ('accepted','declined')))
);
CREATE INDEX IF NOT EXISTS quote_events_tenant_request
    ON agent_tisan.quote_events (tenant_id,request_id,id);
-- Follow the platform RLS rollout; never turn RLS on by itself (the pattern of
-- tank.personal_tokens in tank/schema.sql). An unconditional ENABLE here made Tank's
-- startup guard (tank/main.py _startup) refuse its owner login on 1 Nov 2026. Until
-- the rollout reaches tank.command_threads, these tables stay without RLS, and
-- isolation is the tenant_id filter on every quote query (agents/tisan/quotes.py).
-- The ELSE branch also turns RLS back off where it was already applied.
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_class WHERE oid=to_regclass('tank.command_threads') AND relrowsecurity) THEN
        ALTER TABLE agent_tisan.quote_requests ENABLE ROW LEVEL SECURITY;
        ALTER TABLE agent_tisan.quote_requests FORCE ROW LEVEL SECURITY;
        ALTER TABLE agent_tisan.quote_events ENABLE ROW LEVEL SECURITY;
        ALTER TABLE agent_tisan.quote_events FORCE ROW LEVEL SECURITY;
    ELSE
        ALTER TABLE agent_tisan.quote_requests NO FORCE ROW LEVEL SECURITY;
        ALTER TABLE agent_tisan.quote_requests DISABLE ROW LEVEL SECURITY;
        ALTER TABLE agent_tisan.quote_events NO FORCE ROW LEVEL SECURITY;
        ALTER TABLE agent_tisan.quote_events DISABLE ROW LEVEL SECURITY;
    END IF;
END $$;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='agent_tisan'
        AND tablename='quote_requests' AND policyname='quote_requests_tenant') THEN
        CREATE POLICY quote_requests_tenant ON agent_tisan.quote_requests
            USING (tenant_id = nullif(current_setting('app.tenant_id',true),'')::uuid)
            WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id',true),'')::uuid);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='agent_tisan'
        AND tablename='quote_events' AND policyname='quote_events_tenant') THEN
        CREATE POLICY quote_events_tenant ON agent_tisan.quote_events
            USING (tenant_id = nullif(current_setting('app.tenant_id',true),'')::uuid)
            WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id',true),'')::uuid);
    END IF;
END $$;
-- Schemas may be installed before room roles are provisioned. Reapplying after
-- provisioning grants only the existing room role; policies remain enforced.
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='agent_tisan') THEN
        GRANT SELECT,INSERT,UPDATE ON agent_tisan.quote_requests TO agent_tisan;
        GRANT SELECT,INSERT ON agent_tisan.quote_events TO agent_tisan;
        GRANT USAGE,SELECT ON SEQUENCE agent_tisan.quote_events_id_seq TO agent_tisan;
    END IF;
END $$;

-- BEGIN GENERATED AGENT MEMORY (hermes/record_schema.py)
CREATE TABLE IF NOT EXISTS agent_tisan.memory_records (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    agent text NOT NULL DEFAULT 'tisan' CHECK (agent = 'tisan'),
    claim text NOT NULL CHECK (length(claim) BETWEEN 1 AND 8000),
    evidence jsonb NOT NULL DEFAULT '[]' CHECK (jsonb_typeof(evidence) = 'array'),
    confidence double precision NOT NULL DEFAULT 0.5 CHECK (confidence BETWEEN 0 AND 1),
    last_verified timestamptz,
    embed_model text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    tier text NOT NULL DEFAULT 'client' CHECK (tier IN ('client','platform')),
    kind text NOT NULL DEFAULT 'fact',
    meta jsonb NOT NULL DEFAULT '{}',
    seen integer NOT NULL DEFAULT 1,
    CHECK (tier <> 'platform' OR tenant_id = '00000000-0000-0000-0000-000000000001'::uuid)
);
CREATE INDEX IF NOT EXISTS memory_records_scope ON agent_tisan.memory_records (tenant_id, tier, created_at, id);
CREATE INDEX IF NOT EXISTS memory_records_encoder ON agent_tisan.memory_records (tenant_id, embed_model);
CREATE TABLE IF NOT EXISTS agent_tisan.memory_index_jobs (
    row_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    target_model text NOT NULL,
    operation text NOT NULL DEFAULT 'upsert' CHECK (operation IN ('upsert','delete')),
    attempts integer NOT NULL DEFAULT 0,
    run_at timestamptz NOT NULL DEFAULT now(),
    last_error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, row_id, target_model, operation)
);
CREATE INDEX IF NOT EXISTS memory_index_jobs_due ON agent_tisan.memory_index_jobs (run_at);
CREATE TABLE IF NOT EXISTS agent_tisan.memory_publish_policy (
    tenant_id uuid PRIMARY KEY,
    enabled boolean NOT NULL DEFAULT false,
    identifiers jsonb NOT NULL DEFAULT '{}',
    updated_by text NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS agent_tisan.memory_publish_log (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    actor text NOT NULL,
    happened_at timestamptz NOT NULL DEFAULT now(),
    source_row uuid NOT NULL,
    result text NOT NULL CHECK (result IN ('disabled','missing','refused','published','already_published')),
    published_row uuid
);
-- END GENERATED AGENT MEMORY
