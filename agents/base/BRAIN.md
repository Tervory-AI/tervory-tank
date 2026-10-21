# Base Hermes pilot (AGENT-1)

PR: https://github.com/Tervory-AI/tervory-tank/pull/216

Nous Research Hermes Agent **v0.22.2** is pinned to release commit
`d923a5eb487a17c0a68801bba9ef0f56c81040a8`.
Its [MIT licence](https://github.com/NousResearch/hermes-agent/blob/d923a5eb487a17c0a68801bba9ef0f56c81040a8/LICENSE)
is retained at `/opt/hermes/LICENSE`. The brain image uses Python 3.14, required
by this upstream release. Source is installed as upstream's editable package;
bundled skills and optional skills are removed. No model credential is present.

## Task flow

1. The existing Base worker pins approved versions and calls its brain service.
2. The service recalls Base memories for the tenant before starting work. A
   wrong-tenant response or memory outage fails visibly. Each task gets a fresh
   process; session state and approved skills live under that tenant's directory.
3. Hermes plans through Tank, then calls the existing code pipeline. During this
   first pass, Tank defers model enrichment and withholds paid-service keys from
   the skill context. The original approved packages are unchanged.
4. Hermes can recover unresolved records using the private browser, offline
   Docker sandbox and approved Skala skills. Recovery retries are bounded. It
   cannot load a candidate it submits. Human checks are recorded, never solved.
5. After recovery, the existing pipeline continues automatically with its existing
   paid rungs for unresolved or deferred records. The thinking calls themselves
   are policy-routed model calls and are charged; the free-first order applies to
   enrichment and paid search, not to Hermes' planning.
6. The service remembers the result and source references, then completes the
   receipt. A failed remember marks the task failed while retaining work.

## Tank and Skala boundary

All new endpoint logic is in `tank/agent_skills.py`. `tank/main.py` contains route
registration and the explicitly approved narrow guard on its existing Skala run
path. Tank's image copies the new module. Schema is additive and reapplies safely.

- `POST /v1/agents/base/chat/completions`: Bearer or X-Tank-Key authentication,
  `X-Tenant-ID`, `X-Task-ID`, `X-Home-Region: us-east`. Request model names cannot
  override policy. Text/tool calls and buffered SSE are supported. The ledger and
  receipt transaction commits before a successful completion is returned.
- `GET /v1/agents/base/skills?tenant_id=...&home_region=us-east`: approved, present
  Base versions only, with agentskills.io `SKILL.md` files. Authored versions are
  restricted to their submitting tenant and region.
- `POST /v1/agents/base/skills/candidates`: immutable new `base.learned.*` version,
  always candidate, with submitting room/tenant/region recorded. Source is durable
  in Postgres and reconstructed after restart. No update, replacement or approval
  operation exists here. Existing Skala evals and founder approval remain required.
- `POST /v1/skala/{id}/run`: the only execution path. Base's key can run only its
  own approved versions, never preview or another tenant's authored version.
- `GET /v1/agents/base/receipts?tenant_id=...&task_id=...`: thinking receipts with
  ledger IDs, model cost, policy baseline and savings. An unavailable baseline is
  null, never an invented saving. The new routes refuse every other room's key.

The initial `agent.base.think` policy copies the current platform `tier0.answer`
model once. It does not alter any existing route or select a new provider. The
new policy has no cache or automatic promotion. Existing policy edits survive
schema reapplication. Failed gateway responses are sanitized and recorded as
failed; missing accounting never produces a successful completion.

The full task receipt is stored in `agent_base.tasks.input.brain_receipt` and on
Base's volume. The existing `GET /v1/base/batches?tenant_id=...` Tank proxy adds
`brain_tasks`: task ID, status, error and receipt. This is the COMMAND-1 work-panel
integration contract; no window UI is changed here. Existing skill model ledger
rows also receive the Base task ID.

## Private tools

Base has its own browser volume, tenant-separated storage and history, and a
private browser network. The gateway permits only exact configured HTTPS hosts
on port 443 and rejects private, loopback and metadata DNS answers. Redirects and
subresources are checked too. The default hosts are `www.atf.gov,atf.gov`;
additional public hosts are an operator setting in `BASE_ALLOWED_HOSTS`. No
wildcards, credentials or custom ports are accepted. The current pipeline uses
HTML; OCR is not invoked without an image-reading requirement.

The sandbox daemon is a privileged **Base-only sidecar**, running rootless Docker
inside an isolated namespace. It has neither the host Docker socket nor host
filesystem mounts. Its only exposed API is on Base's internal sandbox network,
reachable only by the brain. Each execution has a read-only root, no network,
no forwarded environment credentials and only the current run's work directory.
The Python execution image is imported from a bundled rootfs, so runtime startup
needs no internet. The sidecar's Compose CPU/memory limit bounds all its children;
inner cgroup limits depend on host support. No other room joins either private
network. Base's browser adapter points to its gateway, never Tiger.

## Cloud verification

The standard CI tests cover route authentication, policy enforcement, tool-call
preservation, durable receipts, real Postgres schema reapplication, candidate
immutability, existing eval/approval integration, tenant isolation, memory order,
free recovery before paid continuation, and the work-panel receipt contract.

Managed-cloud checkpoint on 21 October 2026: **34 focused tests passed**, including
the unchanged Dockerfile and billing regressions, Base room tests and real
Postgres checks. The actual pinned Hermes protocol test passed (two model calls
and two receipts), the real Chromium isolation test passed, and the actual Hermes
Docker backend test passed (denied internet, no forwarded key, own work volume).
These component checks use synthetic fixtures. The owner-approved integrated
sandbox pilot below replaces the pre-merge live run; CI links are in the PR.

Opt-in checks run actual containers without model/provider credentials. Build
`agents/base/Dockerfile.{brain,browser,gateway,sandbox}` with repository-root build
context, tagging each image `tervory-agent1-<name>:cloud`, then run:

```sh
AGENT1_HERMES_IMAGE=tervory-agent1-brain:cloud pytest -q tests/test_agent1_hermes_runtime.py
AGENT1_CONTAINER_IMAGES=1 pytest -q tests/test_agent1_container_runtime.py
```

The Hermes protocol check runs the pinned AIAgent against a synthetic model and
the real Tank adapter. It verifies two model calls, two scoped receipts, the
restricted six-tool list and pipeline continuation. This is **not a live ATF
pilot**. Container checks exercise actual Chromium, cross-room refusal and the
actual Hermes Docker backend. They remove only their randomly named resources.

## Recorded sandbox pilot

The owner requested an offline replacement for the pre-merge live pilot: run Tank
from this branch with recorded LiteLLM answers, a generated throwaway Base room
key and a small ATF-format fixture. No production key, endpoint or model is used.

- [Input fixture](pilot/atf-fixture.json): two synthetic Delaware rows.
- [Recording](pilot/recording.json): actual HTTP calls, room-key validation booleans,
  recorded model answers, Postgres ledger rows, approved export, loaded skill
  folders, resulting records and private container identities.
- [Complete receipt](pilot/receipt.json): recall, approved skills, default pipeline,
  browser refusal, sandbox action, continuation, thinking costs and remember.

The real Tank app and existing Base pipeline run against a newly created test
Postgres database. The real Hermes memory API uses its in-memory test store and
deterministic local embeddings; it includes a second-tenant decoy. Site requests
return recorded missing-site responses. The pinned upstream agent, its room
service, Chromium and rootless Docker backend execute normally. Only the test
database has seeded approved registry entries; source packages remain unchanged.
LiteLLM prices are synthetic accounting values, not billed spend. Actual model
spend is zero. An expected browser refusal is retained as a failed tool step;
it is not represented as a successful public-page fetch.

To reproduce in a managed cloud sandbox, build the four images above, provide a
throwaway Postgres admin DSN in `POOL_SCHEMA_DATABASE_URL`, and run:

```sh
AGENT1_PILOT=1 AGENT1_PILOT_OUTPUT=/tmp/base-pilot pytest -q -s tests/test_agent1_pilot.py
```

The harness generates temporary keys, records no credentials, and removes only
its randomly named containers, volumes, networks and database on completion.

## How Claude runs the live pilot

**live ATF run: done by Claude on Boston after merge**

This is the assigned post-merge handoff, not a claim that the live run has already
occurred. This lane does not merge or deploy.

1. After founder merge and authorized Boston deployment, verify the existing
   Base room key, database role and Hermes connection are configured. Run
   `python agents/base/check_brain_isolation.py ROOM BRAIN SANDBOX BROWSER GATEWAY`
   with the five deployed container names. Require every isolation check to pass.
2. Save a current official ATF state file containing only Delaware rows, retaining
   its original ATF columns. Record its source URL, snapshot date and row count.
   Use the authorized tenant and US region. Browser visits are limited to the
   exact configured `BASE_ALLOWED_HOSTS`; a refusal must remain in the receipt.
3. Open `https://app.tervory.com/data`, name the batch with state and snapshot date,
   upload that CSV/TSV, select **FFL engine**, uncheck **preview (allow unapproved
   skill versions)** and click **Run Base**. The existing server-side equivalent
   is `POST /v1/base/run` with `tenant_id`, `batch`, `records`, `engine: "ffl"`,
   `preview: false`, `split_by_state: false`. Keep keys server-side.
4. Record the returned task ID. Inspect the batch on `/data` and Base's results on
   `/base`. Read `GET /v1/base/batches?tenant_id=...` through Tank and save the
   matching `brain_tasks[].receipt`, along with source/snapshot/count/task ID and
   outcome. The full receipt also lives in `agent_base.tasks.input.brain_receipt`.
5. Confirm recall is first and tenant-scoped; loaded skills match Skala's approved
   Base export; default pipeline and free recovery precede continuation; browser
   actions use Base's volume and container; human checks are recorded; remember
   is last. Join `tank.ledger` to `tank.agent_receipts` on `ledger_id`, filtering
   both tenant and task, and verify each thinking call's model, cost, baseline and
   outcome. Attach the complete live receipt to PR #216 after the run.
