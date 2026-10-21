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
    messages        jsonb NOT NULL,           -- as sent; agent chat includes its policy system prompt
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

-- Zenas scope gate (Z1). Model is Gemini Flash-Lite while Gemini carries the work.
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

-- T6: graduate a task onto a code skill, and prove a semantic cache the same way.
-- field breakdown from a shadow comparison (method = 'fields'). Empty object until scored.
ALTER TABLE tank.shadow ADD COLUMN IF NOT EXISTS fields jsonb NOT NULL DEFAULT '{}'::jsonb;
-- Promote by itself once the bar is cleared. The founder can turn this off per task.
ALTER TABLE tank.policy ADD COLUMN IF NOT EXISTS auto_promote boolean NOT NULL DEFAULT true;
-- Per-field floors. Missing keys use the task's eval_threshold.
ALTER TABLE tank.policy ADD COLUMN IF NOT EXISTS field_floors jsonb NOT NULL DEFAULT '{}'::jsonb;
-- Rung 4 semantic cache, off until the shadow loop proves it.
ALTER TABLE tank.policy ADD COLUMN IF NOT EXISTS semantic_cache boolean NOT NULL DEFAULT false;
-- When the current model was promoted. Rollback watches the next 7 days.
ALTER TABLE tank.policy ADD COLUMN IF NOT EXISTS promoted_at timestamptz;
-- Numbers in a field comparison match inside this relative tolerance.
ALTER TABLE tank.policy ADD COLUMN IF NOT EXISTS number_tolerance numeric(8,6) NOT NULL DEFAULT 0.01;

-- Ranked search: cheapest candidate first, for one task type.
CREATE TABLE IF NOT EXISTS tank.graduation_rank (
    task_type           text NOT NULL,
    candidate           text NOT NULL,
    kind                text NOT NULL DEFAULT 'model',
    price_usd           numeric(14,8) NOT NULL DEFAULT 0,
    screen_agreement    numeric(8,6),
    shadow_n            integer NOT NULL DEFAULT 0,
    shadow_agreement    numeric(8,6),
    cost_per_call       numeric(14,6),
    monthly_saving_usd  numeric(14,4),
    status              text NOT NULL DEFAULT 'unscreened',
    updated_at          timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (task_type, candidate)
);

-- Paid shadow and search spend for the daily cap. Code skills add nothing.
CREATE TABLE IF NOT EXISTS tank.shadow_spend (
    task_type   text NOT NULL,
    day         date NOT NULL,
    spent_usd   numeric(14,6) NOT NULL DEFAULT 0,
    PRIMARY KEY (task_type, day)
);

-- When this task was last searched, and why. A roster or price change starts another search.
CREATE TABLE IF NOT EXISTS tank.search_state (
    task_type            text PRIMARY KEY,
    roster_fingerprint   text,
    price_fingerprint    text,
    searched_at          timestamptz,
    reason               text,
    proposed             text
);

-- Zenas ladder (Z4). Rule cards use luna, the same model as the other late Zenas rows.
-- Apply, compose, case facts, and plain language stay on the cheapest model.
-- cache_scope region is the law layer. Apply stays inside the tenant.
INSERT INTO tank.policy (task_type, rung, model, priority, cache_scope, max_tokens_out, system_prompt) VALUES
  ('zenas.rule_card', 1, 'luna', 'standard', 'region', 1200,
   'You build a rule card from the passages you are given. Reply with JSON only. Every element cites one passage. Do not add law that is not in the passages. Do not include client facts or personal identifiers.'),
  ('zenas.case_facts', 1, 'luna', 'batch', 'region', 800,
   'You read one judgment and reply with JSON only: fact features, element findings, and the outcome, as the court stated them. Do not add facts.'),
  ('zenas.apply', 1, 'luna', 'urgent', 'tenant', 400,
   'You decide one legal element. Reply with JSON only: {"finding":"met|not_met|unclear","support":"","missing":""}. Use only the facts and the element test you are given. Do not add law.'),
  ('zenas.compose', 1, 'luna', 'standard', 'tenant', 800,
   'You smooth the wording of a memo you are given. Do not add law, citations, or facts. Reply with the memo text only.'),
  ('zenas.plain_language', 1, 'luna', 'standard', 'tenant', 800,
   'You rewrite for a business reader. Do not change the legal effect. Keep every citation. Do not add law. Reply with the text only.'),
  ('zenas.draft', 1, 'luna', 'standard', 'tenant', 800,
   'You revise only the sentences you are given, using the facts you are given. Do not add law or citations. Reply with the sentences only.'),
  ('zenas.review', 1, 'luna', 'standard', 'tenant', 400,
   'You name the risk of one difference: low, medium, or high. Do not add law or a replacement sentence. Reply with that one word.')
ON CONFLICT DO NOTHING;

-- zenas.rule_card was seeded as astra, which has no LiteLLM fallback. The other late
-- Zenas rows use luna, and luna falls back in litellm/config.yaml. One-time, so a later
-- choice is kept. Only a row that is still astra moves.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM tank.policy_log
    WHERE action = 'switch' AND detail->>'id' = '2026-10-15-zenas-rule-card-fallback'
  ) THEN
    INSERT INTO tank.policy_log (task_type, action, from_model, to_model, by_user, detail)
    SELECT task_type, 'switch', model, 'luna', 'tank',
           '{"id": "2026-10-15-zenas-rule-card-fallback"}'::jsonb
    FROM tank.policy
    WHERE task_type = 'zenas.rule_card' AND tenant_id IS NULL AND model = 'astra';

    UPDATE tank.policy
    SET model = 'luna', updated_at = now()
    WHERE task_type = 'zenas.rule_card' AND tenant_id IS NULL AND model = 'astra';

    INSERT INTO tank.policy_log (task_type, action, by_user, detail)
    VALUES ('*', 'switch', 'tank', '{"id": "2026-10-15-zenas-rule-card-fallback", "marker": true}'::jsonb);
  END IF;
