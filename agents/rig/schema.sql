-- Rig's room. Additive and idempotent. Applied by the agent on start.
-- Shoppers only see rows with approved = true. Imported rows are approved.
-- Suggested rows stay hidden until approve_fit sets approved.
-- Rejected rows have source 'rejected' and approved = false, so shoppers never see them.
-- answers stores one graph or setup per product, keyed by a hash of the catalogue.
-- fit_why stores why-text for one fit, keyed by a hash of its rule and note.
-- Import, a feed pull, a price watch, approve, and reject clear answers for that tenant.
-- fit_why is kept so a known fit is not sent to a model again.
-- searches keeps each finished shopper search for that tenant.
-- A later search reads only the newest rows inside the recall window
-- (RIG_SEARCH_RECALL_DAYS, default 90), at most 500, newest first.
-- A nightly job deletes rows older than that same window.
-- A changed catalogue is not reused. A search from another tenant is never read.
-- market_prices is not the catalogue. Search does not read it.
-- Each row is one other seller's price for a sku this retailer already stocks.
-- The sheet is a separate import. A later price reader is the intended feed.
-- When a sku has no rows, the shopper is told the figure is not available.
-- retailers.name is the label on that retailer's own price.

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
    webhook    text,
    name       text NOT NULL DEFAULT ''
);

ALTER TABLE agent_rig.retailers ADD COLUMN IF NOT EXISTS name text NOT NULL DEFAULT '';

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

CREATE TABLE IF NOT EXISTS agent_rig.market_prices (
    tenant_id  uuid NOT NULL,
    sku        text NOT NULL,
    source     text NOT NULL,
    price      numeric NOT NULL,
    currency   text NOT NULL,
    seen_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, sku, source)
);

CREATE INDEX IF NOT EXISTS market_prices_tenant_sku ON agent_rig.market_prices (tenant_id, sku);

CREATE TABLE IF NOT EXISTS agent_rig.searches (
    tenant_id     uuid NOT NULL,
    id            text NOT NULL,
    version       text NOT NULL,
    query         text NOT NULL,
    host          text NOT NULL DEFAULT '',
    signature     text NOT NULL,
    result_limit  integer NOT NULL,
    ids           jsonb NOT NULL,
    exact_match   boolean NOT NULL DEFAULT true,
    message       text,
    parts         jsonb NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, id)
);

CREATE INDEX IF NOT EXISTS searches_tenant_version ON agent_rig.searches (tenant_id, version);

CREATE INDEX IF NOT EXISTS searches_tenant_created
    ON agent_rig.searches (tenant_id, created_at DESC);

-- RIG-4: durable retailer handoff and anonymous daily widget counts.
CREATE TABLE IF NOT EXISTS agent_rig.quote_handoffs (
    tenant_id uuid NOT NULL,
    quote_id text NOT NULL REFERENCES agent_rig.quotes(id) ON DELETE CASCADE,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'sending', 'sent')),
    error text,
    attempts integer NOT NULL DEFAULT 0,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, quote_id)
);

CREATE TABLE IF NOT EXISTS agent_rig.widget_counts (
    tenant_id uuid NOT NULL,
    day date NOT NULL,
    event text NOT NULL CHECK (event IN ('searches', 'setups_opened', 'swaps', 'quotes', 'no_results')),
    count bigint NOT NULL DEFAULT 0 CHECK (count >= 0),
    PRIMARY KEY (tenant_id, day, event)
);
-- End RIG-4.

-- RIG-4b: short-lived per-client/route abuse limits, never joined to analytics.
ALTER TABLE agent_rig.quote_handoffs ADD COLUMN IF NOT EXISTS next_attempt_at timestamptz DEFAULT now();
ALTER TABLE agent_rig.quote_handoffs ADD COLUMN IF NOT EXISTS needs_attention boolean NOT NULL DEFAULT false;
CREATE INDEX IF NOT EXISTS quote_handoffs_due ON agent_rig.quote_handoffs(tenant_id, next_attempt_at)
    WHERE NOT needs_attention AND status <> 'sent';
