"""Deadline-aware selection uses only recorded roster prices and a frozen clock."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
import uuid

import pytest

import offpeak_schedule
import priority_queue


NOW = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)
INFO = {"offpeak": {"timezone": "UTC", "charge_multiplier": .25,
                    "windows": [{"days": [2], "start": "14:00", "end": "16:00"}]}}


def choose(hours, **kwargs):
    return offpeak_schedule.select(INFO, NOW, NOW + timedelta(hours=hours), **kwargs)


def test_cheapest_known_window_within_deadline():
    plan = choose(5, batch_discount=.5)
    assert plan == {"dispatch_at": "2026-11-04T14:00:00+00:00",
                    "deadline": "2026-11-04T17:00:00+00:00",
                    "mode": "foreground", "charge_multiplier": .25}


def test_deadline_before_discount_uses_peak_without_waiting_past_it():
    assert choose(1, batch_discount=.5)["dispatch_at"] == NOW.isoformat()
    assert choose(1, batch_discount=.5)["charge_multiplier"] == 1


def test_batch_requires_its_completion_window_and_cheapest_rate():
    assert choose(25, batch_discount=.1)["mode"] == "batch"
    assert choose(5, batch_discount=.1)["mode"] == "foreground"
    assert choose(25, batch_discount=.5)["mode"] == "foreground"


def test_equal_prices_prefer_earliest_completion():
    info = {"offpeak": {**INFO["offpeak"], "charge_multiplier": .5}}
    plan = offpeak_schedule.select(info, NOW, NOW + timedelta(days=2), batch_discount=.5)
    assert plan["mode"] == "foreground"  # 14:02 beats tomorrow's provider batch.


def test_no_published_discount_sends_now():
    plan = offpeak_schedule.select({}, NOW, NOW + timedelta(hours=1))
    assert plan["dispatch_at"] == NOW.isoformat() and plan["charge_multiplier"] == 1


def test_dst_and_special_dates_are_local_price_data():
    info = {"offpeak": {"timezone": "America/Los_Angeles", "charge_multiplier": .5,
                        "windows": [], "dates": ["2026-11-05"]}}
    plan = offpeak_schedule.select(info, NOW, NOW + timedelta(days=2))
    assert plan["dispatch_at"] == "2026-11-05T08:00:00+00:00"


@pytest.mark.parametrize("stamp,expected", [
    ("2026-11-01T08:45:00+00:00", "2026-11-01T09:00:00+00:00"),
    ("2026-11-01T09:15:00+00:00", "2026-11-01T09:15:00+00:00"),
])
def test_both_occurrences_of_a_fall_back_price_window(stamp, expected):
    at = datetime.fromisoformat(stamp)
    info = {"offpeak": {"timezone": "America/Los_Angeles", "charge_multiplier": .5,
                        "windows": [{"days": [6], "start": "01:00", "end": "01:30"}]}}
    plan = offpeak_schedule.select(info, at, at + timedelta(hours=2))
    assert plan["dispatch_at"] == expected and plan["charge_multiplier"] == .5


@pytest.mark.parametrize("deadline", [NOW, NOW + timedelta(seconds=119), NOW.replace(tzinfo=None)])
def test_invalid_or_unachievable_deadline_refuses(deadline):
    with pytest.raises(ValueError):
        offpeak_schedule.select(INFO, NOW, deadline)


@pytest.mark.parametrize("discount", [-1, 0, 2, "NaN", "Infinity"])
def test_invalid_price_never_becomes_a_free_window(discount):
    with pytest.raises(ValueError):
        offpeak_schedule.select({"offpeak": {**INFO["offpeak"], "charge_multiplier": discount}},
                                NOW, NOW + timedelta(days=1))


@pytest.mark.asyncio
async def test_worker_waits_then_uses_existing_foreground_dispatch(monkeypatch):
    clock = [NOW]
    req = SimpleNamespace(deadline=NOW + timedelta(hours=5), task_type="placeholder.task", tenant_id=uuid.uuid4())
    policy = {"model": "placeholder", "updated_at": "same", "max_cost_usd": 1}
    tank = SimpleNamespace(RouteRequest=SimpleNamespace(model_validate=lambda _: req),
        load_policy=AsyncMock(return_value=policy),
        _batch_price=AsyncMock(return_value={"provider": "openai", "native": "placeholder", "discount": .5}),
        run_route=AsyncMock(return_value=SimpleNamespace(model_dump=lambda **_: {"delivered": True})))
    job = {"id": uuid.uuid4(), "tenant_id": uuid.uuid4(), "status": "queued", "request": {},
           "policy": {"routing": policy, "messages": [], "generation": {}, "escalation": []},
           "task_id": None, "caller": None, "model_override": None}
    conn = SimpleNamespace(execute=AsyncMock())
    monkeypatch.setattr(priority_queue, "now", lambda: clock[0])
    monkeypatch.setattr(priority_queue, "model_info", AsyncMock(return_value=INFO))
    await priority_queue._process(tank, conn, job)
    tank.run_route.assert_not_awaited()
    assert not conn.execute.await_count
    clock[0] = NOW + timedelta(hours=2)
    await priority_queue._process(tank, conn, job)
    tank.run_route.assert_awaited_once()
    assert tank.run_route.await_args.kwargs["_receipt_id"] == job["id"]
    assert conn.execute.await_args.args[1:3] == (job["id"], job["tenant_id"])


@pytest.mark.asyncio
async def test_expired_job_is_failed_without_a_paid_call(monkeypatch):
    req = SimpleNamespace(deadline=NOW, task_type="placeholder.task", tenant_id=uuid.uuid4())
    policy = {"model": "placeholder", "updated_at": "same"}
    tank = SimpleNamespace(RouteRequest=SimpleNamespace(model_validate=lambda _: req),
        load_policy=AsyncMock(return_value=policy),
        _batch_price=AsyncMock(return_value={"provider": "openai", "native": "placeholder", "discount": .5}),
        run_route=AsyncMock())
    job = {"id": uuid.uuid4(), "tenant_id": uuid.uuid4(), "status": "queued", "request": {},
           "policy": {"routing": policy, "messages": [], "generation": {}}}
    conn = SimpleNamespace(execute=AsyncMock())
    monkeypatch.setattr(priority_queue, "now", lambda: NOW)
    monkeypatch.setattr(priority_queue, "model_info", AsyncMock(return_value=INFO))
    await priority_queue._process(tank, conn, job)
    tank.run_route.assert_not_awaited()
    assert conn.execute.await_args.args[-1] == "deadline_exceeded"
