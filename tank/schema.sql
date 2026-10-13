-- Tank schema. Applied by Tank on every start; every statement is idempotent.
-- Build Pack v2, "Tank — the centrepiece": ledger, policy, evals, tasks.

CREATE SCHEMA IF NOT EXISTS tank;

-- One row per model call. Never updated after insert except outcome/feedback.
CREATE TABLE IF NOT EXISTS tank.ledger (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ts              timestamptz NOT NULL DEFAULT now(),
    tenant_id       uuid NOT NULL,
    region          text NOT NULL DEFAULT 'us-east',
    agent           text NOT NULL,            -- tier0 | base | tiger | market_lab | radix | tisan | zenas | orchestrator
    skill           text,                     -- Skala skill id@version, null for Tier 0
    task_type       text NOT NULL,            -- policy key, e.g. tier0.answer
    rung            smallint NOT NULL DEFAULT 1,  -- 1 frontier, 2 owned model, 3 code, 4 cache
    model           text NOT NULL,            -- LiteLLM model_name actually used
    priority        text NOT NULL DEFAULT 'standard',  -- urgent | standard | batch
    tokens_in       integer NOT NULL DEFAULT 0,
    tokens_out      integer NOT NULL DEFAULT 0,
    cost_usd        numeric(12,6) NOT NULL DEFAULT 0,
    latency_ms      integer,
    cache_hit       boolean NOT NULL DEFAULT false,
    eval_score      numeric(5,4),             -- null unless sampled by the eval harness
    outcome         text NOT NULL DEFAULT 'delivered'  -- delivered | failed | unverified
);
CREATE INDEX IF NOT EXISTS ledger_tenant_ts ON tank.ledger (tenant_id, ts DESC);
CREATE INDEX IF NOT EXISTS ledger_task_ts   ON tank.ledger (task_type, ts DESC);

-- Human verdict on a delivered answer. This column is what outcome-based billing,
-- the eval harness and the graduation loop all read. Null = nobody has said yet.
ALTER TABLE tank.ledger ADD COLUMN IF NOT EXISTS feedback      text;         -- accepted | rejected
ALTER TABLE tank.ledger ADD COLUMN IF NOT EXISTS feedback_note text;
ALTER TABLE tank.ledger ADD COLUMN IF NOT EXISTS feedback_at   timestamptz;
ALTER TABLE tank.ledger ADD COLUMN IF NOT EXISTS feedback_by   text;         -- user id of who said so
ALTER TABLE tank.ledger ADD COLUMN IF NOT EXISTS task_id       uuid;         -- set when the call ran a task
ALTER TABLE tank.ledger ADD COLUMN IF NOT EXISTS error         text;         -- why a failed call failed: upstream status and a short message

-- Routing policy. Data, not code: change a row, not a deploy.
CREATE TABLE IF NOT EXISTS tank.policy (
    task_type       text NOT NULL,
    tenant_id       uuid,                     -- null = default for every tenant
    rung            smallint NOT NULL DEFAULT 1,
    model           text NOT NULL,            -- LiteLLM model_name
    priority        text NOT NULL DEFAULT 'standard',
    batch_eligible  boolean NOT NULL DEFAULT false,
    cache_scope     text NOT NULL DEFAULT 'none',   -- none | tenant | platform
    max_tokens_out  integer NOT NULL DEFAULT 1024,
    system_prompt   text,
    eval_threshold  numeric(5,4) NOT NULL DEFAULT 0.97,
    updated_at      timestamptz NOT NULL DEFAULT now()
);
-- Graduation: a cheaper candidate runs in the shadow of the current model on a share of calls.
ALTER TABLE tank.policy ADD COLUMN IF NOT EXISTS candidate_model text;
ALTER TABLE tank.policy ADD COLUMN IF NOT EXISTS shadow_rate numeric(4,3) NOT NULL DEFAULT 0;   -- 0..1 of calls shadowed
ALTER TABLE tank.policy ADD COLUMN IF NOT EXISTS previous_model text;

