#!/usr/bin/env bash
# SEAL-1 live check. Read-only: it runs only `docker ps`, `docker inspect` and
# `docker network inspect`, and changes nothing. Run it on the host after every
# deploy of Base or Radix:
#   bash ops/seal-check.sh
#
# For every running container labelled coolify.applicationUuid, it lists the
# container's networks and their Internal flag. A container that joins an
# internal network must not also join a non-internal one, except the declared
# corridor services:
#   agent-base, base-brain and base-browser-gateway on tervory-gw-base;
#   egress-proxy on egress (compose names it <project>_egress).
#
# Prints one line per room (Coolify app): "<room> (<uuid>): sealed" or
# "<room> (<uuid>): LEAK: <container> on <network>" (several leaks are joined by "; ").
# An app with no container on an internal network prints "no sealed containers".
#
# Rooms are the Coolify apps whose resource name starts with "agent-" (one per
# agents/<room>/docker-compose.yml). Other apps, such as the main Tank stack, are
# the hub every corridor connects to by design; they print "not a room, skipped".
# Exit 0 when every room is sealed, 1 on any leak, 2 when the check cannot run.
set -uo pipefail

DOCKER="${DOCKER:-docker}"

# service name -> the one non-internal network it may also join
declare -A CORRIDOR=(
  [agent-base]="tervory-gw-base"
  [base-brain]="tervory-gw-base"
  [base-browser-gateway]="tervory-gw-base"
  [egress-proxy]="egress"
)

if ! ids="$("$DOCKER" ps -q --filter label=coolify.applicationUuid 2>&1)"; then
  echo "seal-check: docker ps failed: $ids" >&2
  exit 2
fi
if [[ -z "$ids" ]]; then
  echo "seal-check: no running Coolify containers found; nothing was checked." >&2
  exit 2
fi

declare -A INTERNAL=()   # network -> true|false
declare -A ROOM_NAME=()  # uuid -> resource name
declare -A ROOM_LEAKS=() # uuid -> leak text
declare -A ROOM_SEALED=() # uuid -> number of containers on an internal network
declare -A SKIPPED=()   # uuid -> resource name of a non-room app
ROOMS=()
SKIP_ORDER=()
FORMAT='{{index .Config.Labels "coolify.applicationUuid"}}|{{index .Config.Labels "coolify.resourceName"}}|{{index .Config.Labels "com.docker.compose.service"}}|{{index .Config.Labels "com.docker.compose.project"}}|{{.Name}}|{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}'

FLAG=""
internal_flag() {  # sets FLAG; no subshell, so the cache and exit 2 both hold
  local net="$1" out
  if [[ -z "${INTERNAL[$net]+set}" ]]; then
    if ! out="$("$DOCKER" network inspect -f '{{.Internal}}' "$net" 2>&1)"; then
      echo "seal-check: docker network inspect $net failed: $out" >&2
      exit 2
    fi
    INTERNAL[$net]="$out"
  fi
  FLAG="${INTERNAL[$net]}"
}

for id in $ids; do
  if ! line="$("$DOCKER" inspect -f "$FORMAT" "$id" 2>&1)"; then
    echo "seal-check: docker inspect $id failed: $line" >&2
    exit 2
  fi
  IFS='|' read -r uuid resource service project name networks <<<"$line"
  name="${name#/}"
  if [[ "${resource:-}" != agent-* ]]; then
    if [[ -z "${SKIPPED[$uuid]+set}" ]]; then
      SKIPPED[$uuid]="${resource:-$uuid}"
      SKIP_ORDER+=("$uuid")
    fi
    continue
  fi
  if [[ -z "${ROOM_NAME[$uuid]+set}" ]]; then
    ROOMS+=("$uuid")
    ROOM_NAME[$uuid]="${resource:-$uuid}"
    ROOM_LEAKS[$uuid]=""
    ROOM_SEALED[$uuid]=0
  fi
  on_internal=0
  outward=()
  for net in $networks; do
    internal_flag "$net"
    if [[ "$FLAG" == "true" ]]; then
      on_internal=1
    else
      outward+=("$net")
    fi
  done
  (( on_internal )) || continue
  ROOM_SEALED[$uuid]=$(( ROOM_SEALED[$uuid] + 1 ))
  allowed="${CORRIDOR[$service]:-}"
  for net in "${outward[@]}"; do
    if [[ -n "$allowed" && ( "$net" == "$allowed" || "$net" == "${project}_${allowed}" ) ]]; then
      continue
    fi
    leak="LEAK: $name on $net"
    ROOM_LEAKS[$uuid]="${ROOM_LEAKS[$uuid]:+${ROOM_LEAKS[$uuid]}; }$leak"
  done
done

status=0
for uuid in "${SKIP_ORDER[@]}"; do
  echo "${SKIPPED[$uuid]} ($uuid): not a room, skipped"
done
if (( ${#ROOMS[@]} == 0 )); then
  echo "seal-check: no room containers (resource name agent-*) found; nothing was checked." >&2
  exit 2
fi
for uuid in "${ROOMS[@]}"; do
  if [[ -n "${ROOM_LEAKS[$uuid]}" ]]; then
    echo "${ROOM_NAME[$uuid]} ($uuid): ${ROOM_LEAKS[$uuid]}"
    status=1
  elif (( ROOM_SEALED[$uuid] > 0 )); then
    echo "${ROOM_NAME[$uuid]} ($uuid): sealed"
  else
    echo "${ROOM_NAME[$uuid]} ($uuid): no sealed containers"
  fi
done
exit "$status"
