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

-- Durable handoff to Tank's save_pair collector. No contact details or keys.
-- Events are removed only in the same transaction that stores the training pair.
CREATE TABLE IF NOT EXISTS agent_rig.training_events (
    tenant_id uuid NOT NULL,
    region text NOT NULL,
    source text NOT NULL CHECK (source IN ('rig_no_result', 'rig_quote')),
    source_ref text NOT NULL,
    input jsonb NOT NULL,
    output jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, region, source, source_ref)
);

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

-- Append-only event history. Consumer retries never overwrite earlier prices.
CREATE TABLE IF NOT EXISTS agent_rig.price_history (
    tenant_id uuid NOT NULL,
    product_id text NOT NULL,
    price numeric NOT NULL CHECK(price >= 0 AND price < 'Infinity'::numeric),
    currency text NOT NULL CHECK(currency ~ '^[A-Z]{3}$'),
    observed_at timestamptz NOT NULL,
    event_id uuid PRIMARY KEY
);
CREATE INDEX IF NOT EXISTS price_history_tenant_product
    ON agent_rig.price_history(tenant_id,product_id,observed_at,event_id);

-- Tiger retries are idempotent and cannot replace a newer confirmed observation.
CREATE TABLE IF NOT EXISTS agent_rig.tiger_receipts (
    tenant_id uuid NOT NULL,
    sku text NOT NULL,
    url text NOT NULL,
    observed_at timestamptz NOT NULL,
    PRIMARY KEY (tenant_id, sku, url),
    FOREIGN KEY (tenant_id, sku) REFERENCES agent_rig.products(tenant_id, sku) ON DELETE CASCADE
);

-- Manual removal survives feed refresh and restart. Only a manual import clears it.
CREATE TABLE IF NOT EXISTS agent_rig.deleted_products (
    tenant_id uuid NOT NULL,
    sku text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, sku)
);

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
ALTER TABLE agent_rig.retailers ADD COLUMN IF NOT EXISTS theme text NOT NULL DEFAULT 'neutral'
    CHECK (theme IN ('neutral', 'custom-nation'));
ALTER TABLE agent_rig.retailers ADD COLUMN IF NOT EXISTS quote_notice jsonb;
-- Optional cross-store fulfilment (Locate). Off for every store until it opts in.
-- Off means no supply lookup in search or quotes and no locate, confirm or accept.
ALTER TABLE agent_rig.retailers ADD COLUMN IF NOT EXISTS locate_enabled boolean NOT NULL DEFAULT false;
-- Optional blind ship: Locate orders ship from the other store straight to the shopper. Off by default.
ALTER TABLE agent_rig.retailers ADD COLUMN IF NOT EXISTS blind_ship boolean NOT NULL DEFAULT false;
-- Optional auto-order: send the PO to the approved source (sandbox outbox only). Off by default.
ALTER TABLE agent_rig.retailers ADD COLUMN IF NOT EXISTS auto_order boolean NOT NULL DEFAULT false;

CREATE TABLE IF NOT EXISTS agent_rig.feeds (
    tenant_id  uuid NOT NULL,
    format     text NOT NULL,
    url        text NOT NULL,
    currency   text NOT NULL DEFAULT '',
    PRIMARY KEY (tenant_id, url)
);

