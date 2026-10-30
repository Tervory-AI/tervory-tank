-- RX-5: applied by agent_radix in its own pre-provisioned schema.
-- No new role, public grant, extension, sequence or change to Tank's tables.
CREATE TABLE IF NOT EXISTS agent_radix.business_runs (
    tenant_id uuid NOT NULL,
    id uuid NOT NULL,
    region text NOT NULL CHECK (region IN ('us-east', 'za')),
    skill text NOT NULL CHECK (skill IN ('verify_business', 'entity_links', 'account_links', 'site_risk', 'business_risk')),
    result jsonb NOT NULL CHECK (jsonb_typeof(result) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, id),
    CHECK (result->>'tenant_id' IS NOT NULL AND result->>'tenant_id' = tenant_id::text),
    CHECK (result->>'region' IS NOT NULL AND result->>'region' = region)
);
CREATE INDEX IF NOT EXISTS business_runs_tenant_created
    ON agent_radix.business_runs (tenant_id, created_at DESC);
CREATE TABLE IF NOT EXISTS agent_radix.business_sources (
    tenant_id uuid NOT NULL,
    run_id uuid NOT NULL,
    source_id text NOT NULL,
    catalogue jsonb NOT NULL CHECK (jsonb_typeof(catalogue) = 'object'),
    PRIMARY KEY (tenant_id, run_id, source_id),
    FOREIGN KEY (tenant_id, run_id) REFERENCES agent_radix.business_runs (tenant_id, id),
    CHECK (catalogue->>'tenant_id' IS NOT NULL AND catalogue->>'tenant_id' = tenant_id::text),
    CHECK (catalogue->>'id' IS NOT NULL AND catalogue->>'id' = source_id)
);

-- BEGIN GENERATED AGENT MEMORY (hermes/record_schema.py)
CREATE TABLE IF NOT EXISTS agent_radix.memory_records (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    agent text NOT NULL DEFAULT 'radix' CHECK (agent = 'radix'),
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
CREATE INDEX IF NOT EXISTS memory_records_scope ON agent_radix.memory_records (tenant_id, tier, created_at, id);
CREATE INDEX IF NOT EXISTS memory_records_encoder ON agent_radix.memory_records (tenant_id, embed_model);
CREATE TABLE IF NOT EXISTS agent_radix.memory_index_jobs (
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
CREATE INDEX IF NOT EXISTS memory_index_jobs_due ON agent_radix.memory_index_jobs (run_at);
CREATE TABLE IF NOT EXISTS agent_radix.memory_publish_policy (
    tenant_id uuid PRIMARY KEY,
    enabled boolean NOT NULL DEFAULT false,
    identifiers jsonb NOT NULL DEFAULT '{}',
    updated_by text NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS agent_radix.memory_publish_log (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    actor text NOT NULL,
    happened_at timestamptz NOT NULL DEFAULT now(),
    source_row uuid NOT NULL,
    result text NOT NULL CHECK (result IN ('disabled','missing','refused','published','already_published')),
    published_row uuid
);
-- END GENERATED AGENT MEMORY
