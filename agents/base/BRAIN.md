# Base Hermes pilot (AGENT-1)

Draft PR: https://github.com/Tervory-AI/tervory-tank/pull/216

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
All use synthetic fixtures, not a substitute ATF pilot. CI status is linked in
the PR for its current commit.

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

## Live proof after authorized deployment

No production deployment is performed by this lane. After founder review and an
authorized deployment, run the five-container isolation gate documented in
`docs/cursor/ROOMS.md` before taking real jobs. Existing `TANK_KEY_BASE` must be
set in Tank and Base; existing Base database and Hermes access must work.

Use the Base page to import one small state from the public ATF list (Delaware is
a suitable bounded pilot), engine `ffl`, preview off. The equivalent existing
route is `POST /v1/base/run`, with tenant ID, batch, public records and engine.
Record the source URL, snapshot date, count, task ID, outcome and complete receipt.
Read `GET /v1/base/batches?tenant_id=...` for `brain_tasks[].receipt`; verify recall
first, recovery before paid continuation, remember last, and the policy-routed
thinking ledger rows in `tank.ledger` joined to `tank.agent_receipts`. Query all
rows with both tenant ID and task ID. Confirm the run's skills are approved and
browser history is on Base's volume.

The required live ATF run is **pending**: this managed cloud workspace has no
existing Base room credential or nonproduction Tank endpoint running this branch.
The operator has been asked once to inject the existing key through the cloud
secret mechanism and provide that endpoint. Do not paste keys into chat or logs,
create a new provider, deploy production, or substitute synthetic evidence for
that live receipt. Keep the PR draft until the live proof and CI are complete.
