"""One offline execution per Workspace/Tank acceptance row; external I/O is stubbed."""

from __future__ import annotations

import json
from pathlib import Path
import re
import uuid

import pytest
import yaml

import test_command as chats
import test_core2_savings as savings
import test_dashboards as dashboards
import test_execution_receipt as execution
import test_offpeak_deadline as offpeak
import test_platform_morning as morning
import test_platform_roster as roster
import test_platform_routellm_serving as graduation
import test_platform_workspace as workspace
import test_registry_frozen as registry
import test_shell_nav as shell
import test_tank_ladder as routing
from skala_b3_b4 import test_lifecycle as lifecycle

ROOT = Path(__file__).resolve().parents[2]
boundary = workspace.boundary
ladder = routing.ladder
runtime = chats.runtime
command_pool = chats.command_pool
api = chats.api
conn = dashboards.conn
client = dashboards.client
database = savings.database
env = lifecycle.env

ROWS = [
    ("P01", "test_p01_shell"),
    ("P02", "test_p02_dashboard_render"),
    ("P03", "test_p03_founder_controls"),
    ("P04", "test_p04_chats_auto"),
    ("P05", "test_p05_conversation_ownership"),
    ("P06", "test_p06_receipt_unknowns"),
    ("P07", "test_p07_ledger_scope"),
    ("P08", "test_p08_savings_reconcile"),
    ("P09", "test_p09_code_ladder"),
    ("P10", "test_p10_actual_execution_receipt"),
    ("P11", "test_p11_price_window_and_deadline"),
    ("P12", "test_p12_expired_work"),
    ("P13", "test_p13_retirement_and_rollback"),
    ("P14", "test_p14_roster_before_policy"),
    ("P15", "test_p15_founder_onboarding"),
    ("P16", "test_p16_regional_content_transport"),
    ("P17", "test_p17_task_board"),
    ("P18", "test_p18_wrong_with_note"),
    ("P19", "test_p19_recorded_results"),
    ("P20", "test_p20_morning_ledger"),
    ("P21", "test_p21_morning_smtp_claim"),
    ("P22", "test_p22_seven_pacific"),
    ("P23", "test_p23_product_registries"),
    ("P24", "test_p24_global_paid_pause"),
    ("P25", "test_p25_founder_promotion_bar"),
    ("P26", "test_p26_multiple_deployments"),
]


def test_sheet_has_exactly_one_offline_case_per_row():
    sheet = (ROOT / "docs/acceptance/platform.md").read_text()
    rows = re.findall(r"^\| (P\d\d) `([^`]+)` \|", sheet, flags=re.M)
    assert rows == ROWS
    names = [name for _, name in ROWS]
    assert len(names) == len(set(names))
    assert len(ROWS) == len({ident for ident, _ in ROWS})
    assert set(names) == {name for name in globals() if re.fullmatch(r"test_p\d\d_.*", name)}


def test_p01_shell():
    shell.test_sidebar_order_squad_popout_and_escape()


def test_p02_dashboard_render():
    dashboards.test_frontend_access_sources_and_banned_copy()


def test_p03_founder_controls(client, conn):
    dashboards.test_non_founder_cannot_read_or_write_controls(client, conn)


@pytest.mark.asyncio
async def test_p04_chats_auto(runtime):
    await chats.test_auto_turn_uses_existing_router(runtime)


@pytest.mark.asyncio
async def test_p05_conversation_ownership(api):
    await chats.test_persistence_search_ownership_and_replay(api)


def test_p06_receipt_unknowns():
    chats.test_receipts_never_invent_baseline()
    chats.test_receipt_ids_are_explicit_and_unknown_cost_is_not_zero()