END
$$;

-- TRAIN-1. Client examples stay tenant- and region-scoped. Holdouts are stored
-- but never enter the weekly run or an exported training dataset.
CREATE TABLE IF NOT EXISTS tank.gold_examples (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    region text NOT NULL CHECK (region IN ('us-east', 'za')),
    skill_id text NOT NULL,
    agent text NOT NULL,
    input jsonb NOT NULL,
    expected jsonb NOT NULL,
    tolerance text NOT NULL DEFAULT 'exact',
    status text NOT NULL DEFAULT 'candidate' CHECK (status IN ('candidate','checked','rejected')),
    holdout boolean NOT NULL DEFAULT false,
    source text NOT NULL,
    source_ref text NOT NULL,
    input_hash text NOT NULL,
    checked_by text,
    checked_at timestamptz,
    note text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, region, skill_id, source, source_ref)
);
CREATE INDEX IF NOT EXISTS gold_review_queue ON tank.gold_examples (tenant_id, region, agent, skill_id, status);
CREATE INDEX IF NOT EXISTS gold_input_group ON tank.gold_examples (tenant_id, region, skill_id, input_hash);
CREATE TABLE IF NOT EXISTS tank.gold_scores (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    region text NOT NULL CHECK (region IN ('us-east','za')),
    skill_id text NOT NULL,
    version text NOT NULL,
    score numeric(5,4) NOT NULL CHECK (score BETWEEN 0 AND 1),
    n integer NOT NULL CHECK (n > 0),
    final_check boolean NOT NULL DEFAULT false,
    ran_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS gold_score_history ON tank.gold_scores (tenant_id, region, skill_id, final_check, ran_at DESC);
CREATE TABLE IF NOT EXISTS tank.training_pairs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    agent text NOT NULL,
    task_type text NOT NULL,
    region text NOT NULL CHECK (region IN ('us-east','za')),
    input jsonb NOT NULL,
    output jsonb NOT NULL,
    approved_by text NOT NULL,
    source text NOT NULL,
    source_ref text NOT NULL,
    gold_id uuid REFERENCES tank.gold_examples(id),
    holdout boolean NOT NULL DEFAULT false,
    active boolean NOT NULL DEFAULT true,
    client_matter boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, region, source, source_ref)
);
CREATE INDEX IF NOT EXISTS training_pairs_scope ON tank.training_pairs (tenant_id, region, agent);
CREATE TABLE IF NOT EXISTS tank.training_exports (
    region text NOT NULL,
    day date NOT NULL,
    agent text NOT NULL,
    exported_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (region, day, agent)
);

-- Zenas self-test (Z7). Batch, so it stays behind a client's question.
-- Scores are stored on the box. A cheaper route takes over only when it matches
-- on the held-out cases. This row does not change which route a question uses.
INSERT INTO tank.policy (task_type, rung, model, priority, cache_scope, max_tokens_out, system_prompt) VALUES
  ('zenas.selftest', 1, 'luna', 'batch', 'region', 400,
   'You compare a held-out case with the ladder result. Reply with JSON only. Do not add facts the court did not state.')
ON CONFLICT DO NOTHING;

-- Workspace billing webhook. One row per Stripe event id.
CREATE TABLE IF NOT EXISTS tank.billing_events (
    event_id text PRIMARY KEY,
    type text,
    received_at timestamptz,
    handled boolean DEFAULT false
);

-- GRAD-1: machine labels remain candidates until a source passes review.
ALTER TABLE tank.gold_examples ADD COLUMN IF NOT EXISTS auto_label boolean NOT NULL DEFAULT false;
ALTER TABLE tank.gold_examples ADD COLUMN IF NOT EXISTS label_source text;
ALTER TABLE tank.gold_examples ADD COLUMN IF NOT EXISTS public boolean NOT NULL DEFAULT false;
ALTER TABLE tank.gold_examples ADD COLUMN IF NOT EXISTS intake_day date;
CREATE INDEX IF NOT EXISTS gold_auto_source ON tank.gold_examples
    (tenant_id,region,agent,label_source,intake_day) WHERE auto_label;
ALTER TABLE tank.ledger ADD COLUMN IF NOT EXISTS vendor        text;
ALTER TABLE tank.ledger ADD COLUMN IF NOT EXISTS units         numeric;

ALTER TABLE tank.gold_examples ADD COLUMN IF NOT EXISTS auto_approved boolean NOT NULL DEFAULT false;
ALTER TABLE tank.gold_examples ADD COLUMN IF NOT EXISTS label_family text;

-- Explicit model holdout evidence; never substitute offline screening scores.
ALTER TABLE tank.gold_scores ADD COLUMN IF NOT EXISTS task_type text;
ALTER TABLE tank.gold_scores ADD COLUMN IF NOT EXISTS candidate_model text;
ALTER TABLE tank.gold_scores ADD COLUMN IF NOT EXISTS cost_per_call numeric(14,8);

