# Runbook: review, merge, deploy and check without Claude

Every task follows the same five steps. Nothing here needs a laptop install or a secret typed by hand.

## 1. Build
Paste the task's prompt (`docs/cursor/prompts/<ID>.md`) into Cursor. Cursor opens a pull request and writes "ready for review" when CI is green.

## 2. Review (a second Cursor agent, then you)
Start a **new** Cursor agent and paste:
```
You are the reviewer, not the builder. Repo Tervory-AI/tervory-tank, pull request #<N>. Read AGENTS.md and the task brief named in the PR. Do not change code. Check and report PASS/FAIL for each:
1. Only files the brief allows were changed (list any others).
2. No secrets, keys or passwords in code, logs or tests.
3. No paid service, model call or key that the brief does not name (AGENTS rule 10).
4. Every Tank read/write is scoped by tenant_id (AGENTS rule 3).
5. Schema changes are additive and idempotent (AGENTS rule 5).
6. Tests were added for the brief's "Done when" items, and CI is green.
7. Anything the founder must decide.
Post the report as a comment on the PR. End with APPROVE or CHANGES NEEDED.
```
If it says **CHANGES NEEDED**, paste its comment back to the builder agent. If it says **APPROVE**, read the summary yourself, then merge.

## 3. Merge
On the PR page click **Squash and merge**. The main app redeploys by itself in about 3 minutes. Check that the newest deployment says **Success**:
https://coolify.tervory.com/project/dguxczrbmbqvezo3qib0twge/environment/0zjmt7swwqqevcjq21121oq8/application/xnmc0jkz8j9i5jh1jwanbsfv/deployment

## 4. Task-specific steps after merge
| Task | After merge |
| --- | --- |
| **B3 (Base room)** | Run **room setup** (below) with room `base`, then the **room check** with `base`. Expected extra neighbours for Base only: `tiger` and `searxng` = yes. |
| **R3 (RIG)** | Run **room setup** with room `rig`. Then in Coolify open `agent-rig` → **General** → domain for the service: `https://rig.tervory.com` → Save → **Deploy**. Then the **room check** with `rig`. Open https://rig.tervory.com/health: it should say ok. |
| **C13 / RX1 / TS1 / R3 skills** | Workspace → **Skills** (https://app.tervory.com/skills) → find the new version → **Approve**. |
| **C13 + B3 both live** | Workspace → **Data** → the batch → **Re-run** with "model skipped". It costs $0 on the new code skills. |
| **OPS4** | GitHub → Actions → **watchdog** → **Run workflow** once. It should pass. After that it runs every 10 minutes by itself. |
| **TG2, W1, T6** | Nothing extra; check the new page in the app. |

### Room setup (creates the room, makes its passwords unseen, deploys)
GitHub → **Actions** → **coolify-ops** → **Run workflow**: https://github.com/Tervory-AI/tervory-tank/actions/workflows/coolify-ops.yml
- `op` = `room-setup`
- `room` = the agent folder name (`base` or `rig`)
- leave the rest empty → **Run workflow**. Wait about 6 minutes; the run should be green.

### Room check (read-only; paste in the Coolify terminal)
https://coolify.tervory.com/terminal → **localhost** → paste, changing `r=base` to the room:
```
r=base; c=$(docker ps --format '{{.Names}}' | grep -m1 "^agent-$r"); echo "nets: $(docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' $c)"; docker exec $c python -c 'exec("import socket\ndef r(h):\n try:\n  socket.getaddrinfo(h,None);return \"yes\"\n except Exception:\n  return \"no\"\nprint(\" \".join(h+\"=\"+r(h) for h in [\"tank\",\"postgres\",\"hermes\",\"tiger\",\"searxng\",\"litellm\",\"redis\",\"qdrant\",\"workspace\"]))")'; docker exec $c python -c 'exec("import asyncio,asyncpg,os\nasync def m():\n c=await asyncpg.connect(os.environ[\"DATABASE_URL\"])\n print(\"role=\"+await c.fetchval(\"select current_user\"))\n try:\n  await c.fetchval(\"select 1 from tank.ledger limit 1\");print(\"ledger=READABLE (BAD)\")\n except Exception:\n  print(\"ledger=denied (good)\")\nasyncio.run(m())")'
```
**Pass** = `tank=yes postgres=yes hermes=yes`, everything else `no` (Base may also say `tiger=yes searxng=yes`), `role=agent_<room>`, `ledger=denied (good)`. Anything else: do not use the room; check the PR's compose changes.

## 5. If something breaks
- **Undo a merge:** on the merged PR click **Revert** → merge the revert PR. The app redeploys the previous code.
- **Undo a deployment fast:** Coolify → the app → **Rollback** → pick the previous Success.
- **Something is down:** the watchdog (OPS4) opens a GitHub issue "Down: …" and emails you. Coolify → the app → **Logs** shows why.

## Order (no clashes)
Wave 1 together: B3, C13, R3, RX1, TS1, OPS4. → Wave 2 after B3 merged: TG2, W1, T6.
