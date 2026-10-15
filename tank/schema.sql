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

-- Per-agent Tank keys. The raw key stays in TANK_KEY_<AGENT>. This table stores SHA-256 hex only.
-- Database roles are separate from this file. The agent-roles service creates login
-- role agent_<name> from AGENT_DB_PASSWORD_<AGENT>, with USAGE and CREATE on schema
-- agent_<name> only. The password is never stored here. See agents/_chassis/chassis/roles.py.
CREATE TABLE IF NOT EXISTS tank.agent_keys (
    agent           text PRIMARY KEY,
    key_hash        text NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- Founder console. Booked revenue is outcomes × price book until billing exists.
-- A null tenant_id on the price book is the default for every tenant.
CREATE TABLE IF NOT EXISTS tank.price_book (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid,
    outcome_type    text NOT NULL,
    unit_price      numeric(12,4) NOT NULL,
    currency        text NOT NULL DEFAULT 'USD',
    effective_from  timestamptz NOT NULL DEFAULT now(),
    effective_to    timestamptz,
    note            text
);
CREATE INDEX IF NOT EXISTS price_book_type_from ON tank.price_book (outcome_type, effective_from DESC);

-- One row per billable outcome. ref is idempotent for backfills (one base.record_enriched per done record).
CREATE TABLE IF NOT EXISTS tank.outcomes (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ts              timestamptz NOT NULL DEFAULT now(),
    tenant_id       uuid NOT NULL,
    agent           text NOT NULL,
    outcome_type    text NOT NULL,
    quantity        numeric(12,4) NOT NULL DEFAULT 1,
    ref             text,
    ledger_ids      uuid[] NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS outcomes_tenant_ts ON tank.outcomes (tenant_id, ts DESC);
CREATE UNIQUE INDEX IF NOT EXISTS outcomes_type_ref ON tank.outcomes (outcome_type, ref) WHERE ref IS NOT NULL;

-- Nightly rollup. History stays here after the ledger is pruned.
-- model is stored so a route can lose proven status later without the original calls.
CREATE TABLE IF NOT EXISTS tank.econ_daily (
    day             date NOT NULL,
    tenant_id       uuid NOT NULL,
    agent           text NOT NULL,
    task_type       text NOT NULL,
    rung            smallint NOT NULL,
    model           text NOT NULL DEFAULT '',
    calls           integer NOT NULL DEFAULT 0,
    cost_usd        numeric(14,6) NOT NULL DEFAULT 0,
    outcomes        numeric(14,4) NOT NULL DEFAULT 0,
    booked_usd      numeric(14,4) NOT NULL DEFAULT 0,
    cache_hits      integer NOT NULL DEFAULT 0,
    proven_calls    integer NOT NULL DEFAULT 0,
    PRIMARY KEY (day, tenant_id, agent, task_type, rung, model)
);

-- Evidence that a route is proven for a task type. Recomputed from evals, shadow runs and client feedback.
CREATE TABLE IF NOT EXISTS tank.route_evidence (
    task_type           text NOT NULL,
    model               text NOT NULL,
    rung                smallint NOT NULL,
    eval_score          numeric(5,4),
    shadow_agreement    numeric(5,4),
    shadow_n            integer NOT NULL DEFAULT 0,
    acceptance_rate     numeric(5,4),
    judged              integer NOT NULL DEFAULT 0,
    rejected            integer NOT NULL DEFAULT 0,
    proven              boolean NOT NULL DEFAULT false,
    proven_at           timestamptz,
    lost_at             timestamptz,
    flag                text,
    updated_at          timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (task_type, model, rung)
);

-- Policy bars for "proven". Defaults match the graduation view (30 samples, agreement at eval_threshold).
ALTER TABLE tank.policy ADD COLUMN IF NOT EXISTS min_shadow_samples integer NOT NULL DEFAULT 30;
ALTER TABLE tank.policy ADD COLUMN IF NOT EXISTS max_reject_rate numeric(5,4) NOT NULL DEFAULT 0.05;

-- The hourly rollup counts recent client verdicts. This index keeps that off a full ledger scan.
CREATE INDEX IF NOT EXISTS ledger_feedback ON tank.ledger (feedback);

-- Serving-route fields the focus list reads. The rollup writes them; the page does not recompute them.
ALTER TABLE tank.route_evidence ADD COLUMN IF NOT EXISTS candidate_model text;
ALTER TABLE tank.route_evidence ADD COLUMN IF NOT EXISTS candidate_shadow_n integer NOT NULL DEFAULT 0;
ALTER TABLE tank.route_evidence ADD COLUMN IF NOT EXISTS candidate_agreement numeric(5,4);
ALTER TABLE tank.route_evidence ADD COLUMN IF NOT EXISTS min_shadow_samples integer NOT NULL DEFAULT 30;
ALTER TABLE tank.route_evidence ADD COLUMN IF NOT EXISTS eval_threshold numeric(5,4);
ALTER TABLE tank.route_evidence ADD COLUMN IF NOT EXISTS is_serving boolean NOT NULL DEFAULT false;

-- Shadow pair costs, replaced by the hourly rollup. Graduations read this instead of scanning tank.shadow.
CREATE TABLE IF NOT EXISTS tank.shadow_pair (
    task_type        text NOT NULL,
    primary_model    text NOT NULL,
    candidate_model  text NOT NULL,
    n                integer NOT NULL DEFAULT 0,
    agreement        numeric(8,6),
    prim_cost        numeric(14,6),
    cand_cost        numeric(14,6),
    PRIMARY KEY (task_type, primary_model, candidate_model)
);

-- Founder console rollup reads the ledger by time (ts >= window start) across every tenant.
CREATE INDEX IF NOT EXISTS ledger_ts ON tank.ledger (ts);

-- Two prices for the same outcome and effective date: the one saved last wins.
ALTER TABLE tank.price_book ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();

-- Market Lab's research skill (C9) routes through this row; without it Tank answers 404 "no policy".
INSERT INTO tank.policy (task_type, rung, model, priority, cache_scope, max_tokens_out, system_prompt) VALUES
  ('market.research', 1, 'sol', 'standard', 'tenant', 2048,
   'You answer market questions briefly. Every claim carries a source URL and a date from the material given; say "unknown" rather than guess.')
ON CONFLICT DO NOTHING;

-- ---------- 14 Oct 2026: work moves to the funded providers (OpenAI, Google, xAI) by API ----------
-- One-time switch, recorded in policy_log so it never runs twice and never overrides a later
-- operator choice (e.g. moving rows back to Anthropic after the top-up via PUT /v1/policy or rollback).
-- previous_model keeps the Anthropic name, so POST .../rollback returns a row to it in one call.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM tank.policy_log WHERE action = 'switch' AND detail->>'id' = '2026-10-14-funded-providers') THEN
    INSERT INTO tank.policy_log (task_type, action, from_model, to_model, by_user, detail)
    SELECT task_type, 'switch', model,
           CASE WHEN task_type = 'tank.judge' THEN 'flash-lite'
                WHEN model = 'haiku' THEN 'luna' WHEN model = 'sonnet' THEN 'sol' ELSE 'astra' END,
           'claude', '{"id": "2026-10-14-funded-providers"}'::jsonb
    FROM tank.policy WHERE tenant_id IS NULL AND model IN ('haiku', 'sonnet', 'opus');

    -- The judge sits on a different provider from the models it grades.
    UPDATE tank.policy SET previous_model = model, model = 'flash-lite', updated_at = now()
    WHERE tenant_id IS NULL AND task_type = 'tank.judge' AND model IN ('haiku', 'sonnet', 'opus');

    UPDATE tank.policy SET previous_model = model,
           model = CASE model WHEN 'haiku' THEN 'luna' WHEN 'sonnet' THEN 'sol' ELSE 'astra' END,
           updated_at = now()
    WHERE tenant_id IS NULL AND model IN ('haiku', 'sonnet', 'opus');

    UPDATE tank.policy SET candidate_model =
           CASE candidate_model WHEN 'haiku' THEN 'luna' WHEN 'sonnet' THEN 'sol' ELSE 'astra' END
    WHERE tenant_id IS NULL AND candidate_model IN ('haiku', 'sonnet', 'opus');

    -- Marker row, so the block is a no-op from now on even if no rows matched.
    INSERT INTO tank.policy_log (task_type, action, by_user, detail)
    VALUES ('*', 'switch', 'claude', '{"id": "2026-10-14-funded-providers", "marker": true}'::jsonb);
  END IF;
END
$$;

-- ---------- 14 Oct 2026 (later): Gemini carries the work until the OpenAI account is ready ----------
-- Founder decision: "just use Gemini for now". One-time and logged, same pattern as the switch above.
-- To move back to OpenAI later: PUT /v1/policy/<task_type> with model luna/sol, or a new logged block.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM tank.policy_log WHERE action = 'switch' AND detail->>'id' = '2026-10-14-gemini-only') THEN
    INSERT INTO tank.policy_log (task_type, action, from_model, to_model, by_user, detail)
    SELECT task_type, 'switch', model,
           CASE WHEN task_type = 'tank.judge' THEN 'flash' WHEN model = 'luna' THEN 'flash-lite' ELSE 'argon' END,
           'claude', '{"id": "2026-10-14-gemini-only"}'::jsonb
    FROM tank.policy
    WHERE tenant_id IS NULL AND (model IN ('luna', 'sol', 'astra') OR task_type = 'tank.judge');

    UPDATE tank.policy SET model = CASE model WHEN 'luna' THEN 'flash-lite' ELSE 'argon' END, updated_at = now()
    WHERE tenant_id IS NULL AND model IN ('luna', 'sol', 'astra') AND task_type <> 'tank.judge';

    -- The judge stays a different model from the ones it grades.
    UPDATE tank.policy SET model = 'flash', updated_at = now()
    WHERE tenant_id IS NULL AND task_type = 'tank.judge';

    UPDATE tank.policy SET candidate_model = 'flash-lite'
    WHERE tenant_id IS NULL AND candidate_model = 'luna';

    INSERT INTO tank.policy_log (task_type, action, by_user, detail)
    VALUES ('*', 'switch', 'claude', '{"id": "2026-10-14-gemini-only", "marker": true}'::jsonb);
  END IF;