-- Export provenance defaults to private; legacy rows require explicit review.
ALTER TABLE tank.training_pairs ADD COLUMN IF NOT EXISTS public boolean NOT NULL DEFAULT false;
CREATE TABLE IF NOT EXISTS tank.training_jobs (
    id text PRIMARY KEY,
    tenant_id uuid NOT NULL,
    region text NOT NULL,
    model_repo text NOT NULL,
    estimated_usd numeric(12,6) NOT NULL,
    actual_usd numeric(12,6),
    ledger_id uuid UNIQUE REFERENCES tank.ledger(id),
    created_at timestamptz NOT NULL DEFAULT now()
);

-- A training row keeps the batch it came from. A removed batch retires its gold
-- and marks every model trained on it.
ALTER TABLE tank.gold_examples ADD COLUMN IF NOT EXISTS batch_id text;
ALTER TABLE tank.gold_examples ADD COLUMN IF NOT EXISTS currency text;
ALTER TABLE tank.gold_examples ADD COLUMN IF NOT EXISTS unit text;
ALTER TABLE tank.gold_examples ADD COLUMN IF NOT EXISTS quarantine text;

ALTER TABLE tank.training_pairs ADD COLUMN IF NOT EXISTS batch_id text;
ALTER TABLE tank.training_pairs ADD COLUMN IF NOT EXISTS currency text;
ALTER TABLE tank.training_pairs ADD COLUMN IF NOT EXISTS unit text;

CREATE TABLE IF NOT EXISTS tank.removed_batches (
    tenant_id uuid NOT NULL,
    batch_id text NOT NULL,
    removed_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, batch_id)
);

CREATE TABLE IF NOT EXISTS tank.training_job_batches (
    tenant_id uuid NOT NULL,
    job_id text NOT NULL,
    model_repo text NOT NULL,
    batch_id text NOT NULL,
    region text NOT NULL,
    PRIMARY KEY (tenant_id, job_id, batch_id)
);

CREATE TABLE IF NOT EXISTS tank.training_snapshot_batches (
    tenant_id uuid NOT NULL,
    region text NOT NULL,
    day date NOT NULL,
    agent text NOT NULL,
    batch_id text NOT NULL,
    PRIMARY KEY (tenant_id, region, day, agent, batch_id)
);

-- CORE-1: disable existing automation once; preserve later founder choices.
ALTER TABLE tank.policy ALTER COLUMN auto_promote SET DEFAULT false;
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM tank.policy_log WHERE detail->>'id'='2026-10-21-core1-auto-off') THEN
    UPDATE tank.policy SET auto_promote=false WHERE auto_promote;
    INSERT INTO tank.policy_log(task_type,action,by_user,detail)
    VALUES('*','switch','tank','{"id":"2026-10-21-core1-auto-off","marker":true}'::jsonb);
  END IF;
END $$;

-- CORE-1 price snapshots and savings. Unknown prices stay null, never invented.
ALTER TABLE tank.policy ADD COLUMN IF NOT EXISTS baseline_model text;
ALTER TABLE tank.ledger ADD COLUMN IF NOT EXISTS baseline_model text;
ALTER TABLE tank.ledger ADD COLUMN IF NOT EXISTS baseline_cost_usd numeric(18,8);
ALTER TABLE tank.ledger ADD COLUMN IF NOT EXISTS baseline_status text NOT NULL DEFAULT 'pending';
ALTER TABLE tank.ledger ADD COLUMN IF NOT EXISTS baseline_priced_at timestamptz;
CREATE TABLE IF NOT EXISTS tank.proof_prices (
    model text PRIMARY KEY, family text NOT NULL,
    input_usd numeric(20,12) NOT NULL CHECK (input_usd>=0),
    output_usd numeric(20,12) NOT NULL CHECK (output_usd>=0),
    active boolean NOT NULL DEFAULT true, updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE OR REPLACE FUNCTION tank.price_receipt() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE chosen text; price tank.proof_prices%ROWTYPE;
BEGIN
    -- Research can retain tokens with a placeholder zero when cost is unknown.
    -- Vendor fees are actual spend only: there is no comparable token baseline.
    IF to_jsonb(NEW)->>'research_cost_status'='unknown'
       OR NEW.model LIKE 'vendor:%' OR to_jsonb(NEW)->>'vendor' IS NOT NULL THEN
      NEW.baseline_model := NULL;
      NEW.baseline_cost_usd := NULL;
      NEW.baseline_priced_at := NULL;
      NEW.baseline_status := 'unpriced';
      RETURN NEW;
    END IF;
    IF NEW.baseline_status <> 'pending' THEN RETURN NEW; END IF;
    SELECT coalesce(p.baseline_model,(SELECT b.model FROM tank.proof_prices a
      JOIN tank.proof_prices b ON b.family=a.family AND b.active WHERE a.model=p.model
      ORDER BY b.input_usd+b.output_usd DESC,b.model LIMIT 1)) INTO chosen FROM tank.policy p
      WHERE p.task_type=NEW.task_type AND (p.tenant_id=NEW.tenant_id OR p.tenant_id IS NULL)
      ORDER BY p.tenant_id NULLS LAST LIMIT 1;
    NEW.baseline_model := coalesce(chosen,NEW.model);
    SELECT * INTO price FROM tank.proof_prices WHERE model=NEW.baseline_model;
    IF FOUND THEN
      NEW.baseline_cost_usd := NEW.tokens_in*price.input_usd + NEW.tokens_out*price.output_usd;
      NEW.baseline_status := 'measured';
      NEW.baseline_priced_at := price.updated_at;
    ELSIF NEW.tokens_in=0 AND NEW.tokens_out=0 THEN
      NEW.baseline_cost_usd := 0;
      NEW.baseline_status := 'no_tokens';
    END IF;
    RETURN NEW;
END $$;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='core1_price_receipt'
                   AND tgrelid='tank.ledger'::regclass) THEN
      CREATE TRIGGER core1_price_receipt BEFORE INSERT ON tank.ledger
        FOR EACH ROW EXECUTE FUNCTION tank.price_receipt();
    END IF;