CREATE TABLE IF NOT EXISTS agent_rig.widget_search_events (
    tenant_id uuid NOT NULL,
    event_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, event_id)
);
CREATE TABLE IF NOT EXISTS agent_rig.rate_windows (
    tenant_id uuid NOT NULL,
    window_id bigint NOT NULL,
    salt bytea NOT NULL,
    PRIMARY KEY (tenant_id, window_id)
);
CREATE TABLE IF NOT EXISTS agent_rig.rate_counts (
    tenant_id uuid NOT NULL,
    window_id bigint NOT NULL,
    route text NOT NULL,
    client_hash bytea NOT NULL,
    hits integer NOT NULL CHECK (hits > 0),
    PRIMARY KEY (tenant_id, window_id, route, client_hash),
    FOREIGN KEY (tenant_id, window_id) REFERENCES agent_rig.rate_windows(tenant_id, window_id) ON DELETE CASCADE
);
-- End RIG-4b.

-- RIG-3: private price inputs and per-file import receipts.
-- Public product queries never select these tables.
CREATE TABLE IF NOT EXISTS agent_rig.price_rules (
    tenant_id uuid PRIMARY KEY,
    rule jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS agent_rig.exchange_rates (
    tenant_id uuid NOT NULL,
    currency text NOT NULL,
    rate numeric NOT NULL CHECK (rate > 0),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id,currency)
);
CREATE TABLE IF NOT EXISTS agent_rig.supplier_costs (
    tenant_id uuid NOT NULL,
    sku text NOT NULL,
    cost numeric NOT NULL CHECK (cost >= 0),
    currency text NOT NULL,
    provider text NOT NULL,
    site text NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id,sku)
);
CREATE TABLE IF NOT EXISTS agent_rig.feed_receipts (
    tenant_id uuid NOT NULL,
    id uuid NOT NULL,
    provider text NOT NULL,
    site text NOT NULL,
    added integer NOT NULL CHECK (added >= 0),
    updated integer NOT NULL CHECK (updated >= 0),
    rejected integer NOT NULL CHECK (rejected >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id,id)
);
CREATE INDEX IF NOT EXISTS rig_feed_receipts_tenant_created ON agent_rig.feed_receipts(tenant_id,created_at DESC);

-- RIG-3: source provenance for per-feed pricing. Amounts stay private.
ALTER TABLE agent_rig.supplier_costs ADD COLUMN IF NOT EXISTS feed_metadata jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE agent_rig.feed_receipts ADD COLUMN IF NOT EXISTS feed_id text NOT NULL DEFAULT '';

-- RIG-5: immutable model revisions, reviewed anchors and a per-tenant add-on.
-- A forge result is never a shopper asset until both automatic and human checks pass.
CREATE TABLE IF NOT EXISTS agent_rig.rig_3d_entitlements (
    tenant_id uuid PRIMARY KEY,
    enabled boolean NOT NULL DEFAULT false,
    price_amount numeric CHECK (price_amount >= 0),
    currency text NOT NULL DEFAULT 'USD' CHECK (currency ~ '^[A-Z]{3}$')
);

CREATE TABLE IF NOT EXISTS agent_rig.rig_3d_jobs (
    tenant_id uuid NOT NULL,
    id uuid NOT NULL,
    product_id text NOT NULL,
    request jsonb NOT NULL,
    status text NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued','running','failed','draft','approved')),
    report jsonb,
    reason text,
    review jsonb,
    reviewed_by text,
    created_at timestamptz NOT NULL DEFAULT now(),
    approved_at timestamptz,
    PRIMARY KEY (tenant_id,id),
    FOREIGN KEY (tenant_id,product_id) REFERENCES agent_rig.products (tenant_id,sku),
    CHECK (status <> 'approved' OR (report IS NOT NULL AND review IS NOT NULL AND approved_at IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS rig_3d_jobs_product
    ON agent_rig.rig_3d_jobs (tenant_id,product_id,status,approved_at DESC);

ALTER TABLE agent_rig.fits ADD COLUMN IF NOT EXISTS mount_points jsonb NOT NULL DEFAULT '{}'::jsonb;

CREATE TABLE IF NOT EXISTS agent_rig.rig_3d_kiosks (
    tenant_id uuid NOT NULL,
    id uuid NOT NULL,
    revision bigint NOT NULL DEFAULT 0 CHECK (revision >= 0),
    PRIMARY KEY (tenant_id,id)
);
-- End RIG-5.
