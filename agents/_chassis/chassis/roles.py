"""Database role for one agent. Idempotent. The password is never logged.

Tank runs this at start from AGENT_DB_PASSWORD_<AGENT>. The role can use only
schema agent_<name>. It is not a superuser and cannot read tank or base.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

_AGENT = re.compile(r"^[a-z][a-z0-9_]{0,40}$")
_PREFIX = "AGENT_DB_PASSWORD_"

_ROLE_OPTIONS = (
    "LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"
)


class RoleProvisionError(RuntimeError):
    """Provisioning failed. The message does not include the password or the SQL."""


def role_name(agent: str) -> str:
    if _AGENT.fullmatch(agent) is None:
        raise ValueError("agent name must be lowercase letters, digits, and underscores")
    return f"agent_{agent}"


def quote_literal(value: str) -> str:
    if "\x00" in value:
        raise ValueError("password contains a null")
    return "'" + value.replace("'", "''") + "'"


def passwords_from_env(env: Mapping[str, str]) -> list[tuple[str, str]]:
    """(agent id, password) for every non-empty AGENT_DB_PASSWORD_<AGENT>."""
    found: list[tuple[str, str]] = []
    for key in sorted(env):
        if not key.startswith(_PREFIX):
            continue
        raw = env[key].strip()
        if not raw:
            continue
        agent = key[len(_PREFIX):].lower()
        if _AGENT.fullmatch(agent) is None:
            continue
        found.append((agent, raw))
    return found


def statements_for(agent: str, password: str) -> list[str]:
    """SQL that creates or updates one agent role. Safe to run on every start."""
    if not password or not password.strip():
        raise ValueError("password is empty")
    name = role_name(agent)
    literal = quote_literal(password.strip())
    tag = "pw"
    while f"${tag}$" in password:
        tag += "x"
    return [
        f"CREATE SCHEMA IF NOT EXISTS {name}",
        f"""
DO ${tag}$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{name}') THEN
    CREATE ROLE {name} {_ROLE_OPTIONS} PASSWORD {literal};
  ELSE
    ALTER ROLE {name} WITH {_ROLE_OPTIONS} PASSWORD {literal};
  END IF;
END
${tag}$;
""".strip(),
        f"GRANT USAGE, CREATE ON SCHEMA {name} TO {name}",
        f"REVOKE ALL ON SCHEMA tank FROM {name}",
        f"REVOKE ALL ON SCHEMA base FROM {name}",
        f"REVOKE ALL ON SCHEMA public FROM {name}",
        f"REVOKE ALL ON ALL TABLES IN SCHEMA tank FROM {name}",
        f"REVOKE ALL ON ALL TABLES IN SCHEMA base FROM {name}",
        f"ALTER ROLE {name} SET search_path = {name}",
    ]


async def apply_roles(conn: Any, env: Mapping[str, str]) -> list[str]:
    """Run statements_for for every configured agent. Returns the agent ids."""
    applied: list[str] = []
    for agent, password in passwords_from_env(env):
        for statement in statements_for(agent, password):
            try:
                await conn.execute(statement)
            except Exception:
                raise RoleProvisionError(f"could not provision {role_name(agent)}") from None
        applied.append(agent)
    return applied