END $$;

-- Bench state is independent of the existing monthly candidate search.
ALTER TABLE tank.search_state ADD COLUMN IF NOT EXISTS bench_roster_fingerprint text;
ALTER TABLE tank.search_state ADD COLUMN IF NOT EXISTS bench_price_fingerprint text;
ALTER TABLE tank.search_state ADD COLUMN IF NOT EXISTS bench_at timestamptz;
ALTER TABLE tank.search_state ADD COLUMN IF NOT EXISTS bench_status text;
ALTER TABLE tank.search_state ADD COLUMN IF NOT EXISTS bench_error text;
ALTER TABLE tank.route_evidence ADD COLUMN IF NOT EXISTS bench_run_id uuid;
ALTER TABLE tank.route_evidence ADD COLUMN IF NOT EXISTS bench_score numeric(8,6);
ALTER TABLE tank.route_evidence ADD COLUMN IF NOT EXISTS bench_cost_per_call numeric(18,8);
ALTER TABLE tank.route_evidence ADD COLUMN IF NOT EXISTS bench_n integer NOT NULL DEFAULT 0;
ALTER TABLE tank.route_evidence ADD COLUMN IF NOT EXISTS bench_at timestamptz;
CREATE TABLE IF NOT EXISTS tank.bench_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL,
    region text NOT NULL, task_type text NOT NULL, model text NOT NULL,
    comparison_model text NOT NULL, suite_hash text NOT NULL, expected_n integer NOT NULL,
    score numeric(8,6), cost_per_call numeric(18,8),
    status text NOT NULL DEFAULT 'running', error text,
    started_at timestamptz NOT NULL DEFAULT now(), finished_at timestamptz
);
CREATE TABLE IF NOT EXISTS tank.bench_calls (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), run_id uuid NOT NULL REFERENCES tank.bench_runs(id),
    tenant_id uuid NOT NULL, region text NOT NULL, day date NOT NULL,
    case_ref text NOT NULL, case_kind text NOT NULL, ledger_id uuid REFERENCES tank.ledger(id),
    reserved_usd numeric(18,8) NOT NULL, charged_usd numeric(18,8), score numeric(8,6),
    status text NOT NULL DEFAULT 'reserved', created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS bench_budget ON tank.bench_calls (tenant_id,region,day);
CREATE INDEX IF NOT EXISTS bench_task_history ON tank.bench_runs (tenant_id,region,task_type,started_at DESC);

-- The existing hourly rollup rebuilds route_evidence from scratch. Reattach
-- benchmark receipts on insert; historical runs remain immutable in bench_runs.
CREATE OR REPLACE FUNCTION tank.restore_bench_evidence() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE recent tank.bench_runs%ROWTYPE;
BEGIN
    IF NEW.rung <> 1 THEN RETURN NEW; END IF;
    SELECT * INTO recent FROM tank.bench_runs
      WHERE tenant_id='00000000-0000-0000-0000-000000000001'::uuid
        AND task_type=NEW.task_type AND model=NEW.model AND status='complete'
      ORDER BY finished_at DESC,id DESC LIMIT 1;
    IF FOUND THEN
      NEW.bench_run_id := recent.id;
      NEW.bench_score := recent.score;
      NEW.bench_cost_per_call := recent.cost_per_call;
      NEW.bench_n := recent.expected_n;
      NEW.bench_at := recent.finished_at;
    END IF;
    RETURN NEW;
END $$;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='core1_restore_bench'
                   AND tgrelid='tank.route_evidence'::regclass) THEN
      CREATE TRIGGER core1_restore_bench BEFORE INSERT ON tank.route_evidence
        FOR EACH ROW EXECUTE FUNCTION tank.restore_bench_evidence();
    END IF;
END $$;
-- Bounded savings backfill and receipt navigation.
CREATE INDEX IF NOT EXISTS ledger_baseline_pending ON tank.ledger(tenant_id,region) WHERE baseline_status='pending';
CREATE INDEX IF NOT EXISTS ledger_baseline_unpriced ON tank.ledger(region,id) WHERE baseline_status='unpriced';
CREATE INDEX IF NOT EXISTS ledger_proof_receipts ON tank.ledger(region,ts DESC,id DESC)
    WHERE agent NOT IN ('bench','shadow') AND task_type NOT LIKE '%#shadow';

