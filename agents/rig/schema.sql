-- Rig's room. Additive and idempotent. Applied by the agent on start.
-- Shoppers only see rows with approved = true. Imported rows are approved.
-- Suggested rows stay hidden until approve_fit sets approved.
-- Rejected rows have source 'rejected' and approved = false, so shoppers never see them.
-- answers stores one graph or setup per product, keyed by a hash of the catalogue.
-- fit_why stores why-text for one fit, keyed by a hash of its rule and note.
-- Import, a feed pull, a price watch, approve, and reject clear answers for that tenant.
-- fit_why is kept so a known fit is not sent to a model again.

CREATE SCHEMA IF NOT EXISTS agent_rig;

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS agent_rig.products (
    tenant_id   uuid NOT NULL,
    id          text NOT NULL,
    sku         text NOT NULL,
    gtin        text,
    name        text NOT NULL,
    brand       text NOT NULL,
    category    text NOT NULL,
    price       numeric NOT NULL,
    currency    text NOT NULL,
    image_url   text,
    url         text,
    family      text NOT NULL DEFAULT '',
    attributes  jsonb NOT NULL DEFAULT '{}'::jsonb,
    active      boolean NOT NULL DEFAULT true,
    updated_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, sku)
);

CREATE INDEX IF NOT EXISTS products_tenant_active ON agent_rig.products (tenant_id, active);

CREATE INDEX IF NOT EXISTS products_search_fts ON agent_rig.products
USING gin (to_tsvector('simple',
    coalesce(name, '') || ' ' || coalesce(brand, '') || ' ' || coalesce(sku, '') || ' ' || coalesce(attributes::text, '')
));

CREATE INDEX IF NOT EXISTS products_name_trgm ON agent_rig.products USING gin (name gin_trgm_ops);

CREATE TABLE IF NOT EXISTS agent_rig.fits (
    tenant_id     uuid NOT NULL,
    part_sku      text NOT NULL,
    fits_sku      text NOT NULL DEFAULT '',
    fits_family   text NOT NULL DEFAULT '',
    rule          jsonb NOT NULL DEFAULT '{}'::jsonb,
    source        text NOT NULL,
    confidence    numeric,
    approved      boolean NOT NULL DEFAULT false,
    note          text NOT NULL DEFAULT '',
    PRIMARY KEY (tenant_id, part_sku, fits_sku, fits_family),
    CONSTRAINT fits_one_target CHECK (
        (fits_sku <> '' AND fits_family = '') OR (fits_sku = '' AND fits_family <> '')
    )
);

CREATE INDEX IF NOT EXISTS fits_tenant_idx ON agent_rig.fits (tenant_id, part_sku);

CREATE TABLE IF NOT EXISTS agent_rig.families (
    tenant_id    uuid NOT NULL,
    family       text NOT NULL,
    member_skus  text[] NOT NULL DEFAULT '{}',
    PRIMARY KEY (tenant_id, family)
);

CREATE TABLE IF NOT EXISTS agent_rig.setup_templates (
    tenant_id  uuid NOT NULL,
    category   text NOT NULL,
    roles      jsonb NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (tenant_id, category)
);

CREATE TABLE IF NOT EXISTS agent_rig.keys (
    tenant_id   uuid NOT NULL,
    key_hash    text NOT NULL,
    kind        text NOT NULL,
    origins     text[] NOT NULL DEFAULT '{}',
    created_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (key_hash),
    CONSTRAINT keys_kind_chk CHECK (kind IN ('publishable', 'admin'))
);

CREATE INDEX IF NOT EXISTS keys_tenant_idx ON agent_rig.keys (tenant_id);

CREATE TABLE IF NOT EXISTS agent_rig.quotes (
    tenant_id   uuid NOT NULL,
    id          text PRIMARY KEY,
    payload     jsonb NOT NULL,
    contact     jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at  timestamptz NOT NULL DEFAULT now(),
    sent_at     timestamptz
);

CREATE INDEX IF NOT EXISTS quotes_tenant_created ON agent_rig.quotes (tenant_id, created_at DESC);

CREATE TABLE IF NOT EXISTS agent_rig.retailers (
    tenant_id  uuid PRIMARY KEY,
    slug       text NOT NULL,
    email      text,
    webhook    text
);

CREATE TABLE IF NOT EXISTS agent_rig.feeds (
    tenant_id  uuid NOT NULL,
    format     text NOT NULL,
    url        text NOT NULL,
    currency   text NOT NULL DEFAULT '',
    PRIMARY KEY (tenant_id, url)
);

CREATE TABLE IF NOT EXISTS agent_rig.answers (
    tenant_id   uuid NOT NULL,
    kind        text NOT NULL,
    product_id  text NOT NULL,
    version     text NOT NULL,
    body        jsonb NOT NULL,
    PRIMARY KEY (tenant_id, kind, product_id)
);

CREATE TABLE IF NOT EXISTS agent_rig.fit_why (
    tenant_id   uuid NOT NULL,
    fit_id      text NOT NULL,
    rule_hash   text NOT NULL,
    why         jsonb NOT NULL,
    PRIMARY KEY (tenant_id, fit_id, rule_hash)
);