@pytest.mark.asyncio
async def test_p07_ledger_scope(boundary):
    b = boundary
    async with b.pool.acquire() as db:
        await db.execute("""INSERT INTO tank.ledger
            (tenant_id,agent,task_type,model,rung,outcome,cost_usd,cost_status)
            VALUES($1,'base','fixture','fixture-own',1,'delivered',.1,'set'),
                  ($1,'base','fixture','fixture-pending',1,'unverified',0,'not_set'),
                  ($2,'base','fixture','fixture-other',1,'delivered',999,'set')""",
            *b.tenants)
    response = await b.client.get("/v1/ledger/summary", params={"tenant_id": str(b.tenants[0])})
    assert response.status_code == 200
    data = response.json()
    assert data["calls"] == 2 and data["delivered"] == 1 and data["unpriced"] == 1
    assert data["cost_usd"] == .1
    assert {row["model"] for row in data["by_model"]} == {"fixture-own", "fixture-pending"}
    assert (await b.client.get("/v1/ledger/summary", params={"tenant_id": str(uuid.uuid4())})).json()["calls"] == 0


@pytest.mark.asyncio
async def test_p08_savings_reconcile(database, monkeypatch):
    await savings.test_graph_totals_reconcile_to_every_page_and_scope(database, monkeypatch)


@pytest.mark.asyncio
async def test_p09_code_ladder(ladder):
    await routing.test_rung_three_receipts_transcripts_and_direct_skill_runs(ladder)


@pytest.mark.asyncio
async def test_p10_actual_execution_receipt(ladder, monkeypatch):
    await execution.test_actual_route_receipt_after_escalation_and_cache_remain_distinct(ladder, monkeypatch)


@pytest.mark.asyncio
async def test_p11_price_window_and_deadline(ladder, monkeypatch):
    offpeak.test_cheapest_known_window_within_deadline()
    await offpeak.test_deadline_before_next_discount_delivers_one_existing_receipt(ladder, monkeypatch)


@pytest.mark.asyncio
async def test_p12_expired_work(monkeypatch):
    await offpeak.test_expired_job_is_failed_without_a_paid_call(monkeypatch)


@pytest.mark.asyncio
async def test_p13_retirement_and_rollback(env, tmp_path):
    await lifecycle.test_retire_day_29_refused_day_30_allowed_files_kept_and_rollback_works(env, tmp_path)


@pytest.mark.asyncio
async def test_p14_roster_before_policy(env, tmp_path, monkeypatch):
    await roster.test_roster_evals_precede_new_policy_and_existing_target_gate_still_holds(env, tmp_path, monkeypatch)


@pytest.mark.asyncio
async def test_p15_founder_onboarding(boundary):
    await workspace.test_founder_home_onboarding_is_immutable_and_ordinary_requests_use_it(boundary)


def test_p16_regional_content_transport():
    workspace.test_workspace_routes_private_content_only_to_the_recorded_home()


@pytest.mark.asyncio
async def test_p17_task_board(boundary):
    b = boundary
    delivered, _ = await workspace.seed(b, b.tenants[0])
    unverified, _ = await workspace.seed(b, b.tenants[0], outcome="unverified")
    foreign, _ = await workspace.seed(b, b.tenants[1])
    async with b.pool.acquire() as db:
        await db.execute("UPDATE tank.ledger SET cost_status='not_set' WHERE tenant_id=$1", b.tenants[0])
    response = await b.client.get("/v1/workspace/tasks", headers=workspace.headers(b.tenants[0]))
    assert response.status_code == 200
    rows = {row["id"]: row for row in response.json()["tasks"]}
    assert rows[str(delivered)]["status"] == "delivered"
    assert rows[str(unverified)]["status"] == "unverified"
    assert rows[str(delivered)]["cost_pending"] and rows[str(delivered)]["cost_usd"] is None
    assert str(foreign) not in rows