-- AGENT-1: Base pilot. Copy the current general-purpose serving route once;
-- no existing route changes, automatic promotion or new provider is introduced.
ALTER TABLE tank.policy ADD COLUMN IF NOT EXISTS baseline_model text;
DO $$
BEGIN
    -- Serialize this one-time seed across concurrent Tank starts. Preserve an
    -- existing brain policy, including any founder-selected serving model.
    PERFORM pg_advisory_xact_lock(hashtextextended('agent.base.think.seed',0));
    IF NOT EXISTS (SELECT 1 FROM tank.policy WHERE task_type='agent.base.think' AND tenant_id IS NULL) THEN
        INSERT INTO tank.policy (task_type,rung,model,priority,cache_scope,max_tokens_out,baseline_model,auto_promote)
        SELECT 'agent.base.think',rung,model,'standard','none',4096,model,false
        FROM tank.policy WHERE task_type='tier0.answer' AND tenant_id IS NULL;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS tank.agent_receipts (
    ledger_id uuid PRIMARY KEY REFERENCES tank.ledger(id),
    tenant_id uuid NOT NULL,
    room text NOT NULL,
    receipt jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS agent_receipts_tenant ON tank.agent_receipts (tenant_id,created_at);

-- Source is immutable. The ordinary tank.skills row owns candidate/staging/
-- approved/retired state, and only the existing eval and approval routes change it.
CREATE TABLE IF NOT EXISTS tank.agent_skill_submissions (
    skill_id text NOT NULL,
    version text NOT NULL,
    tenant_id uuid NOT NULL,
    region text NOT NULL,
    submitted_by_room text NOT NULL,
    package jsonb NOT NULL,
    sha256 text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (skill_id,version),
    FOREIGN KEY (skill_id,version) REFERENCES tank.skills(id,version)
);

-- DASH-1: founder controls and immutable audit history, local to this box.
CREATE TABLE IF NOT EXISTS tank.controls (
    tenant_id uuid NOT NULL,
    name text NOT NULL CHECK (name = 'paid_paused'),
    value boolean NOT NULL,
    updated_by text NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, name)
);
CREATE TABLE IF NOT EXISTS tank.control_log (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    name text NOT NULL,
    by_user text NOT NULL,
    old_value boolean NOT NULL,
    new_value boolean NOT NULL,
    at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE tank.control_log ADD COLUMN IF NOT EXISTS task text;
ALTER TABLE tank.control_log ADD COLUMN IF NOT EXISTS path text;
CREATE INDEX IF NOT EXISTS control_log_tenant_at ON tank.control_log (tenant_id, at DESC);

-- MODELS-2: provider tool charges are expenses, scoped to the platform price book.
-- Checked 2026-10-21: https://docs.perplexity.ai/docs/getting-started/pricing
-- Presets fast/low/medium/high use Fast Search ($0.001/invocation); fetch is $0.0005.
-- UUIDs make re-applying the schema a no-op without changing any policy row.
INSERT INTO tank.price_book (id, tenant_id, outcome_type, unit_price, currency, effective_from, note)
VALUES
 ('66000000-0000-4000-8000-000000000001','00000000-0000-0000-0000-000000000001',
  'perplexity.search.fast',0.001,'USD','2026-10-21T00:00:00Z',
  'Provider expense per invocation; https://docs.perplexity.ai/docs/getting-started/pricing checked 2026-10-21'),
 ('66000000-0000-4000-8000-000000000002','00000000-0000-0000-0000-000000000001',
  'perplexity.fetch',0.0005,'USD','2026-10-21T00:00:00Z',
  'Provider expense per invocation; https://docs.perplexity.ai/docs/getting-started/pricing checked 2026-10-21')
ON CONFLICT (id) DO NOTHING;

ALTER TABLE tank.ledger ADD COLUMN IF NOT EXISTS token_cost_usd numeric(20,10);
ALTER TABLE tank.ledger ADD COLUMN IF NOT EXISTS search_fee_usd numeric(20,10);
ALTER TABLE tank.ledger ADD COLUMN IF NOT EXISTS fetch_fee_usd numeric(20,10);
-- Retain the exact provider total alongside the existing six-decimal summary cost.
ALTER TABLE tank.ledger ADD COLUMN IF NOT EXISTS provider_cost_usd numeric(20,10);
ALTER TABLE tank.ledger ADD COLUMN IF NOT EXISTS research_sources jsonb;
-- Unknown charges on failed calls require reconciliation; they are never called free.
ALTER TABLE tank.ledger ADD COLUMN IF NOT EXISTS research_cost_status text;

-- CORE-2: bounded evidence joins and the client job-completion watermark.
CREATE INDEX IF NOT EXISTS tasks_tenant_ledger ON tank.tasks(tenant_id,ledger_id) WHERE ledger_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS tasks_tenant_finished ON tank.tasks(tenant_id,finished_at DESC) WHERE finished_at IS NOT NULL;

-- CORE-2 / section 8: provider defaults are explicit, never inferred from price.
CREATE TABLE IF NOT EXISTS tank.baseline_settings (
    task_type text PRIMARY KEY, override_model text, revision bigint NOT NULL DEFAULT 1,
    updated_by text NOT NULL DEFAULT 'migration', updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS tank.baseline_changes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), task_type text NOT NULL,
    old_model text, new_model text, by_user text NOT NULL, revision bigint NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(), rows_updated bigint NOT NULL DEFAULT 0,
    status text NOT NULL DEFAULT 'pending', error text,
    UNIQUE(task_type,revision)
);
ALTER TABLE tank.ledger ADD COLUMN IF NOT EXISTS standard_model text;
ALTER TABLE tank.ledger ADD COLUMN IF NOT EXISTS standard_cost_usd numeric(18,8);
ALTER TABLE tank.ledger ADD COLUMN IF NOT EXISTS top_model text;
ALTER TABLE tank.ledger ADD COLUMN IF NOT EXISTS top_cost_usd numeric(18,8);
ALTER TABLE tank.ledger ADD COLUMN IF NOT EXISTS comparison_revision bigint NOT NULL DEFAULT 0;
CREATE INDEX IF NOT EXISTS ledger_comparison_revision ON tank.ledger(task_type,region,comparison_revision,tenant_id);
CREATE TABLE IF NOT EXISTS tank.comparison_history (
    ledger_id uuid NOT NULL, tenant_id uuid NOT NULL, region text NOT NULL,
    valid_from timestamptz NOT NULL, valid_until timestamptz NOT NULL, comparison jsonb NOT NULL,
    PRIMARY KEY(ledger_id,valid_until)
);
CREATE INDEX IF NOT EXISTS comparison_history_scope ON tank.comparison_history(tenant_id,region,ledger_id,valid_until);
ALTER TABLE tank.comparison_history ADD COLUMN IF NOT EXISTS reason text;
CREATE TABLE IF NOT EXISTS tank.baseline_price_changes (
    id bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, model text NOT NULL,
    old_input numeric, old_output numeric, new_input numeric, new_output numeric,
    changed_at timestamptz NOT NULL DEFAULT now()
);
CREATE OR REPLACE FUNCTION tank.standard_model_for(family text) RETURNS text
LANGUAGE sql IMMUTABLE AS $$ SELECT CASE split_part(family,'/',1)
    WHEN 'openai' THEN 'sol' WHEN 'anthropic' THEN 'sonnet' WHEN 'gemini' THEN 'argon'
    WHEN 'xai' THEN 'grok-top' WHEN 'moonshot' THEN 'kimi' WHEN 'deepseek' THEN 'deepseek-pro'
    ELSE NULL END $$;