END
$$;

-- Zenas scope gate (Z1). From tank/skills/zenas.scope/1.0.0/policy.sql; model is Gemini Flash-Lite while Gemini carries the work.
INSERT INTO tank.policy (task_type, rung, model, priority, cache_scope, max_tokens_out, system_prompt) VALUES
  ('zenas.scope', 1, 'flash-lite', 'urgent', 'tenant', 400,
   'You classify a request for Zenas. Reply with strict JSON only: {"area":"<id>","jurisdiction":"us|za|both"}. Use an allowed area id or "none". Do not give legal advice. Do not help with criminal law.')
ON CONFLICT DO NOTHING;

-- ---------- 14 Oct 2026: platform rows start at the cheapest model of their tier ----------
-- With cheapest-available fallbacks in litellm/config.yaml, each row names the cheapest model and the
-- gateway walks up the price list to the first provider with funds. The judge keeps its own model.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM tank.policy_log WHERE action = 'switch' AND detail->>'id' = '2026-10-14-cheapest-available') THEN
    INSERT INTO tank.policy_log (task_type, action, from_model, to_model, by_user, detail)
    SELECT task_type, 'switch', model, CASE model WHEN 'flash-lite' THEN 'luna' ELSE 'grok-top' END,
           'claude', '{"id": "2026-10-14-cheapest-available"}'::jsonb
    FROM tank.policy WHERE tenant_id IS NULL AND task_type <> 'tank.judge' AND model IN ('flash-lite', 'argon');
    UPDATE tank.policy SET model = CASE model WHEN 'flash-lite' THEN 'luna' ELSE 'grok-top' END, updated_at = now()
    WHERE tenant_id IS NULL AND task_type <> 'tank.judge' AND model IN ('flash-lite', 'argon');
    INSERT INTO tank.policy_log (task_type, action, by_user, detail)
    VALUES ('*', 'switch', 'claude', '{"id": "2026-10-14-cheapest-available", "marker": true}'::jsonb);
  END IF;