-- One shadow comparison per sampled call. agreement 0..1: how close the candidate came to the primary.
CREATE TABLE IF NOT EXISTS tank.shadow (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ledger_id       uuid NOT NULL,            -- the primary call
    tenant_id       uuid NOT NULL,
    task_type       text NOT NULL,
    primary_model   text NOT NULL,
    candidate_model text NOT NULL,
    primary_content text NOT NULL,
    candidate_content text,
    candidate_cost_usd numeric(12,6) NOT NULL DEFAULT 0,
    primary_cost_usd   numeric(12,6) NOT NULL DEFAULT 0,
    agreement       numeric(5,4),             -- null until judged
    method          text,                     -- json | judge | failed
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS shadow_task ON tank.shadow (task_type, created_at DESC);

-- Promotions and demotions, so the ladder has a history.
CREATE TABLE IF NOT EXISTS tank.policy_log (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    task_type       text NOT NULL,
    action          text NOT NULL,            -- promote | candidate | rollback
    from_model      text,
    to_model        text,
    by_user         text,
    detail          jsonb,
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- One policy row per task type per tenant; a null tenant is the platform default.
CREATE UNIQUE INDEX IF NOT EXISTS policy_task_tenant
    ON tank.policy (task_type, COALESCE(tenant_id, '00000000-0000-0000-0000-000000000000'::uuid));

-- What was asked and what came back, one row per model call. This is the learning corpus:
-- feedback turns rows here into golden cases; the graduation loop replays them against candidates.
CREATE TABLE IF NOT EXISTS tank.transcripts (
    ledger_id       uuid PRIMARY KEY,
    tenant_id       uuid NOT NULL,
    task_type       text NOT NULL,
    messages        jsonb NOT NULL,           -- as sent (system prompt excluded; it lives in policy)
    content         text NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS transcripts_task ON tank.transcripts (task_type, created_at DESC);

-- Golden cases per task type for the eval harness (build order step 5).
CREATE TABLE IF NOT EXISTS tank.evals (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    task_type       text NOT NULL,
    input           jsonb NOT NULL,
    expected        jsonb NOT NULL,
    tolerance       text NOT NULL DEFAULT 'exact',  -- exact | contains | semantic
    source          text NOT NULL DEFAULT 'manual', -- manual | tester_feedback
    created_at      timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE tank.evals ADD COLUMN IF NOT EXISTS tenant_id uuid;          -- who the case came from (null = platform)
ALTER TABLE tank.evals ADD COLUMN IF NOT EXISTS ledger_id uuid;          -- the call it was made from
ALTER TABLE tank.evals ADD COLUMN IF NOT EXISTS verdict text NOT NULL DEFAULT 'accepted';  -- accepted | rejected
ALTER TABLE tank.evals ADD COLUMN IF NOT EXISTS note text;
CREATE UNIQUE INDEX IF NOT EXISTS evals_ledger ON tank.evals (ledger_id) WHERE ledger_id IS NOT NULL;

-- A unit of work a person asked for. The board in the Workspace is a view of this table.
-- Today a task is one model call; later a task fans out to an agent run of many calls,
-- all stamped with this task_id in the ledger.
CREATE TABLE IF NOT EXISTS tank.tasks (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL,
    created_by      text,                     -- user id of who asked
    agent           text NOT NULL DEFAULT 'tier0',
    task_type       text NOT NULL DEFAULT 'tier0.answer',
    title           text NOT NULL,
    input           jsonb NOT NULL,           -- the messages as submitted
    status          text NOT NULL DEFAULT 'queued',   -- queued | running | done | failed
    result          text,
    error           text,
    ledger_id       uuid,                     -- the call that produced the result
    created_at      timestamptz NOT NULL DEFAULT now(),
    started_at      timestamptz,
    finished_at     timestamptz
);
CREATE INDEX IF NOT EXISTS tasks_tenant_created ON tank.tasks (tenant_id, created_at DESC);

-- Tier 0 defaults. Haiku for everything that is not a judgment call.
INSERT INTO tank.policy (task_type, rung, model, priority, cache_scope, max_tokens_out, system_prompt) VALUES
  ('tier0.answer',   1, 'haiku',  'urgent',   'platform', 1024,
   'You are Tervory, an assistant for entrepreneurs. Answer plainly and briefly. If the request needs research, data work, price monitoring, security checks, a build, or legal documents, say which of those it is rather than attempting it.'),
  ('tier0.draft',    1, 'haiku',  'urgent',   'none',     2048,
   'You draft short business writing (emails, messages, summaries) in plain, direct English. No preamble.'),
  ('route.request',  1, 'haiku',  'urgent',   'none',     64,
   'Classify the request into exactly one of: tier0, base, tiger, market_lab, radix, tisan, zenas. Reply with the label only.'),
  ('reason.brief',   1, 'sonnet', 'standard', 'none',     4096,
   'You write concise, well-structured analysis for a business owner. Lead with the conclusion.')
ON CONFLICT DO NOTHING;

-- The judge: scores whether two answers say the same thing. Platform-only, never billed to a client.
INSERT INTO tank.policy (task_type, rung, model, priority, cache_scope, max_tokens_out, system_prompt) VALUES
  ('tank.judge', 1, 'haiku', 'batch', 'none', 64,
   'You compare two answers to the same request. Reply with one integer 0-100: how closely the second answer matches the first in conclusion and key facts. 100 = same conclusion and facts; 0 = contradicts or misses the point. Reply with the number only.')
ON CONFLICT DO NOTHING;

-- First graduation candidate: reason.brief from Sonnet to Haiku, every call shadowed until promoted.
UPDATE tank.policy SET candidate_model = 'haiku', shadow_rate = 1.0
WHERE task_type = 'reason.brief' AND tenant_id IS NULL AND model = 'sonnet' AND candidate_model IS NULL;

-- ---------- Skala: the skills registry (Phase 1 = this table + the skills/ folder in Git) ----------
CREATE TABLE IF NOT EXISTS tank.skills (
    id              text NOT NULL,
    version         text NOT NULL,
    agent           text NOT NULL,
    rung            smallint NOT NULL DEFAULT 1,
    task_type       text,                     -- policy row the skill routes through (model skills only)
    description     text NOT NULL DEFAULT '',
    state           text NOT NULL DEFAULT 'candidate',  -- candidate | staging | approved | retired
    eval_threshold  numeric(5,4) NOT NULL DEFAULT 0.95,
    cases           integer NOT NULL DEFAULT 0,
    last_eval_score numeric(5,4),
    last_eval_at    timestamptz,
    models_validated jsonb NOT NULL DEFAULT '[]'::jsonb,
    approved_by     text,
    approved_at     timestamptz,
    present         boolean NOT NULL DEFAULT true,   -- false when the package has gone from disk
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (id, version)
);

CREATE TABLE IF NOT EXISTS tank.skill_evals (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_id        text NOT NULL,
    version         text NOT NULL,
    score           numeric(5,4) NOT NULL,
    passed          integer NOT NULL,
    total           integer NOT NULL,
    cost_usd        numeric(12,6) NOT NULL DEFAULT 0,
    details         jsonb NOT NULL,
    ran_by          text,
    ran_at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS skill_evals_skill ON tank.skill_evals (skill_id, version, ran_at DESC);

-- ---------- Base: enriched records ----------
CREATE SCHEMA IF NOT EXISTS base;
CREATE TABLE IF NOT EXISTS base.records (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL,
    task_id         uuid,                     -- the Tank task that ran the batch
    batch           text,                     -- a label the client gave the upload
    raw             jsonb NOT NULL,           -- the input record as received
    profile         jsonb NOT NULL DEFAULT '{}'::jsonb,  -- field -> {value, source, confidence}
    passes          jsonb NOT NULL DEFAULT '{}'::jsonb,  -- pass -> {skill, ms, note}
    confidence      smallint NOT NULL DEFAULT 0,         -- 0-100 overall (pass 7 owns this later)
    status          text NOT NULL DEFAULT 'queued',      -- queued | running | done | failed
    error           text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS base_records_tenant ON base.records (tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS base_records_task   ON base.records (task_id);

-- Policy rows for the model steps in Base (pass 2c extract, pass 5 business data).
INSERT INTO tank.policy (task_type, rung, model, priority, cache_scope, max_tokens_out, system_prompt) VALUES
  ('base.extract', 1, 'haiku', 'batch', 'tenant', 600,
   'You extract structured facts from website text and reply with strict JSON only.'),
  ('base.business_data', 1, 'haiku', 'batch', 'tenant', 600,
   'You estimate the size and shape of a small business from sparse signals, conservatively, and reply with strict JSON only.')
ON CONFLICT (task_type, COALESCE(tenant_id, '00000000-0000-0000-0000-000000000000'::uuid))
DO UPDATE SET max_tokens_out = GREATEST(tank.policy.max_tokens_out, EXCLUDED.max_tokens_out);
-- (the cap only ever goes up from the repo; an operator's higher setting is kept)