CREATE OR REPLACE FUNCTION tank.price_receipt() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE chosen_family text; standard_name text; selected_name text; top_name text;
        setting tank.baseline_settings%ROWTYPE; priced numeric; selected_cost numeric; top_cost numeric;
BEGIN
    IF TG_OP='UPDATE' THEN
      INSERT INTO tank.comparison_history(ledger_id,tenant_id,region,valid_from,valid_until,comparison,reason)
      VALUES(OLD.id,OLD.tenant_id,OLD.region,coalesce(OLD.baseline_priced_at,OLD.ts),now(),
        jsonb_build_object('standard_model',OLD.standard_model,'standard_cost_usd',OLD.standard_cost_usd,
          'top_model',OLD.top_model,'top_cost_usd',OLD.top_cost_usd,'baseline_model',OLD.baseline_model,
          'baseline_cost_usd',OLD.baseline_cost_usd,'baseline_status',OLD.baseline_status,
          'baseline_priced_at',OLD.baseline_priced_at,'comparison_revision',OLD.comparison_revision),
        CASE WHEN OLD.comparison_revision=0 THEN 'default migration'
          WHEN OLD.comparison_revision=NEW.comparison_revision THEN 'price refresh' ELSE 'task override' END)
      ON CONFLICT DO NOTHING;
    END IF;
    -- Serialize new receipts with a founder change so a completed batch cannot miss
    -- an in-flight receipt carrying the previous revision.
    INSERT INTO tank.baseline_settings(task_type) VALUES(NEW.task_type) ON CONFLICT DO NOTHING;
    SELECT * INTO setting FROM tank.baseline_settings WHERE task_type=NEW.task_type FOR SHARE;
    NEW.comparison_revision := coalesce(setting.revision,1);
    -- Invalidate all comparisons when actual costs are unknown or are vendor fees.
    IF to_jsonb(NEW)->>'research_cost_status'='unknown' OR NEW.model LIKE 'vendor:%' OR to_jsonb(NEW)->>'vendor' IS NOT NULL THEN
      NEW.baseline_model:=NULL; NEW.baseline_cost_usd:=NULL;
      NEW.standard_model:=NULL; NEW.standard_cost_usd:=NULL;
      NEW.top_model:=NULL; NEW.top_cost_usd:=NULL; NEW.baseline_status:='unpriced';
      NEW.baseline_priced_at:=now(); RETURN NEW;
    END IF;
    SELECT family INTO chosen_family FROM tank.proof_prices WHERE model=NEW.model;
    IF chosen_family IS NULL AND (NEW.rung=3 OR NEW.cache_hit) THEN
      SELECT a.family INTO chosen_family FROM tank.policy p JOIN tank.proof_prices a ON a.model=p.model
        WHERE p.task_type=NEW.task_type AND (p.tenant_id=NEW.tenant_id OR p.tenant_id IS NULL)
        ORDER BY p.tenant_id NULLS LAST LIMIT 1;
    END IF;
    standard_name:=tank.standard_model_for(chosen_family);
    selected_name:=coalesce(setting.override_model,standard_name);
    standard_name:=selected_name; -- A founder override replaces this task's comparison.
    SELECT model INTO top_name FROM tank.proof_prices WHERE family=chosen_family AND active
      ORDER BY input_usd+output_usd DESC,model LIMIT 1;
    SELECT NEW.tokens_in*input_usd+NEW.tokens_out*output_usd INTO priced
      FROM tank.proof_prices WHERE model=standard_name AND family=chosen_family AND active;
    SELECT NEW.tokens_in*input_usd+NEW.tokens_out*output_usd INTO selected_cost
      FROM tank.proof_prices WHERE model=selected_name AND family=chosen_family AND active;
    SELECT NEW.tokens_in*input_usd+NEW.tokens_out*output_usd INTO top_cost
      FROM tank.proof_prices WHERE model=top_name AND family=chosen_family AND active;
    IF NEW.tokens_in=0 AND NEW.tokens_out=0 AND NEW.cost_usd=0 AND (NEW.rung=3 OR NEW.cache_hit) THEN
      priced:=0; selected_cost:=0; top_cost:=0;
      standard_name:=coalesce(standard_name,'No AI call');
      selected_name:=coalesce(selected_name,'No AI call'); top_name:=coalesce(top_name,'No AI call');
    END IF;
    NEW.standard_model:=standard_name; NEW.standard_cost_usd:=priced;
    NEW.top_model:=top_name; NEW.top_cost_usd:=top_cost;
    NEW.baseline_model:=selected_name; NEW.baseline_cost_usd:=selected_cost;
    NEW.baseline_priced_at:=now();
    IF TG_OP='UPDATE' THEN
      NEW.baseline_status:=CASE WHEN priced IS NULL THEN 'unpriced' WHEN OLD.standard_cost_usd IS NOT NULL OR OLD.baseline_cost_usd IS NOT NULL
        THEN 're-priced' WHEN priced IS NOT NULL THEN 'backfilled' ELSE 'unpriced' END;
    ELSE
      NEW.baseline_status:=CASE WHEN priced IS NULL THEN 'unpriced' ELSE 'measured' END;
    END IF;
    RETURN NEW;
