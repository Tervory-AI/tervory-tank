#!/bin/sh
# Prove one agent box can reach Tank and Postgres, and nothing else.
# This file stands alone. Paste it on the server and run:
#   sh check_isolation.sh <agent-container>
# Prints PASS or FAIL per check. Exits 1 if any check fails.
# Read-only except a probe table in the agent's own schema, which it drops,
# and one ping job posted to the box.
# Never prints a password or a connection string.

set -u

container="${1:?usage: sh check_isolation.sh <agent-container>}"
failed=0

say() {
  printf '%s\n' "$1"
}

mark() {
  if [ "$1" -eq 0 ]; then
    say "PASS $2"
  else
    say "FAIL $2"
    failed=1
  fi
}

has_part() {
  _rest=$1
  _want=$2
  while [ -n "$_rest" ]; do
    _part=${_rest%%[-_.]*}
    if [ "$_part" = "$_want" ]; then
      return 0
    fi
    case "$_rest" in
      *[-_.]*) _rest=${_rest#*[-_.]} ;;
      *) return 1 ;;
    esac
  done
  return 1
}

if ! docker inspect "$container" >/dev/null 2>&1; then
  say "FAIL container $container is not on this docker host"
  exit 1
fi

self_name=$(docker inspect -f '{{.Name}}' "$container")
self_name=${self_name#/}

health=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container")
say "health status: $health"
if [ "$health" = "healthy" ]; then
  mark 0 "container is healthy"
else
  mark 1 "container is healthy"
fi

# Single-label names. Docker DNS answers these; it does not ask the public internet.
resolves() {
  docker exec "$container" python -c 'import socket,sys
try:
    socket.getaddrinfo(sys.argv[1], None)
except socket.gaierror:
    sys.exit(1)
' "$1" >/dev/null 2>&1
}

for host in tank postgres; do
  if resolves "$host"; then
    mark 0 "$host resolves"
  else
    mark 1 "$host resolves"
  fi
done

# tiger stays dark until C8. agent-other stands in for any second agent: it is not
# on this network, so it has no name here.
for host in workspace redis qdrant litellm searxng tiger agent-other; do
  if resolves "$host"; then
    mark 1 "$host does not resolve"
  else
    mark 0 "$host does not resolve"
  fi
done

if docker exec "$container" python -c 'import urllib.request, urllib.error
try:
    urllib.request.urlopen("http://tank:8000/health", timeout=5).read()
except urllib.error.HTTPError:
    pass
' >/dev/null 2>&1; then
  mark 0 "tank answers"
else
  mark 1 "tank answers"
fi

if docker exec "$container" python -c 'import socket
s = socket.create_connection(("postgres", 5432), 5)
s.close()
' >/dev/null 2>&1; then
  mark 0 "postgres answers"
else
  mark 1 "postgres answers"
fi

# Network membership. Printed in full so a human can see who shares a network.
# The gateway (tervory-gw-*) may hold only this agent, tank, and postgres.
say "--- docker inspect networks ---"
docker inspect -f '{{range $name, $net := .NetworkSettings.Networks}}{{$name}}{{"\n"}}{{end}}' "$container"
nets=$(docker inspect -f '{{range $name, $net := .NetworkSettings.Networks}}{{$name}} {{end}}' "$container")
gateway_seen=0
for net in $nets; do
  say "network $net members:"
  members=$(docker network inspect -f '{{range .Containers}}{{.Name}}{{"\n"}}{{end}}' "$net" 2>/dev/null || true)
  if [ -z "$members" ]; then
    say "(none)"
  else
    printf '%s\n' "$members"
  fi
  case "$net" in
    *tervory-gw*)
      gateway_seen=1
      has_self=0
      has_tank=0
      has_pg=0
      unexpected=""
      for member in $members; do
        short=${member#/}
        if [ -z "$short" ]; then
          continue
        fi
        if [ "$short" = "$self_name" ] || [ "$short" = "$container" ]; then
          has_self=1
          continue
        fi
        if has_part "$short" tank; then
          has_tank=1
          continue
        fi
        if has_part "$short" postgres; then
          has_pg=1
          continue
        fi
        unexpected="$unexpected $short"
      done
      if [ "$has_self" -eq 1 ] && [ "$has_tank" -eq 1 ] && [ "$has_pg" -eq 1 ] && [ -z "$unexpected" ]; then
        mark 0 "gateway $net holds only this agent, tank, and postgres"
      else
        mark 1 "gateway $net holds only this agent, tank, and postgres"
        if [ -n "$unexpected" ]; then
          say "unexpected members:$unexpected"
        fi
      fi
      ;;
  esac
done
if [ "$gateway_seen" -eq 0 ]; then
  mark 1 "gateway network tervory-gw is attached"
else
  mark 0 "gateway network tervory-gw is attached"
fi

# A ping job must reach done. The template handles kind "ping".
if docker exec "$container" python -c 'import json, time, urllib.request
body = json.dumps({
    "tenant_id": "00000000-0000-0000-0000-000000000001",
    "kind": "ping",
    "input": {"proof": True},
}).encode()
req = urllib.request.Request(
    "http://127.0.0.1:8000/jobs",
    data=body,
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(req, timeout=10) as resp:
    job = json.load(resp)
job_id = job["id"]
tenant = job["tenant_id"]
status = ""
deadline = time.time() + 45
while time.time() < deadline:
    with urllib.request.urlopen(
        "http://127.0.0.1:8000/jobs/%s?tenant_id=%s" % (job_id, tenant),
        timeout=10,
    ) as resp:
        status = json.load(resp).get("status", "")
    if status in ("done", "failed"):
        break
    time.sleep(1)
if status != "done":
    raise SystemExit(1)
' >/dev/null 2>&1; then
  mark 0 "ping job reaches done"
else
  mark 1 "ping job reaches done"
fi

# Database checks run inside the container so the password never reaches this script.
docker exec -i "$container" python - <<'PY'
import asyncio
import os
import re
import sys

import asyncpg

_NAME = re.compile(r"^[a-z][a-z0-9_]{0,60}$")
failed = False
conn = None
schema = ""


def line(ok: bool, text: str) -> None:
    global failed
    print(("PASS " if ok else "FAIL ") + text)
    if not ok:
        failed = True


async def denied(sql: str) -> bool:
    try:
        await conn.execute(sql)
    except asyncpg.PostgresError as exc:
        return getattr(exc, "sqlstate", "") == "42501"
    return False


async def main() -> None:
    global conn, schema
    url = os.environ.get("DATABASE_URL", "")
    agent = os.environ.get("AGENT_NAME", "")
    if not url or not _NAME.fullmatch(agent or ""):
        line(False, "database login")
        return
    schema = "agent_" + agent
    try:
        conn = await asyncpg.connect(url)
    except Exception:
        line(False, "database login")
        return
    me = await conn.fetchval("SELECT current_user")
    superuser = await conn.fetchval(
        "SELECT rolsuper FROM pg_roles WHERE rolname = current_user"
    )
    line(me == schema and superuser is False, "database role is " + schema + " and is not superuser")
    if not _NAME.fullmatch(schema):
        line(False, "schema name")
        return

    await conn.execute(f"DROP TABLE IF EXISTS {schema}._c6b_probe")
    await conn.execute(f"CREATE TABLE {schema}._c6b_probe (id int)")
    await conn.execute(f"INSERT INTO {schema}._c6b_probe (id) VALUES (1)")
    got = await conn.fetchval(f"SELECT id FROM {schema}._c6b_probe")
    line(got == 1, "can create and read in " + schema)
    await conn.execute(f"DROP TABLE {schema}._c6b_probe")
    line(True, "dropped probe table in " + schema)

    line(await denied("SELECT 1 FROM tank.ledger LIMIT 1"), "permission denied on tank.ledger")
    line(await denied("SELECT 1 FROM base.records LIMIT 1"), "permission denied on base.records")

    others = await conn.fetch(
        "SELECT nspname FROM pg_namespace WHERE nspname LIKE 'agent\\_%' AND nspname <> $1",
        schema,
    )
    other = ""
    for row in others:
        candidate = str(row["nspname"])
        if _NAME.fullmatch(candidate):
            other = candidate
            break
    if other:
        line(await denied(f"SELECT 1 FROM {other}.jobs LIMIT 1"), "permission denied on " + other)
    else:
        line(await denied("CREATE SCHEMA agent_other"), "permission denied creating another agent schema")


async def run() -> None:
    try:
        await main()
    except Exception:
        line(False, "database checks")
    finally:
        if conn is not None and _NAME.fullmatch(schema or ""):
            try:
                await conn.execute(f"DROP TABLE IF EXISTS {schema}._c6b_probe")
            except Exception:
                pass
            await conn.close()


asyncio.run(run())
raise SystemExit(1 if failed else 0)
PY
if [ "$?" -ne 0 ]; then
  failed=1
fi

if [ "$failed" -ne 0 ]; then
  exit 1
fi
exit 0
