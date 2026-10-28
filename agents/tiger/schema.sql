-- G5. Applied by watch.ensure_tables in the validated Tiger room schema.
-- Additive and idempotent; no production migration is run by the builder.
ALTER TABLE watchlist ADD COLUMN IF NOT EXISTS alert_new_product boolean NOT NULL DEFAULT true;
ALTER TABLE watchlist ADD COLUMN IF NOT EXISTS alert_below_cost boolean NOT NULL DEFAULT true;
ALTER TABLE watchlist ADD COLUMN IF NOT EXISTS alert_market_gap boolean NOT NULL DEFAULT true;

-- Baselines and condition transitions commit with the ordinary alert/mail rows.
CREATE TABLE IF NOT EXISTS alert_state (
    tenant_id uuid NOT NULL,
    key text NOT NULL,
    data jsonb NOT NULL,
    PRIMARY KEY (tenant_id, key)
);