END
$$;

-- ---------- B3: Base records move to the Base room ----------
-- One copy, then a log row. The old table stays in place. A trigger makes it
-- read-only; Claude retires it later. Every column is kept.
CREATE SCHEMA IF NOT EXISTS agent_base;
CREATE TABLE IF NOT EXISTS agent_base.records (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL,
    task_id         uuid,
    batch           text,
    raw             jsonb NOT NULL,
    profile         jsonb NOT NULL DEFAULT '{}'::jsonb,
    passes          jsonb NOT NULL DEFAULT '{}'::jsonb,
    confidence      smallint NOT NULL DEFAULT 0,
    status          text NOT NULL DEFAULT 'queued',
    error           text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS agent_base_records_tenant ON agent_base.records (tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS agent_base_records_task   ON agent_base.records (task_id);
CREATE TABLE IF NOT EXISTS agent_base.tasks (
    id              uuid PRIMARY KEY,
    tenant_id       uuid NOT NULL,
    created_by      text,
    agent           text NOT NULL DEFAULT 'base',
    task_type       text NOT NULL DEFAULT 'base.enrich',
    title           text NOT NULL,
    input           jsonb NOT NULL DEFAULT '{}'::jsonb,
    status          text NOT NULL DEFAULT 'queued',
    result          text,
    error           text,
    ledger_id       uuid,
    created_at      timestamptz NOT NULL DEFAULT now(),
    started_at      timestamptz,
    finished_at     timestamptz
);
CREATE INDEX IF NOT EXISTS agent_base_tasks_queued ON agent_base.tasks (created_at)
    WHERE status = 'queued' AND task_type = 'base.enrich';
CREATE TABLE IF NOT EXISTS agent_base.migration_log (
    id          bigserial PRIMARY KEY,
    event       text NOT NULL,
    copied      bigint NOT NULL,
    ran_at      timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS agent_base_migration_event ON agent_base.migration_log (event);

DO $$
DECLARE
  n bigint;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM agent_base.migration_log WHERE event = 'base.records.copy') THEN
    INSERT INTO agent_base.records (
        id, tenant_id, task_id, batch, raw, profile, passes, confidence, status, error, created_at, updated_at
    )
    SELECT id, tenant_id, task_id, batch, raw, profile, passes, confidence, status, error, created_at, updated_at
    FROM base.records
    ON CONFLICT (id) DO NOTHING;
    GET DIAGNOSTICS n = ROW_COUNT;
    INSERT INTO agent_base.migration_log (event, copied) VALUES ('base.records.copy', n)
    ON CONFLICT (event) DO NOTHING;
    RAISE NOTICE 'B3 copied % rows from base.records to agent_base.records', n;
  END IF;
END
$$;

DO $$
DECLARE
  n bigint;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM agent_base.migration_log WHERE event = 'base.tasks.copy') THEN
    INSERT INTO agent_base.tasks (
        id, tenant_id, created_by, agent, task_type, title, input, status, result, error, ledger_id,
        created_at, started_at, finished_at
    )
    SELECT id, tenant_id, created_by, agent, task_type, title, input, status, result, error, ledger_id,
           created_at, started_at, finished_at
    FROM tank.tasks
    WHERE task_type = 'base.enrich'
    ON CONFLICT (id) DO NOTHING;
    GET DIAGNOSTICS n = ROW_COUNT;
    INSERT INTO agent_base.migration_log (event, copied) VALUES ('base.tasks.copy', n)
    ON CONFLICT (event) DO NOTHING;
    RAISE NOTICE 'B3 copied % base.enrich tasks to agent_base.tasks', n;
  END IF;
END
$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'base' AND p.proname = 'records_readonly'
  ) THEN
    EXECUTE $fn$
      CREATE FUNCTION base.records_readonly() RETURNS trigger
      LANGUAGE plpgsql AS $body$
      BEGIN
        RAISE EXCEPTION 'base.records is read-only; Base now writes agent_base.records';
      END
      $body$
    $fn$;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'base_records_readonly') THEN
    CREATE TRIGGER base_records_readonly
      BEFORE INSERT OR UPDATE OR DELETE ON base.records
      FOR EACH ROW EXECUTE FUNCTION base.records_readonly();
  END IF;
