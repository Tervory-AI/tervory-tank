-- Market Lab box. Additive and idempotent. Applied by the agent on start.
-- Predictions are append-only: the application inserts a new row to resolve
-- or correct one. It never updates a row that was already inserted.

CREATE SCHEMA IF NOT EXISTS agent_market_lab;

CREATE TABLE IF NOT EXISTS agent_market_lab.series (
    id          text PRIMARY KEY,
    tenant_id   uuid NOT NULL,
    source      text NOT NULL,
    ref         text NOT NULL,
    unit        text NOT NULL,
    engine      text NOT NULL
);

CREATE INDEX IF NOT EXISTS series_tenant_idx
    ON agent_market_lab.series (tenant_id, source);

CREATE TABLE IF NOT EXISTS agent_market_lab.points (
    series_id   text NOT NULL,
    date        text NOT NULL,
    value       numeric NOT NULL,
    fetched_at  text NOT NULL,
    PRIMARY KEY (series_id, date)
);

CREATE TABLE IF NOT EXISTS agent_market_lab.events (
    series_id   text NOT NULL,
    date        text NOT NULL,
    kind        text NOT NULL,
    size        numeric NOT NULL,
    PRIMARY KEY (series_id, date, kind)
);

CREATE TABLE IF NOT EXISTS agent_market_lab.opportunities (
    id            uuid PRIMARY KEY,
    tenant_id     uuid NOT NULL,
    made_at       timestamptz NOT NULL,
    area          text NOT NULL,
    segment       text NOT NULL,
    demand_idx    numeric NOT NULL,
    supply_idx    numeric NOT NULL,
    gap           numeric NOT NULL,
    saturation    numeric NOT NULL,
    reachability  numeric NOT NULL,
    trend         jsonb NOT NULL,
    rank          integer NOT NULL,
    evidence      jsonb NOT NULL
);

CREATE INDEX IF NOT EXISTS opportunities_tenant_idx
    ON agent_market_lab.opportunities (tenant_id, made_at);

CREATE TABLE IF NOT EXISTS agent_market_lab.predictions (
    id                uuid PRIMARY KEY,
    tenant_id         uuid NOT NULL,
    made_at           timestamptz NOT NULL,
    statement         text NOT NULL,
    metric_series_id  text NOT NULL,
    comparator        text NOT NULL,
    target            numeric NOT NULL,
    resolve_by        timestamptz NOT NULL,
    rationale         text NOT NULL,
    sources           jsonb NOT NULL,
    outcome           text,
    resolved_at       timestamptz,
    score             numeric
);

CREATE INDEX IF NOT EXISTS predictions_tenant_idx
    ON agent_market_lab.predictions (tenant_id, resolve_by);

CREATE TABLE IF NOT EXISTS agent_market_lab.reports (
    id          uuid PRIMARY KEY,
    tenant_id   uuid NOT NULL,
    made_at     timestamptz NOT NULL,
    question    text NOT NULL,
    answer      text NOT NULL,
    citations   jsonb NOT NULL
);

CREATE INDEX IF NOT EXISTS reports_tenant_idx
    ON agent_market_lab.reports (tenant_id, made_at);

-- Provenance on every stored point. A batch stays out of the pool until it passes.
ALTER TABLE agent_market_lab.series ADD COLUMN IF NOT EXISTS region text NOT NULL DEFAULT '';
ALTER TABLE agent_market_lab.series ADD COLUMN IF NOT EXISTS currency text NOT NULL DEFAULT '';
ALTER TABLE agent_market_lab.series ADD COLUMN IF NOT EXISTS jump_limit numeric NOT NULL DEFAULT 10;

ALTER TABLE agent_market_lab.points ADD COLUMN IF NOT EXISTS source text NOT NULL DEFAULT '';
ALTER TABLE agent_market_lab.points ADD COLUMN IF NOT EXISTS region text NOT NULL DEFAULT '';
ALTER TABLE agent_market_lab.points ADD COLUMN IF NOT EXISTS currency text NOT NULL DEFAULT '';
ALTER TABLE agent_market_lab.points ADD COLUMN IF NOT EXISTS unit text NOT NULL DEFAULT '';
ALTER TABLE agent_market_lab.points ADD COLUMN IF NOT EXISTS batch_id text NOT NULL DEFAULT '';

CREATE TABLE IF NOT EXISTS agent_market_lab.batches (
    id          text PRIMARY KEY,
    tenant_id   uuid NOT NULL,
    series_id   text NOT NULL,
    source      text NOT NULL,
    fetched_at  text NOT NULL,
    region      text NOT NULL,
    currency    text NOT NULL,
    unit        text NOT NULL,
    status      text NOT NULL,
    reason      text NOT NULL DEFAULT '',
    jump_limit  numeric NOT NULL DEFAULT 10,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS batches_tenant_idx
    ON agent_market_lab.batches (tenant_id, status);

CREATE TABLE IF NOT EXISTS agent_market_lab.batch_points (
    batch_id    text NOT NULL,
    tenant_id   uuid NOT NULL,
    series_id   text NOT NULL,
    date        text NOT NULL,
    value       numeric NOT NULL,
    source      text NOT NULL,
    fetched_at  text NOT NULL,
    region      text NOT NULL,
    currency    text NOT NULL,
    unit        text NOT NULL,
    PRIMARY KEY (batch_id, series_id, date)
);

CREATE TABLE IF NOT EXISTS agent_market_lab.official_values (
    tenant_id   uuid NOT NULL,
    series_id   text NOT NULL,
    date        text NOT NULL,
    value       numeric NOT NULL,
    PRIMARY KEY (tenant_id, series_id, date)
);