-- Legacy feed rows predate supplier_costs. Until a feed refresh records its
-- product membership, its tenant's provenance is unknown and Tiger fails closed.
ALTER TABLE agent_rig.feeds ADD COLUMN IF NOT EXISTS watch_indexed boolean NOT NULL DEFAULT false;
CREATE TABLE IF NOT EXISTS agent_rig.feed_products (
    tenant_id uuid NOT NULL, sku text NOT NULL, feed_url text NOT NULL,
    PRIMARY KEY (tenant_id, sku, feed_url),
    FOREIGN KEY (tenant_id, sku) REFERENCES agent_rig.products(tenant_id, sku) ON DELETE CASCADE
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

-- Prompt2: approved store supplier network. Private inputs never selected as products.
ALTER TABLE agent_rig.products ADD COLUMN IF NOT EXISTS mpn text;
CREATE TABLE IF NOT EXISTS agent_rig.supply_sources (
    tenant_id uuid NOT NULL,
    id text NOT NULL,
    approved boolean NOT NULL DEFAULT false,
    priority integer NOT NULL DEFAULT 0,
    max_offer_age_seconds integer NOT NULL CHECK (max_offer_age_seconds > 0),
    PRIMARY KEY (tenant_id, id)
);
CREATE TABLE IF NOT EXISTS agent_rig.supply_offers (
    tenant_id uuid NOT NULL,
    source_id text NOT NULL,
    sku text NOT NULL,
    gtin text,
    brand text NOT NULL,
    mpn text,
    quantity numeric CHECK (quantity >= 0 AND quantity < 'Infinity'::numeric),
    status text NOT NULL CHECK (status IN ('available', 'unavailable', 'unknown')),
    eta text,
    ship_days integer CHECK (ship_days >= 0),
    region text NOT NULL,
    cost numeric NOT NULL CHECK (cost >= 0 AND cost < 'Infinity'::numeric),
    currency text NOT NULL,
    seen_at timestamptz NOT NULL,
    PRIMARY KEY (tenant_id, source_id, sku),
    FOREIGN KEY (tenant_id, source_id) REFERENCES agent_rig.supply_sources(tenant_id, id)
);
CREATE TABLE IF NOT EXISTS agent_rig.supply_sku_map (
    tenant_id uuid NOT NULL,
    product_sku text NOT NULL,
    source_id text NOT NULL,
    offer_sku text NOT NULL,
    PRIMARY KEY (tenant_id, product_sku, source_id, offer_sku),
    FOREIGN KEY (tenant_id, product_sku) REFERENCES agent_rig.products(tenant_id, sku),
    FOREIGN KEY (tenant_id, source_id, offer_sku) REFERENCES agent_rig.supply_offers(tenant_id, source_id, sku)
);

-- Located counts mean persisted quote requests, never sales or estimates.
ALTER TABLE agent_rig.widget_counts ADD COLUMN IF NOT EXISTS located_count bigint NOT NULL DEFAULT 0 CHECK (located_count >= 0);
ALTER TABLE agent_rig.widget_counts ADD COLUMN IF NOT EXISTS kept_revenue jsonb NOT NULL DEFAULT '{}'::jsonb;
CREATE TABLE IF NOT EXISTS agent_rig.supply_sale_receipts (
    tenant_id uuid NOT NULL,
    receipt_id text NOT NULL,
    quote_id text NOT NULL,
    product_id text NOT NULL,
    amount numeric NOT NULL CHECK (amount > '-Infinity'::numeric AND amount < 'Infinity'::numeric),
    currency text NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
    source_ref text NOT NULL,
    received_at timestamptz NOT NULL,
    PRIMARY KEY (tenant_id, receipt_id)
);
-- Distinguish a feed's zero stock from a deliberately disabled catalogue item.
ALTER TABLE agent_rig.products ADD COLUMN IF NOT EXISTS supply_eligible boolean NOT NULL DEFAULT false;
-- Preserve the existing feed pricing scope identity instead of inventing one.
ALTER TABLE agent_rig.supply_sources ADD COLUMN IF NOT EXISTS provider text NOT NULL DEFAULT '';
ALTER TABLE agent_rig.supply_sources ADD COLUMN IF NOT EXISTS site text NOT NULL DEFAULT '';
ALTER TABLE agent_rig.supply_sources ADD COLUMN IF NOT EXISTS feed_id text NOT NULL DEFAULT '';
-- Blind ship: this source must pack a neutral slip (no own branding or invoice in the parcel).
ALTER TABLE agent_rig.supply_sources ADD COLUMN IF NOT EXISTS neutral_slip_required boolean NOT NULL DEFAULT false;
-- Auto-order: the approved source's real vendor name and order inbox (not its site URL).
ALTER TABLE agent_rig.supply_sources ADD COLUMN IF NOT EXISTS vendor_name text NOT NULL DEFAULT '';
ALTER TABLE agent_rig.supply_sources ADD COLUMN IF NOT EXISTS order_email text NOT NULL DEFAULT '';

-- Locate confirm. The offer page is re-read live before any hold is issued.
ALTER TABLE agent_rig.supply_offers ADD COLUMN IF NOT EXISTS url text;
-- A hold is a short-lived, single-use price snapshot after a live check.
-- private holds the supplier evidence and is never returned to a shopper.
CREATE TABLE IF NOT EXISTS agent_rig.supply_holds (
    tenant_id uuid NOT NULL,
    id text NOT NULL,
    product_id text NOT NULL,
    public jsonb NOT NULL,
    private jsonb NOT NULL,
    expires_at timestamptz NOT NULL,
    used_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, id)
);
CREATE INDEX IF NOT EXISTS supply_holds_expiry ON agent_rig.supply_holds (expires_at);