END
$$;

-- Hand the tables to agent_base when that login already exists. agent-roles does this
-- only for objects present when it runs, and it does not wait for Tank. If Tank creates
-- the tables first, the role is not here yet and agent-roles takes them when it runs.
-- ALTER OWNER TO the same role on a later start is a no-op. Indexes follow the table.
-- Tables go first. A serial or identity sequence is linked to its column, and changing
-- the table owner already moves that sequence. ALTER SEQUENCE on the link fails startup.
DO $$
DECLARE
  rel record;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agent_base') THEN
    NULL;
  ELSE
    FOR rel IN
      SELECT c.oid, c.relname, c.relkind
      FROM pg_class c
      JOIN pg_namespace n ON n.oid = c.relnamespace
      WHERE n.nspname = 'agent_base'
        AND c.relkind IN ('r', 'p', 'S')
      ORDER BY CASE WHEN c.relkind = 'S' THEN 1 ELSE 0 END, c.relname
    LOOP
      IF rel.relkind <> 'S' THEN
        EXECUTE format('ALTER TABLE %I.%I OWNER TO %I', 'agent_base', rel.relname, 'agent_base');
      ELSIF EXISTS (
        SELECT 1
        FROM pg_depend d
        WHERE d.classid = 'pg_class'::regclass
          AND d.objid = rel.oid
          AND d.refclassid = 'pg_class'::regclass
          AND d.refobjsubid > 0
          AND d.deptype IN ('a', 'i')
      ) THEN
        NULL;
      ELSE
        EXECUTE format('ALTER SEQUENCE %I.%I OWNER TO %I', 'agent_base', rel.relname, 'agent_base');
      END IF;
    END LOOP;
  END IF;