END $$;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='core2_reprice' AND tgrelid='tank.ledger'::regclass) THEN
      CREATE TRIGGER core2_reprice BEFORE UPDATE OF comparison_revision ON tank.ledger
        FOR EACH ROW EXECUTE FUNCTION tank.price_receipt();
    END IF;
END $$;
-- Run the historical scan and legacy-policy cleanup once, not on every start.
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM tank.policy_log WHERE detail->>'id'='2026-10-21-core2-baselines') THEN
    INSERT INTO tank.baseline_settings(task_type)
      SELECT task_type FROM tank.policy UNION SELECT task_type FROM tank.ledger WHERE comparison_revision=0
      ON CONFLICT DO NOTHING;
    INSERT INTO tank.baseline_changes(task_type,old_model,new_model,by_user,revision)
      SELECT s.task_type,NULL,NULL,'provider-default migration',s.revision FROM tank.baseline_settings s
      WHERE EXISTS(SELECT 1 FROM tank.ledger l WHERE l.task_type=s.task_type AND l.comparison_revision=0)
      ON CONFLICT DO NOTHING;
    UPDATE tank.policy SET baseline_model=NULL WHERE baseline_model IS NOT NULL;
    INSERT INTO tank.policy_log(task_type,action,by_user,detail)
      VALUES('*','switch','tank','{"id":"2026-10-21-core2-baselines","marker":true}'::jsonb);
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS shadow_tenant_task_time ON tank.shadow(tenant_id,task_type,created_at);
-- COMMAND-1A: conversation state and replay stay on this box.
CREATE TABLE IF NOT EXISTS tank.command_threads (
    thread_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    user_id text NOT NULL,
    title text NOT NULL,
    state jsonb NOT NULL,
    seq bigint NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (thread_id, tenant_id)
);
CREATE INDEX IF NOT EXISTS command_threads_owner ON tank.command_threads(tenant_id,user_id,updated_at DESC);
CREATE TABLE IF NOT EXISTS tank.command_events (
    thread_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    seq bigint NOT NULL,
    kind text NOT NULL CHECK (kind IN ('token','step','card','receipt','done','error')),
    data jsonb NOT NULL,
    PRIMARY KEY (thread_id,seq),
    FOREIGN KEY (thread_id,tenant_id) REFERENCES tank.command_threads(thread_id,tenant_id)
);
CREATE TABLE IF NOT EXISTS tank.command_builds (
    build_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    user_id text NOT NULL,
    brief_markdown text NOT NULL,
    status text NOT NULL CHECK (status IN ('queued','running','awaiting_review','done','failed')),
    pr_url text,
    ci_status text,
    review_status text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (build_id,tenant_id),
    FOREIGN KEY (thread_id,tenant_id) REFERENCES tank.command_threads(thread_id,tenant_id)
);
CREATE INDEX IF NOT EXISTS command_builds_queue ON tank.command_builds(status,created_at);
CREATE UNIQUE INDEX IF NOT EXISTS command_builds_open_thread ON tank.command_builds(thread_id)
    WHERE status IN ('queued','running','awaiting_review');
CREATE TABLE IF NOT EXISTS tank.command_followups (
    followup_id bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    build_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    followup_text text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (build_id,tenant_id) REFERENCES tank.command_builds(build_id,tenant_id)
);

-- Explicit receipt provenance: a row is attributed once, never by tenant/time heuristics.
CREATE TABLE IF NOT EXISTS tank.command_receipt_links (
    tenant_id uuid NOT NULL,
    ledger_id uuid NOT NULL REFERENCES tank.ledger(id),
    thread_id uuid NOT NULL,
    step_id text NOT NULL,
    PRIMARY KEY (tenant_id,ledger_id),
    FOREIGN KEY (thread_id,tenant_id) REFERENCES tank.command_threads(thread_id,tenant_id)
);
-- Bounded attachments remain on this box and are served only as downloads.
CREATE TABLE IF NOT EXISTS tank.command_attachments (
    attachment_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    user_id text NOT NULL,
    name text NOT NULL,
    sha256 text NOT NULL,
    content bytea NOT NULL CHECK (octet_length(content)<=5242880),
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (thread_id,tenant_id) REFERENCES tank.command_threads(thread_id,tenant_id)
);
CREATE INDEX IF NOT EXISTS command_attachments_owner ON tank.command_attachments(tenant_id,user_id,thread_id);
-- Ghost recovery idempotency; no production resource credentials or payloads.
CREATE TABLE IF NOT EXISTS tank.ghost_recovery (
    tenant_id uuid NOT NULL,
    id uuid NOT NULL,
    action text NOT NULL CHECK (action IN ('rerun_failed_deploy','restart_crashed_room')),
    target text NOT NULL,
    status text NOT NULL DEFAULT 'pending',
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id,id)
);