-- Locate orders live in Rig's own database (Tervory no longer uses Odoo).
-- One row per paid Locate Accept, keyed by its quote, so a retry never makes
-- a second order. Private store records: never returned to a shopper.
CREATE TABLE IF NOT EXISTS agent_rig.locate_orders (
    tenant_id uuid NOT NULL,
    quote_id text NOT NULL,
    number text NOT NULL,
    state text NOT NULL DEFAULT 'placed' CHECK (state IN ('placed', 'cancelled')),
    product_id text NOT NULL,
    price numeric(14, 2) NOT NULL CHECK (price > 0),
    currency text NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
    -- Blind ship only: the shopper's delivery address. NULL ships to the store.
    ship_to jsonb,
    cancel_reason text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, quote_id),
    UNIQUE (tenant_id, number)
);
-- The store's purchase order to the approved source, one per Locate order.
-- unit_cost is the source's live price: supplier-side only.
CREATE TABLE IF NOT EXISTS agent_rig.supplier_purchase_orders (
    tenant_id uuid NOT NULL,
    quote_id text NOT NULL,
    number text NOT NULL,
    state text NOT NULL DEFAULT 'draft' CHECK (state IN ('draft', 'sent', 'cancelled')),
    source_id text NOT NULL,
    vendor_name text NOT NULL DEFAULT '',
    order_email text NOT NULL DEFAULT '',
    item_sku text NOT NULL DEFAULT '',
    item_url text NOT NULL DEFAULT '',
    quantity integer NOT NULL DEFAULT 1 CHECK (quantity > 0),
    unit_cost numeric(14, 2) NOT NULL CHECK (unit_cost > 0),
    currency text NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
    -- Blind ship: ship straight to this address with a neutral slip if required.
    ship_to jsonb,
    neutral_slip boolean NOT NULL DEFAULT false,
    instructions text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, quote_id),
    UNIQUE (tenant_id, number),
    FOREIGN KEY (tenant_id, quote_id) REFERENCES agent_rig.locate_orders (tenant_id, quote_id)
);
-- Auto-order: the sandbox outbox record once the PO is emailed to the source.
ALTER TABLE agent_rig.supplier_purchase_orders ADD COLUMN IF NOT EXISTS sent jsonb;
ALTER TABLE agent_rig.supplier_purchase_orders ADD COLUMN IF NOT EXISTS sent_at timestamptz;
-- Pay on Accept reconciler: when it last claimed (tried) this quote. Each pass
-- lists the least recently tried first, so quotes that fail every run rotate
-- to the back instead of blocking newer ones.
ALTER TABLE agent_rig.quotes ADD COLUMN IF NOT EXISTS locate_attempt_at timestamptz;

-- BEGIN GENERATED AGENT MEMORY (hermes/record_schema.py)
CREATE TABLE IF NOT EXISTS agent_rig.memory_records (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    agent text NOT NULL DEFAULT 'rig' CHECK (agent = 'rig'),
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
CREATE INDEX IF NOT EXISTS memory_records_scope ON agent_rig.memory_records (tenant_id, tier, created_at, id);
CREATE INDEX IF NOT EXISTS memory_records_encoder ON agent_rig.memory_records (tenant_id, embed_model);
CREATE TABLE IF NOT EXISTS agent_rig.memory_index_jobs (
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
CREATE INDEX IF NOT EXISTS memory_index_jobs_due ON agent_rig.memory_index_jobs (run_at);
CREATE TABLE IF NOT EXISTS agent_rig.memory_publish_policy (
    tenant_id uuid PRIMARY KEY,
    enabled boolean NOT NULL DEFAULT false,
    identifiers jsonb NOT NULL DEFAULT '{}',
    updated_by text NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS agent_rig.memory_publish_log (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    actor text NOT NULL,
    happened_at timestamptz NOT NULL DEFAULT now(),
    source_row uuid NOT NULL,
    result text NOT NULL CHECK (result IN ('disabled','missing','refused','published','already_published')),
    published_row uuid
);
-- END GENERATED AGENT MEMORY