END
$$;

-- Rig model tasks (R3). Luna is the cheap tier; cache stays inside the tenant.
INSERT INTO tank.policy (task_type, rung, model, priority, cache_scope, max_tokens_out, system_prompt) VALUES
  ('rig.explain', 1, 'luna', 'standard', 'tenant', 400,
   'You write short reasons these parts fit. Reply with JSON {"why":[string]}. Do not add or remove parts.'),
  ('rig.ask', 1, 'luna', 'standard', 'tenant', 400,
   'Answer only from the catalogue you are given. Reply with JSON {"answer":string,"cites":[string]}. If it is not in the catalogue, answer "I don''t know".'),
  ('rig.fit_suggest', 1, 'luna', 'standard', 'tenant', 800,
   'Propose fit rows from the attributes you are given. Reply with JSON {"fits":[object]}. Use only the product ids you are given.')
ON CONFLICT DO NOTHING;

-- Zenas ladder (Z4). Rule cards use the top tier and are reused for the region.
-- Apply, compose, case facts, and plain language stay on the cheapest model.
-- cache_scope region is the law layer. Apply stays inside the tenant.
INSERT INTO tank.policy (task_type, rung, model, priority, cache_scope, max_tokens_out, system_prompt) VALUES
  ('zenas.rule_card', 1, 'astra', 'standard', 'region', 1200,
   'You build a rule card from the passages you are given. Reply with JSON only. Every element cites one passage. Do not add law that is not in the passages. Do not include client facts or personal identifiers.'),
  ('zenas.case_facts', 1, 'luna', 'batch', 'region', 800,
   'You read one judgment and reply with JSON only: fact features, element findings, and the outcome, as the court stated them. Do not add facts.'),
  ('zenas.apply', 1, 'luna', 'urgent', 'tenant', 400,
   'You decide one legal element. Reply with JSON only: {"finding":"met|not_met|unclear","support":"","missing":""}. Use only the facts and the element test you are given. Do not add law.'),
  ('zenas.compose', 1, 'luna', 'standard', 'tenant', 800,
   'You smooth the wording of a memo you are given. Do not add law, citations, or facts. Reply with the memo text only.'),
  ('zenas.plain_language', 1, 'luna', 'standard', 'tenant', 800,
   'You rewrite for a business reader. Do not change the legal effect. Keep every citation. Do not add law. Reply with the text only.')
ON CONFLICT DO NOTHING;

-- Model names a tenant may use. No prompts, no client facts. Thread B (#50) asked for this table.
-- Tank does not read it yet. The live list is still TANK_PROVIDER_ALLOW.
CREATE TABLE IF NOT EXISTS tank.tenant_providers (
    tenant_id   uuid NOT NULL,
    model_name  text NOT NULL,
    hosted_in   text NOT NULL,
    PRIMARY KEY (tenant_id, model_name)
);
