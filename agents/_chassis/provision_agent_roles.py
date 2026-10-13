"""Create agent database roles, then start Tank.

Mounted into the Tank container and used as its command. The password stays in
the environment and is never written to a log. If no AGENT_DB_PASSWORD_* is
set, Tank still starts.
"""

from __future__ import annotations

import asyncio
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from chassis.roles import RoleProvisionError, apply_roles  # noqa: E402

_SCHEMA = "/app/schema.sql"


async def _provision() -> None:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        return
    import asyncpg

    conn = await asyncpg.connect(url)
    try:
        # schema.sql ships in the Tank image. Apply it first so REVOKE has a
        # schema to hit. Tank applies the same file again on startup.
        if os.path.isfile(_SCHEMA):
            with open(_SCHEMA, encoding="utf-8") as handle:
                await conn.execute(handle.read())
        await apply_roles(conn, os.environ)
    finally:
        await conn.close()


def main() -> None:
    try:
        asyncio.run(_provision())
    except RoleProvisionError as exc:
        sys.stderr.write(str(exc) + "\n")
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001 — do not print the driver error; it can echo the URL
        sys.stderr.write(f"agent role provisioning failed: {type(exc).__name__}\n")
        sys.exit(1)
    os.execvp("uvicorn", ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"])


if __name__ == "__main__":
    main()
