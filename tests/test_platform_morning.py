"""Founder digest: real ledger SQL, frozen Pacific dates, SMTP boundary only."""

import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock
import uuid

import pytest
import httpx
from types import SimpleNamespace

import morning_report as report
from test_tank_tenant_boundaries import boundary as _boundary

boundary = _boundary


@pytest.mark.parametrize(
    "stamp,day,hours",
    [
        ("2026-11-04T14:59:59+00:00", "2026-11-03", 7),
        ("2026-11-04T15:00:00+00:00", "2026-11-04", 7),
        ("2026-11-01T15:00:00+00:00", "2026-11-01", 8),
        ("2026-03-08T14:00:00+00:00", "2026-03-08", 6),
    ],
)
def test_night_ends_at_seven_pacific_across_dst(stamp, day, hours):
    date, since, until = report.period(datetime.fromisoformat(stamp))
    assert date.isoformat() == day and (until - since).total_seconds() == hours * 3600
    assert until.astimezone(report.PACIFIC).hour == 7


def mail_settings(monkeypatch):
    for prefix in ("SMTP_", "FOUNDER_REPORT_SMTP_"):
        for suffix in ("HOST", "PORT", "USER", "PASSWORD", "FROM"):
            monkeypatch.delenv(prefix + suffix, raising=False)
    monkeypatch.setenv("FOUNDER_REPORT_TO", "founder@example.test")
    monkeypatch.setenv("FOUNDER_REPORT_SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("FOUNDER_REPORT_SMTP_FROM", "tank@example.test")


def test_transport_is_optional_and_uses_existing_setting_names(monkeypatch):
    mail_settings(monkeypatch)
    config = report.transport()
    assert config["PORT"] == 587 and config["TO"] == "founder@example.test"
    monkeypatch.delenv("FOUNDER_REPORT_TO")
    assert report.transport() is None
    monkeypatch.setenv("FOUNDER_REPORT_TO", "founder@example.test")
    monkeypatch.setenv("FOUNDER_REPORT_SMTP_USER", "fixture")
    with pytest.raises(ValueError, match="Incomplete"):
        report.transport()


@pytest.mark.parametrize("port", [465, 587])
def test_smtp_uses_verified_tls_and_only_configured_recipient(monkeypatch, port):
    mail_settings(monkeypatch)
    monkeypatch.setenv("FOUNDER_REPORT_SMTP_PORT", str(port))
    connection = Mock()
    connection.__enter__ = Mock(return_value=connection)
    connection.__exit__ = Mock(return_value=False)
    smtp = Mock(return_value=connection)
    ssl = Mock(return_value=connection)
    monkeypatch.setattr(report.smtplib, "SMTP", smtp)
    monkeypatch.setattr(report.smtplib, "SMTP_SSL", ssl)
    message = report.EmailMessage()
    message["To"] = "founder@example.test"
    report.smtp_send(report.transport(), message)
    if port == 465:
        smtp.assert_not_called()
        assert ssl.call_args.kwargs["context"].check_hostname
    else:
        ssl.assert_not_called()
        assert connection.starttls.call_args.kwargs["context"].check_hostname
    connection.send_message.assert_called_once_with(message)


def sample():
    return {
        "day": "2026-11-04",
        "region": "us-east",
        "calls": 2,
        "known_spend_usd": 0.2,
        "unpriced_calls": 1,
        "comparable_savings_usd": 0,
        "comparable_calls": 0,
        "failed_jobs": 1,
        "unverified_calls": 1,
        "deploys": [],
        "deploy_coverage": "Tank process-start observations; room health is not attested",
        "deployment_checks": {"status": "not_configured", "checks": []},
        "graduation_candidates": [],
    }


@pytest.mark.asyncio
async def test_one_durable_claim_survives_concurrent_senders_and_restart(
    boundary, monkeypatch
):
    b = boundary
    mail_settings(monkeypatch)
    monkeypatch.setattr(report, "build", AsyncMock(return_value=sample()))
    smtp = Mock()
    monkeypatch.setattr(report, "smtp_send", smtp)
    at = datetime.fromisoformat("2026-11-04T15:00:00+00:00")
    answers = await asyncio.gather(
        report.send_once(b.tank, at), report.send_once(b.tank, at)
    )
    assert sum(a["sent"] for a in answers) == 1
    assert (await report.send_once(b.tank, at))["reason"] == "already_claimed"
    smtp.assert_called_once()
    message = smtp.call_args.args[1]
    assert (
        message["To"] == "founder@example.test"
        and "unpriced calls: 1" in message.get_content()
    )
    async with b.pool.acquire() as conn:
        assert (
            await conn.fetchval(
                "SELECT status FROM tank.founder_morning_reports WHERE tenant_id=$1",
                b.tank.PLATFORM_TENANT,
            )
            == "sent"
        )


@pytest.mark.asyncio
async def test_uncertain_smtp_is_never_retried_and_logs_class_only(
    boundary, monkeypatch, caplog
):
    b = boundary
    mail_settings(monkeypatch)
    monkeypatch.setattr(report, "build", AsyncMock(return_value=sample()))
    smtp = Mock(side_effect=RuntimeError("private transport detail"))
    monkeypatch.setattr(report, "smtp_send", smtp)
    at = datetime.fromisoformat("2026-11-04T15:00:00+00:00")
    assert await report.send_once(b.tank, at) == {"sent": False, "status": "uncertain"}
    assert (await report.send_once(b.tank, at))["reason"] == "already_claimed"
    smtp.assert_called_once()
    assert (
        "RuntimeError" in caplog.text and "private transport detail" not in caplog.text
    )


@pytest.mark.asyncio
async def test_digest_uses_actual_night_rows_and_keeps_content_out(
    boundary, monkeypatch
):
    b = boundary
    monkeypatch.delenv("TANK_GITHUB_READ_TOKEN", raising=False)
    at = datetime.fromisoformat("2026-11-04T15:00:00+00:00")
    stamp = datetime.fromisoformat("2026-11-04T09:00:00+00:00")
    ledger = uuid.uuid4()
    async with b.pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO tank.ledger
            (id,tenant_id,region,agent,task_type,model,rung,outcome,ts,cost_usd,cost_status)
            VALUES($1,$2,'us-east','base','placeholder.report','placeholder',1,'delivered',$3,.2,'set')""",
            ledger,
            b.tenants[0],
            stamp,
        )
        await conn.execute(
            """INSERT INTO tank.ledger
            (tenant_id,region,agent,task_type,model,rung,outcome,ts,cost_usd,cost_status)
            VALUES($1,'us-east','base','placeholder.report','placeholder',1,'unverified',$2,0,'not_set'),
                  ($1,'za','base','placeholder.report','placeholder',1,'delivered',$2,99,'set')""",
            b.tenants[1],
            stamp,
        )
        await conn.execute(
            """INSERT INTO tank.tasks
            (tenant_id,agent,task_type,title,input,status,finished_at)
            VALUES($1,'base','placeholder.report','private title','[]','failed',$2)""",
            b.tenants[1],
            stamp,
        )
        await conn.execute("""INSERT INTO tank.policy(task_type,rung,model,candidate_model)
            VALUES('placeholder.report',1,'placeholder','placeholder.candidate')""")
        await conn.execute(
            """INSERT INTO tank.shadow
            (tenant_id,ledger_id,task_type,primary_model,candidate_model,primary_content,agreement,created_at)
            VALUES($1,$2,'placeholder.report','placeholder','placeholder.candidate','private answer',.98,$3)""",
            b.tenants[0],
            ledger,
            stamp,
        )
    data = await report.build(b.tank, at)
    assert (
        data["calls"],
        data["known_spend_usd"],
        data["unpriced_calls"],
        data["failed_jobs"],
    ) == (2, 0.2, 1, 1)
    assert data["comparable_calls"] == 0 and data["comparable_savings_usd"] == 0
    candidate = next(
        r
        for r in data["graduation_candidates"]
        if r["task_type"] == "placeholder.report"
    )
    assert candidate["night_samples"] == 1 and candidate["night_agreement"] == 0.98
    text = json.dumps(data) + report.render(data)
    for private in (
        "private title",
        "private answer",
        str(b.tenants[0]),
        str(b.tenants[1]),
    ):
        assert private not in text
    actor = {"X-Tervory-Tenant": str(b.tenants[0]), "X-Tervory-User": "member-fixture"}
    assert (
        await b.client.get("/v1/platform/morning-report", headers=actor)
    ).status_code == 403


@pytest.mark.asyncio
async def test_release_observations_are_full_sha_and_idempotent(boundary, monkeypatch):
    b = boundary
    monkeypatch.setattr(b.tank, "tank_sha", lambda: "unknown")
    assert await report.record_release(b.tank) is False

    monkeypatch.setattr(b.tank, "tank_sha", lambda: "a" * 40)
    assert (
        sum(
            await asyncio.gather(
                report.record_release(b.tank), report.record_release(b.tank)
            )
        )
        == 1
    )
    assert await report.record_release(b.tank) is False


@pytest.mark.asyncio
async def test_deploy_history_is_read_only_night_scoped_and_marks_truncation(
    monkeypatch,
):
    monkeypatch.setenv("TANK_GITHUB_READ_TOKEN", "fixture-read-token")
    requests = []

    def feed(request):
        requests.append(request)
        assert request.method == "GET" and request.url.host == "api.github.com"
        assert request.url.path.endswith("/actions/workflows/deploy-on-merge.yml/runs")
        return httpx.Response(
            200,
            json={
                "workflow_runs": [
                    {
                        "head_sha": "a" * 40,
                        "run_started_at": "2026-11-04T09:00:00Z",
                        "conclusion": "success",
                    },
                    {
                        "head_sha": "b" * 40,
                        "run_started_at": "2026-11-04T07:59:59Z",
                        "conclusion": "failure",
                    },
                ]
            },
            headers={"link": '<https://api.github.com/next>; rel="next"'},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(feed)) as client:
        _, since, until = report.period(
            datetime.fromisoformat("2026-11-04T15:00:00+00:00")
        )
        result = await report.deployment_checks(
            SimpleNamespace(_http=client), since, until
        )
    assert result["status"] == "incomplete" and len(requests) == 1
    assert result["checks"] == [
        {"sha": "a" * 40, "state": "success", "started_at": "2026-11-04T09:00:00+00:00"}
    ]


@pytest.mark.asyncio
async def test_scheduler_waits_until_seven_and_sends_once(monkeypatch):
    clock = [datetime.fromisoformat("2026-11-04T14:59:59+00:00")]

    class Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock[0]

    waits = []

    async def sleep(seconds):
        waits.append(seconds)
        if len(waits) == 2:
            raise asyncio.CancelledError
        clock[0] += timedelta(seconds=seconds)

    send = AsyncMock()
    monkeypatch.setattr(report, "datetime", Frozen)
    monkeypatch.setattr(report, "record_release", AsyncMock())
    monkeypatch.setattr(report, "send_once", send)
    monkeypatch.setattr(report, "asyncio", SimpleNamespace(sleep=sleep))
    with pytest.raises(asyncio.CancelledError):
        await report.loop(SimpleNamespace())
    assert waits == [1, 60]
    send.assert_awaited_once()
    assert send.await_args.args[1].isoformat() == "2026-11-04T15:00:00+00:00"


@pytest.mark.asyncio
async def test_digest_uses_dispatch_night_and_counts_failed_evaluations_once(
    boundary, monkeypatch
):
    from test_core2_savings import prices, seed

    b = boundary
    monkeypatch.delenv("TANK_GITHUB_READ_TOKEN", raising=False)
    before = datetime.fromisoformat("2026-11-04T07:00:00+00:00")
    stamp = datetime.fromisoformat("2026-11-04T09:00:00+00:00")
    at = datetime.fromisoformat("2026-11-04T15:00:00+00:00")
    await prices(b.pool)
    receipts, task = await seed(b.pool, b.tenants[0], day=before)
    failed = [uuid.uuid4(), uuid.uuid4()]
    async with b.pool.acquire() as conn:
        await conn.execute(
            "UPDATE tank.ledger SET sent_at=$3,cost_status='set',priority='offpeak' WHERE tenant_id=$1 AND id=$2",
            b.tenants[0],
            receipts[0],
            stamp,
        )
        await conn.execute(
            "UPDATE tank.tasks SET created_at=$3,started_at=$4,finished_at=$4 WHERE tenant_id=$1 AND id=$2",
            b.tenants[0],
            task,
            before,
            stamp,
        )
        for job in failed:
            await conn.execute(
                """INSERT INTO tank.skill_revalidations
                (id,tenant_id,task_type,old_model,model,policy,skill_id,version,completed_at,error)
                VALUES($1,$2,'fixture.boundary','placeholder','placeholder','{}','base.private0','1.0.0',$3,'eval_gate_failed')""",
                job,
                b.tank.PLATFORM_TENANT,
                stamp,
            )
        for _ in range(2):
            await conn.execute(
                """INSERT INTO tank.ledger
                (tenant_id,region,agent,task_type,model,rung,outcome,ts,cost_usd,cost_status,revalidation_id)
                VALUES($1,'us-east','base','fixture.boundary','placeholder',1,'failed',$2,.02,'set',$3)""",
                b.tank.PLATFORM_TENANT,
                stamp,
                failed[0],
            )
    data = await report.build(b.tank, at)
    assert data["calls"] == 3 and data["known_spend_usd"] == pytest.approx(0.14)
    assert data["comparable_calls"] == 1 and data[
        "comparable_savings_usd"
    ] == pytest.approx(0.2)
    assert data["failed_jobs"] == 2
