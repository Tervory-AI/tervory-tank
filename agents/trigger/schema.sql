CREATE TABLE IF NOT EXISTS agent_trigger.voices (
    tenant_id uuid PRIMARY KEY,
    voice jsonb NOT NULL CHECK (jsonb_typeof(voice)='object' AND voice->>'status'='live'),
    revision integer NOT NULL CHECK (revision > 0),
    updated_at timestamptz NOT NULL DEFAULT now()
);
