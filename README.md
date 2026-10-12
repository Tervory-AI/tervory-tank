# Tervory platform

One repo, one Coolify deploy: Tank (the model gateway and ledger), the Workspace (the client product), and the shared stores. Tank is the only path to any AI model in Tervory. Every call goes through it, every call is logged, and the routing policy lives in a table rather than in code.

Build Pack v2, section "Tank — the centrepiece", is the spec this repo implements.

## What is in this repo

| Path | What it is |
| --- | --- |
| `docker-compose.yml` | The Phase 0/1 stack: PostgreSQL, Redis, Qdrant, LiteLLM, Tank API. Coolify deploys this file. |
| `litellm/config.yaml` | The model roster LiteLLM exposes. Keys come from the environment, never from this file. |
| `db/schema.sql` | The `tank` schema: `ledger`, `policy`, `evals`. Runs automatically on first start. |
| `tank/` | The FastAPI service: `/v1/route` (the one endpoint agents call), `/v1/tasks` (the board), `/v1/ledger/{id}/feedback` (a person's verdict), `/v1/ledger/summary`, `/v1/policy`, `/health`. |
| `workspace/` | The Next.js client product: Chat, the Tasks board, thumbs up/down on every answer, and the Ledger. Clerk organizations are tenants. Coolify attaches the public domain to this service. |
| `.env.example` | Every variable the stack needs. Copy the names into Coolify's environment panel; put the values in Doppler. |

## How a call flows

```
agent or Workspace
  → POST /v1/route  {tenant_id, agent, task_type, priority, messages}
  → Tank reads tank.policy for task_type
  → Tank calls LiteLLM with the chosen model
  → Tank writes one row to tank.ledger (tenant, agent, task_type, model, tokens, cost, latency)
  → response returns to the caller
```

## Running it

Locally with Docker: `cp .env.example .env`, fill in the keys, `docker compose up`. Tank answers on `http://localhost:8000/health`.

On the server: Coolify → New resource → Docker Compose → this repo. Paste the variable names from `.env.example` into the environment panel.

## First checks after deploy

1. `GET /health` returns `{"ok": true}`.
2. `POST /v1/route` with `task_type: "tier0.answer"` returns an answer and a `ledger_id`.
3. `GET /v1/ledger/summary?tenant_id=<id>` shows the cost of that call.

## What is deliberately not here yet

Batch queue, semantic cache, eval harness, graduation loop. Feedback already lands in `tank.ledger.feedback`; the eval harness and graduation loop read from there. They are the Tank build order steps 3–6 in the pack and are added one at a time, each with its tests.
