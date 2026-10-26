#!/usr/bin/env bash
# Isolation network test FROM INSIDE a fixture client's Enforce container.
# Coolify TEST host only — never live Boston.
#
# Usage:
#   bash ops/autumbra-enforce-isolation-check.sh <enforce-container-name>
#
# Expected stdout (pass):
#   network=<name> internal=true
#   JSON from ghost.enforce_isolation_probe (probe + report; report.ok=true)
# Exit 1 if no internal:true network. Exit 2 if container missing.
set -euo pipefail

container="${1:?usage: bash ops/autumbra-enforce-isolation-check.sh <enforce-container>}"

if ! docker inspect "$container" >/dev/null 2>&1; then
  echo "BLOCKER: container $container not on this docker host" >&2
  exit 2
fi

# Ensure internal network flag on the attached network(s).
internal_ok=0
for net in $(docker inspect -f '{{range $n,$v := .NetworkSettings.Networks}}{{$n}} {{end}}' "$container"); do
  internal=$(docker network inspect -f '{{.Internal}}' "$net" 2>/dev/null || echo false)
  echo "network=$net internal=$internal"
  if [ "$internal" = "true" ]; then
    internal_ok=1
  fi
done
if [ "$internal_ok" -ne 1 ]; then
  echo "FAIL: no internal:true network attached"
  exit 1
fi

# Inside the Enforce image the package is imported as `ghost.*` (see compose CMD).
docker exec -e PYTHONPATH=/app -e AUTUMBRA_ROLE=enforce "$container" \
  python -m ghost.enforce_isolation_probe
