"""Role SQL for one agent. No database. The password must not leak into errors."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "_chassis"))

from chassis.db import ensure_schema  # noqa: E402
from chassis.roles import (  # noqa: E402
    RoleProvisionError,
    apply_roles,
    passwords_from_env,
    quote_literal,
    statements_for,
)

_SAMPLE = "placeholder-role-secret"


def _sql(agent: str = "template", password: str = _SAMPLE) -> str:
    return "\n".join(statements_for(agent, password))


def test_role_sql_is_idempotent_and_not_a_superuser():
    text = _sql()
    assert "CREATE SCHEMA IF NOT EXISTS agent_template" in text
    assert "IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agent_template')" in text
    assert "CREATE ROLE agent_template" in text
    assert "ALTER ROLE agent_template WITH" in text
    for flag in (
        "LOGIN",
        "NOSUPERUSER",
        "NOCREATEDB",
        "NOCREATEROLE",
        "NOREPLICATION",
        "NOBYPASSRLS",
    ):
        assert flag in text
    assert re.search(r"(?<!NO)SUPERUSER", text) is None
    assert "BYPASSRLS" in text and "NOBYPASSRLS" in text
    assert re.search(r"(?<!NO)BYPASSRLS", text) is None
    assert "GRANT USAGE, CREATE ON SCHEMA agent_template TO agent_template" in text
    assert "GRANT" not in text.replace(
        "GRANT USAGE, CREATE ON SCHEMA agent_template TO agent_template", ""
    )
    for schema in ("tank", "base", "public"):
        assert f"REVOKE ALL ON SCHEMA {schema} FROM agent_template" in text
    assert "REVOKE ALL ON ALL TABLES IN SCHEMA tank FROM agent_template" in text
    assert "REVOKE ALL ON ALL TABLES IN SCHEMA base FROM agent_template" in text
    assert "ALTER ROLE agent_template SET search_path = agent_template" in text
    assert statements_for("template", _SAMPLE) == statements_for("template", _SAMPLE)


def test_one_role_does_not_name_another_agent():
    left = _sql("template")
    right = _sql("market_lab")
    assert "agent_market_lab" not in left
    assert "agent_template" not in right
    assert "agent_market_lab" in right


def test_password_is_quoted_and_tags_do_not_break():
    assert quote_literal("a'b") == "'a''b'"
    quoted = _sql("template", "a'b")
    assert "'a''b'" in quoted
    body = statements_for("template", "aa$pw$bb")[1]
    assert body.startswith("DO $pwx$")
    assert body.rstrip().endswith("$pwx$;")
    with pytest.raises(ValueError):
        quote_literal("bad\x00pass")


def test_empty_password_and_bad_names_are_refused():
    with pytest.raises(ValueError):
        statements_for("template", "   ")
    with pytest.raises(ValueError):
        statements_for("Not A Name", _SAMPLE)
    found = passwords_from_env(
        {
            "AGENT_DB_PASSWORD_TEMPLATE": "  abc  ",
            "AGENT_DB_PASSWORD_": "nope-empty-suffix",
            "AGENT_DB_PASSWORD_BAD-NAME": "skipped-bad-suffix",
            "OTHER_PASSWORD": "not-an-agent-password",
            "AGENT_DB_PASSWORD_TEMPLATE_BLANK": "   ",
        }
    )
    assert found == [("template", "abc")]


def test_apply_roles_hides_the_password_when_sql_fails():
    class Boom:
        async def execute(self, statement: str) -> None:
            raise RuntimeError(statement)

    async def run():
        with pytest.raises(RoleProvisionError) as caught:
            await apply_roles(Boom(), {"AGENT_DB_PASSWORD_TEMPLATE": _SAMPLE})
        message = str(caught.value)
        assert _SAMPLE not in message
        assert "agent_template" in message
        assert caught.value.__cause__ is None

    import asyncio

    asyncio.run(run())


def test_apply_roles_runs_every_statement_and_returns_ids():
    class Record:
        def __init__(self) -> None:
            self.sql: list[str] = []

        async def execute(self, statement: str) -> None:
            self.sql.append(statement)

    async def run():
        conn = Record()
        applied = await apply_roles(
            conn,
            {
                "AGENT_DB_PASSWORD_MARKET_LAB": "placeholder-market",
                "AGENT_DB_PASSWORD_TEMPLATE": "placeholder-template",
                "AGENT_DB_PASSWORD_NOPE": "",
            },
        )
        assert applied == ["market_lab", "template"]
        blob = "\n".join(conn.sql)
        assert "agent_market_lab" in blob
        assert "agent_template" in blob
        assert "placeholder-market" in blob
        assert "NOSUPERUSER" in blob

    import asyncio

    asyncio.run(run())


def test_limited_role_can_start_when_the_schema_already_exists():
    class Conn:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def execute(self, statement: str) -> None:
            self.calls.append(statement)
            if statement.startswith("CREATE SCHEMA"):
                raise RuntimeError("permission denied")

        async def fetchval(self, _query: str, name: str):
            assert name == "agent_template"
            return 1

    async def run():
        conn = Conn()
        assert await ensure_schema(conn, "template") == "agent_template"
        assert any("CREATE TABLE IF NOT EXISTS agent_template.jobs" in sql for sql in conn.calls)

    import asyncio

    asyncio.run(run())


def test_missing_schema_still_raises():
    class Conn:
        async def execute(self, statement: str) -> None:
            if statement.startswith("CREATE SCHEMA"):
                raise RuntimeError("permission denied")

        async def fetchval(self, _query: str, _name: str):
            return None

    async def run():
        with pytest.raises(RuntimeError, match="permission denied"):
            await ensure_schema(Conn(), "template")

    import asyncio

    asyncio.run(run())
