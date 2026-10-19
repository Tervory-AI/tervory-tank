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