@pytest.mark.asyncio
async def test_p18_wrong_with_note(boundary):
    b = boundary
    task, ledger = await workspace.seed(b, b.tenants[0])
    foreign, _ = await workspace.seed(b, b.tenants[1])
    unverified, _ = await workspace.seed(b, b.tenants[0], outcome="unverified")
    headers = workspace.headers(b.tenants[0])
    path = f"/v1/workspace/tasks/{task}/feedback"
    response = await b.client.post(path, headers=headers, json={"verdict": "wrong", "note": "placeholder correction"})
    assert response.status_code == 200 and response.json()["verdict"] == "wrong"
    async with b.pool.acquire() as db:
        row = await db.fetchrow("SELECT feedback,feedback_kind,feedback_note,feedback_by FROM tank.ledger WHERE id=$1 AND tenant_id=$2", ledger, b.tenants[0])
    assert tuple(row) == ("rejected", "wrong", "placeholder correction", "member-fixture")
    assert (await b.client.post(path, headers=headers, json={"verdict": "wrong", "note": "x" * 1001})).status_code == 422
    assert (await b.client.post(f"/v1/workspace/tasks/{foreign}/feedback", headers=headers, json={"verdict": "wrong"})).status_code == 404
    assert (await b.client.post(f"/v1/workspace/tasks/{unverified}/feedback", headers=headers, json={"verdict": "wrong"})).status_code == 409


@pytest.mark.asyncio
async def test_p19_recorded_results(boundary):
    b = boundary
    task, ledger = await workspace.seed(b, b.tenants[0])
    await workspace.seed(b, b.tenants[1])
    async with b.pool.acquire() as db:
        await db.execute("UPDATE tank.tasks SET result=NULL WHERE id=$1 AND tenant_id=$2", task, b.tenants[0])
        await db.execute("""INSERT INTO tank.transcripts(ledger_id,tenant_id,task_type,messages,content)
            VALUES($1,$2,'placeholder.task','[]','actual fixture transcript')""", ledger, b.tenants[0])
    response = await b.client.get("/v1/workspace/results", headers=workspace.headers(b.tenants[0]))
    assert response.status_code == 200
    rows = response.json()["results"]
    assert len(rows) == 1 and rows[0]["id"] == str(task)
    assert rows[0]["result"] == "actual fixture transcript" and rows[0]["ledger_id"] == str(ledger)
    assert "download_url" not in rows[0]


@pytest.mark.asyncio
async def test_p20_morning_ledger(boundary, monkeypatch):
    await morning.test_digest_uses_dispatch_night_and_counts_failed_evaluations_once(boundary, monkeypatch)


@pytest.mark.asyncio
async def test_p21_morning_smtp_claim(boundary, monkeypatch):
    await morning.test_one_durable_claim_survives_concurrent_senders_and_restart(boundary, monkeypatch)


@pytest.mark.asyncio
async def test_p22_seven_pacific(monkeypatch):
    for stamp, day, hours in (
        ("2026-11-04T14:59:59+00:00", "2026-11-03", 7),
        ("2026-11-04T15:00:00+00:00", "2026-11-04", 7),
        ("2026-11-01T15:00:00+00:00", "2026-11-01", 8),
        ("2026-03-08T14:00:00+00:00", "2026-03-08", 6),
    ):
        morning.test_night_ends_at_seven_pacific_across_dst(stamp, day, hours)
    await morning.test_scheduler_waits_until_seven_and_sends_once(monkeypatch)


def test_p23_product_registries():
    expected = json.loads(registry.GOLDEN.read_text())
    assert expected["origin_commit"] == registry.ORIGIN_COMMIT
    assert registry.fresh_snapshot() == expected["registry"]


@pytest.mark.asyncio
async def test_p24_global_paid_pause(conn, monkeypatch):
    await dashboards.test_main_call_stops_after_cache_miss_and_cache_still_runs(conn, monkeypatch, 1)


def test_p25_founder_promotion_bar():
    graduation.test_routellm_cannot_lower_founder_bar(200, .98, "hold")
    graduation.test_routellm_cannot_lower_founder_bar(200, .99, "promote")


def test_p26_multiple_deployments():
    from routing_data import _catalog

    for filename in ("config.yaml", "config.za.yaml"):
        config = yaml.safe_load((ROOT / "litellm" / filename).read_text())
        assert config["router_settings"]["routing_strategy"] == "cost-based-routing"
        rows = config["model_list"]
        groups = _catalog(rows, [])["groups"]
        multi = {name: entries for name, entries in groups.items() if len(entries) > 1}
        assert multi
        for name, entries in multi.items():
            assert len(entries) == sum(row.get("model_name") == name for row in rows)