-- Founder-managed client squad grants. No row means chat-only access.
CREATE TABLE IF NOT EXISTS tank.tenant_squad (
    tenant_id uuid NOT NULL,
    agent text NOT NULL CHECK (agent IN ('base','tiger','market_lab','rig','tisan','radix','zenas')),
    enabled_by text NOT NULL,
    enabled_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id,agent)
);
CREATE TABLE IF NOT EXISTS tank.tenant_squad_log (
    id bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    tenant_id uuid NOT NULL,
    agent text NOT NULL,
    enabled boolean NOT NULL,
    changed_by text NOT NULL,
    changed_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS tenant_squad_log_tenant ON tank.tenant_squad_log(tenant_id,id DESC);

-- Shared Command/MoA attribution; preserve the historical schema prefix.
ALTER TABLE tank.ledger ADD COLUMN IF NOT EXISTS route_seat text;

-- WORKERS-2: host workers check-in and the founder's workers pause. New tables only.
CREATE TABLE IF NOT EXISTS tank.workers_heartbeat (
    worker text PRIMARY KEY,
    state text NOT NULL CHECK (state IN ('running','paused')),
    issue integer,
    commit text NOT NULL,
    last_error text,
    seen_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS tank.workers_controls (
    tenant_id uuid NOT NULL,
    name text NOT NULL CHECK (name = 'workers_paused'),
    value boolean NOT NULL,
    updated_by text NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, name)
);

-- MOA-1: opt-in only, no serving model or enabled policy is seeded here.
ALTER TABLE tank.policy ADD COLUMN IF NOT EXISTS moa_enabled boolean NOT NULL DEFAULT false;
ALTER TABLE tank.policy ADD COLUMN IF NOT EXISTS moa_config jsonb NOT NULL DEFAULT '{}'::jsonb;
CREATE TABLE IF NOT EXISTS tank.moa_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL,
    region text NOT NULL, task_type text NOT NULL, config_hash text NOT NULL,
    shape text NOT NULL, mode text NOT NULL, kind text NOT NULL,
    status text NOT NULL DEFAULT 'running', receipt jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS moa_runs_scope ON tank.moa_runs(tenant_id,region,task_type,created_at DESC);
CREATE TABLE IF NOT EXISTS tank.moa_shadow (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), run_id uuid NOT NULL REFERENCES tank.moa_runs(id),
    tenant_id uuid NOT NULL, region text NOT NULL, task_type text NOT NULL,
    config_hash text NOT NULL, seat text NOT NULL, current_model text NOT NULL,
    candidate_model text NOT NULL, status text NOT NULL,
    against_current numeric, against_final numeric, current_cost numeric, candidate_cost numeric,
    receipt jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(run_id,seat)
);
CREATE INDEX IF NOT EXISTS moa_shadow_scope ON tank.moa_shadow(tenant_id,region,task_type,config_hash,seat);
CREATE TABLE IF NOT EXISTS tank.moa_bench (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL,
    region text NOT NULL, task_type text NOT NULL, config_hash text NOT NULL,
    suite_hash text NOT NULL, shape text NOT NULL, mode text NOT NULL,
    status text NOT NULL, score numeric, cost_per_call numeric, samples integer NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS moa_bench_scope ON tank.moa_bench(tenant_id,region,task_type,config_hash,created_at DESC);
-- Seat receipts inherit the original task's baseline, never an arbitrary seat alias.
-- Trigger names run alphabetically; this follows CORE-1's existing baseline snapshot.
CREATE OR REPLACE FUNCTION tank.moa_baseline_snapshot() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE chosen text; rate tank.proof_prices%ROWTYPE;
BEGIN
    IF NEW.route_seat IS NULL OR NEW.task_type NOT LIKE '%#moa.%' THEN RETURN NEW; END IF;
    SELECT p.baseline_model INTO chosen FROM tank.policy p
      WHERE p.task_type=split_part(NEW.task_type,'#moa.',1)
        AND (p.tenant_id=NEW.tenant_id OR p.tenant_id IS NULL)
      ORDER BY p.tenant_id NULLS LAST LIMIT 1;
    IF chosen IS NOT NULL THEN
      SELECT * INTO rate FROM tank.proof_prices WHERE model=chosen;
      NEW.baseline_model := chosen;
      NEW.baseline_cost_usd := NEW.tokens_in*rate.input_usd+NEW.tokens_out*rate.output_usd;
      NEW.baseline_status := CASE WHEN rate.model IS NULL THEN 'unpriced' ELSE 'measured' END;
      NEW.baseline_priced_at := rate.updated_at;
    END IF;
    RETURN NEW;
END $$;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='zz_moa_baseline'
                   AND tgrelid='tank.ledger'::regclass) THEN
        CREATE TRIGGER zz_moa_baseline BEFORE INSERT ON tank.ledger
            FOR EACH ROW EXECUTE FUNCTION tank.moa_baseline_snapshot();
    END IF;
END $$;
-- ---------- 21 Oct 2026: the window's turns need a platform policy ----------
-- command.turn had no row, so every turn in /chats failed with "no policy".
-- Tank's planning message supplies the system prompt; the founder promotes later.
INSERT INTO tank.policy (task_type, rung, model, priority, cache_scope, max_tokens_out, system_prompt) VALUES
  ('command.turn', 1, 'luna', 'urgent', 'none', 2048, NULL)
ON CONFLICT DO NOTHING;
