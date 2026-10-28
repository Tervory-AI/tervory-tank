CREATE TABLE IF NOT EXISTS agent_trigger.voices (
    tenant_id uuid PRIMARY KEY,
    voice jsonb NOT NULL CHECK (jsonb_typeof(voice)='object' AND voice->>'status'='live'),
    revision integer NOT NULL CHECK (revision > 0),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- Immutable revisions; the current pointer remains compatible with the first build.
CREATE TABLE IF NOT EXISTS agent_trigger.voice_versions (
    tenant_id uuid NOT NULL,
    revision integer NOT NULL CHECK (revision > 0),
    voice jsonb NOT NULL,
    source_text text NOT NULL DEFAULT '',
    operation_id uuid,
    restored_from integer,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, revision),
    UNIQUE (tenant_id, operation_id)
);
INSERT INTO agent_trigger.voice_versions(tenant_id,revision,voice)
SELECT tenant_id,revision,voice FROM agent_trigger.voices ON CONFLICT DO NOTHING;
