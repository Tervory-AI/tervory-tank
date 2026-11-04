"""Offline Tank route -> Workspace loader -> screen fixtures. No real credentials.

Database doubles supply query rows to the production route functions. Their JSON,
not a separately written UI example, is the input to dashboards-w4-render.cjs.
"""
import ast
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from datetime import datetime, timezone
from typing import Any
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tank"))
os.environ["TANK_API_KEY"] = "placeholder-w4-key"
os.environ["TERVORY_ADMIN_USER_IDS"] = "placeholder-founder"
from fastapi import FastAPI, Header, Depends
from fastapi.testclient import TestClient
import controls
import dashboards
import gold
import graduate
import proof
import workers_status

TENANT = uuid.UUID("00000000-0000-0000-0000-0000000000aa")


class Rows:
    def __init__(self):
        self.reads = []

    def acquire(self, **_):
        return self

    def transaction(self, **_):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def fetch(self, sql, *args):
        self.reads.append((sql, args))
        if "FROM eligible" in sql:
            assert args[0] == TENANT
            return []
        if "FROM tank.ledger WHERE" in sql:
            return [dict(day="2026-11-02", calls=14, code=6, delivered=12, spent=4.25, unpriced=0),
                    dict(day="2026-11-03", calls=101, code=31, delivered=83, spent=8.5, unpriced=0)]
        if "FROM tank.skills" in sql:
            return [dict(id=f"base.placeholder-{i}", version="1.0.0", last_eval_score=score, eval_threshold=.99)
                    for i, score in enumerate([1, .995, .5])]
        if "GROUP BY agent,status" in sql:
            return [dict(agent="base", status="running", jobs=3), dict(agent="base", status="queued", jobs=2),
                    dict(agent="tiger", status="queued", jobs=4)]
        if "FROM tank.tasks" in sql:
            assert args == (TENANT,)
            return [dict(id=f"placeholder-job-{i}", title=f"placeholder requested work {i}", status=status)
                    for i, status in enumerate(["queued", "running", "done", "failed"])]
        if "tank.tenant_squad" in sql:
            assert args == (TENANT,)
            return [dict(agent=agent) for agent in ["base", "tiger", "market_lab", "zenas"]]
        if "FROM tank.gold_examples" in sql:
            return [dict(agent="base", skill_id="base.placeholder-check", checked=2, holdout=1, candidates=7)]
        if "FROM tank.policy p" in sql:
            assert args == (None, True)
            return [dict(task_type="placeholder.market_research", rung=1, model="placeholder-primary-model",
                         candidate_model="placeholder-cheaper-model", previous_model=None, shadow_rate=1,
                         eval_threshold=.99, min_shadow_samples=200, max_reject_rate=.05, auto_promote=False,
                         cache_scope="tenant", priority=1, semantic_cache=False, promoted_at=None,
                         n=250, agreement=1, prim_cost=.024, cand_cost=.004, calls_30d=2500,
                         cost_30d=60, cache_hits=0)]
        return []

    async def fetchval(self, sql, *args):
        self.reads.append((sql, args))
        if "FROM tank.tasks" in sql:
            return 1235
        if "tank.controls" in sql or "tank.workers_controls" in sql:
            return False
        return 0

    async def fetchrow(self, sql, *args):
        self.reads.append((sql, args))
        if "FROM eligible" in sql:
            assert args[0] == TENANT
            return dict(work_count=41, jobs_count=9, spent="34.75", would_have_cost="11800",
                        saved="11765.25", free_count=12, standards=["placeholder-model-name"],
                        tops=["placeholder-top-model"], top_cost="12000", top_spent="34.75",
                        top_saved="11965.25", top_count=41, quality_pending=False)
        if "FROM tank.workers_controls" in sql:
            return dict(value=False, updated_by="placeholder-founder", updated_at=datetime(2026, 11, 3, tzinfo=timezone.utc))
        if "FROM tank.command_builds" in sql:
            return dict(queued=2, running=1, awaiting_review=0)
        return None


rows = Rows()
dashboards.db = controls.db = lambda: rows
gold.runtime = lambda: SimpleNamespace(pool=lambda: rows, box_region=lambda: "us-east")
proof.runtime = gold.runtime
workers_status.db = lambda: rows


async def empty(*_):
    return []


async def router_steps(*_):
    return {}


# Load the exact read-only route without booting unrelated model/queue services.
# No route logic, eligibility arithmetic, SQL or auth decision is rewritten.
tree = ast.parse((ROOT / "tank/main.py").read_text())
route = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "graduation")
route.decorator_list = []
scope = dict(__name__=__name__, uuid=uuid, Any=Any, Header=Header, pool=lambda: rows,
             datetime=datetime, timezone=timezone, graduate=graduate,
             _num=lambda value: None if value is None else float(value), _note=lambda row: row,
             _code_quotes=empty, _live_price_quotes=empty,
             routellm_shadow=SimpleNamespace(ladder=router_steps))
exec(compile(ast.Module(body=[route], type_ignores=[]), str(ROOT / "tank/main.py"), "exec"), scope)

app = FastAPI()
app.include_router(dashboards.router)
app.include_router(controls.router)
app.include_router(gold.router)
app.include_router(workers_status.founder_router)
app.include_router(proof.client_router)
app.get("/v1/graduation", dependencies=[Depends(dashboards.workspace_only)])(scope["graduation"])
headers = {"x-tank-key": "placeholder-w4-key", "x-tervory-admin": "placeholder-founder",
           "x-tervory-user": "placeholder-founder", "x-tervory-tenant": str(gold.PLATFORM_TENANT), "x-tervory-role": "founder"}
client = TestClient(app)
assert client.get("/v1/dashboards/founder").status_code == 404
assert client.get(f"/v1/dashboards/client?tenant_id={TENANT}").status_code == 404
result = {}
for path in ["/v1/dashboards/founder", f"/v1/dashboards/client?tenant_id={TENANT}", "/v1/controls", "/v1/graduation",
             "/v1/gold/summary", "/v1/controls/workers", f"/v1/client-savings?tenant_id={TENANT}"]:
    response = client.get(path, headers=headers)
    assert response.status_code == 200, response.text
    result[path] = response.json()
assert result["/v1/dashboards/founder"]["daily"][1]["delivered"] == 83
assert result[f"/v1/dashboards/client?tenant_id={TENANT}"]["recent"][0]["title"] == "placeholder requested work 0"
assert result["/v1/graduation"][0]["eligible"] is True
assert "placeholder-model-name" not in json.dumps(result[f"/v1/client-savings?tenant_id={TENANT}"])
target = Path(sys.argv[1])
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(result, default=str, indent=2) + "\n")
print("PASS: production dashboard, gold, control and graduation reads over isolated placeholder rows; no network/model writes.")
