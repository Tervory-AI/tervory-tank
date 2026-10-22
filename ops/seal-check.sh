#!/usr/bin/env bash
# SEAL-1 live check. Read-only: it runs only `docker ps`, `docker inspect` and
# `docker network inspect`, and changes nothing. Run it on the host after every
# deploy of Base, Tiger, Radix or Rig:
#   bash ops/seal-check.sh
#
# For every running container labelled coolify.applicationUuid, it lists the
# container's networks and their Internal flag. A container that joins an
# internal network must not also join a non-internal one, except the declared
# corridor services (matched by compose service name):
#   agent-base, base-brain and base-browser-gateway on tervory-gw-base;
#   tiger-browser-gateway on tervory-gw-tiger;
#   agent-rig, rig-brain and rig-browser-gateway on tervory-gw-rig;
#   egress-proxy on egress (compose names it <project>_egress).
#
# Rooms are found by labels, never by container name. Coolify's normal mode names
# containers <service>-<uuid>-<timestamp>; Raw Compose mode names them
# <uuid>-<service>-1 and sets no coolify.resourceName. So containers are grouped
# by the coolify.applicationUuid label, and a Coolify app is a room when its
# coolify.resourceName starts with "agent-" or, failing that, when one of its
# compose services (com.docker.compose.service) is named "agent-<room>". That
# name is the room's name. Other apps, such as the main Tank stack, are the hub
# every corridor connects to by design; they print "not a room, skipped".
#
# Prints one line per room: "<room> (<uuid>): sealed" or
# "<room> (<uuid>): LEAK: <container> on <network>" (several leaks are joined by "; ").
# A room with no container on an internal network prints "no sealed containers".
# The rooms that must be sealed (agent-base, agent-radix, agent-tiger) can never be skipped:
# if one is missing it prints "<room>: NOT FOUND", and if one has no container on
# an internal network it prints "<room> (<uuid>): NOT SEALED: no container on an
# internal network". Both fail.
# Exit 0 when every room is sealed, 1 on any leak, NOT FOUND or NOT SEALED,
# 2 when the check cannot run.
set -uo pipefail

DOCKER="${DOCKER:-docker}"

# Rooms whose compose files declare sealed services; each must be found and sealed.
EXPECTED_SEALED=(agent-base agent-radix agent-tiger agent-rig)

# service name -> the one non-internal network it may also join
declare -A CORRIDOR=(
  [agent-base]="tervory-gw-base"
  [base-brain]="tervory-gw-base"
  [base-browser-gateway]="tervory-gw-base"
  [tiger-browser-gateway]="tervory-gw-tiger"
  [agent-rig]="tervory-gw-rig"
  [rig-brain]="tervory-gw-rig"
  [rig-browser-gateway]="tervory-gw-rig"
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

declare -A INTERNAL=()     # network -> true|false
declare -A APP_RESOURCE=() # uuid -> coolify.resourceName (empty in raw mode)
declare -A APP_ROOM=()     # uuid -> agent-* compose service name, if any
declare -A APP_LEAKS=()    # uuid -> leak text
declare -A APP_SEALED=()   # uuid -> number of containers on an internal network
APPS=()
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
  if [[ -z "$uuid" ]]; then
    echo "seal-check: container $id has an empty coolify.applicationUuid label" >&2
    exit 2
  fi
  if [[ -z "${APP_SEALED[$uuid]+set}" ]]; then
    APPS+=("$uuid")
    APP_RESOURCE[$uuid]=""
    APP_ROOM[$uuid]=""
    APP_LEAKS[$uuid]=""
    APP_SEALED[$uuid]=0
  fi
  [[ -n "$resource" ]] && APP_RESOURCE[$uuid]="$resource"
  if [[ "$service" == agent-* && -z "${APP_ROOM[$uuid]}" ]]; then
    APP_ROOM[$uuid]="$service"
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
  # Rig's public API has only its corridor; only its sandbox and browser are
  # sealed. Check every Rig service, even if a sealed network was removed.
  expected_nets=""
  case "$service" in
    agent-rig) expected_nets="tervory-gw-rig" ;;
    rig-brain) expected_nets="tervory-gw-rig ${project}_sandbox" ;;
    rig-sandbox) expected_nets="${project}_sandbox" ;;
    rig-browser) expected_nets="${project}_browser" ;;
    rig-browser-gateway) expected_nets="tervory-gw-rig ${project}_browser" ;;
  esac
  if [[ -n "$expected_nets" ]]; then
    for net in $networks; do
      if [[ " $expected_nets " != *" $net "* ]]; then
        APP_LEAKS[$uuid]="${APP_LEAKS[$uuid]:+${APP_LEAKS[$uuid]}; }LEAK: $name on $net"
      fi
    done
    for net in $expected_nets; do
      if [[ " $networks " != *" $net "* ]]; then
        APP_LEAKS[$uuid]="${APP_LEAKS[$uuid]:+${APP_LEAKS[$uuid]}; }NOT SEALED: $name missing $net"
      elif [[ "$net" != "tervory-gw-rig" ]]; then
        internal_flag "$net"
        if [[ "$FLAG" != "true" ]]; then
          APP_LEAKS[$uuid]="${APP_LEAKS[$uuid]:+${APP_LEAKS[$uuid]}; }NOT SEALED: $name on non-internal $net"
        fi
      fi
    done
    # Rig's exact-network check above already accounts for each attachment.
    if (( on_internal )); then
      APP_SEALED[$uuid]=$(( APP_SEALED[$uuid] + 1 ))
    fi
    continue
  fi
  (( on_internal )) || continue
  APP_SEALED[$uuid]=$(( APP_SEALED[$uuid] + 1 ))
  allowed="${CORRIDOR[$service]:-}"
  for net in "${outward[@]}"; do
    if [[ -n "$allowed" && ( "$net" == "$allowed" || "$net" == "${project}_${allowed}" ) ]]; then
      continue
    fi
    leak="LEAK: $name on $net"
    APP_LEAKS[$uuid]="${APP_LEAKS[$uuid]:+${APP_LEAKS[$uuid]}; }$leak"
  done
done

# The room name comes from the app: its Coolify resource name when that is an
# agent-* name, otherwise its agent-* compose service.
declare -A ROOM_NAME=()  # uuid -> room name
declare -A FOUND=()      # room name -> 1
ROOMS=()
status=0
for uuid in "${APPS[@]}"; do
  resource="${APP_RESOURCE[$uuid]}"
  if [[ "$resource" == agent-* ]]; then
    room="$resource"
  else
    room="${APP_ROOM[$uuid]}"
  fi
  if [[ -z "$room" ]]; then
    echo "${resource:-$uuid} ($uuid): not a room, skipped"
    continue
  fi
  ROOM_NAME[$uuid]="$room"
  FOUND[$room]=1
  ROOMS+=("$uuid")
done

is_expected() {
  local want
  for want in "${EXPECTED_SEALED[@]}"; do
    [[ "$want" == "$1" ]] && return 0
  done
  return 1
}

for uuid in "${ROOMS[@]}"; do
  room="${ROOM_NAME[$uuid]}"
  if [[ -n "${APP_LEAKS[$uuid]}" ]]; then
    echo "$room ($uuid): ${APP_LEAKS[$uuid]}"
    status=1
  elif (( APP_SEALED[$uuid] > 0 )); then
    echo "$room ($uuid): sealed"
  elif is_expected "$room"; then
    echo "$room ($uuid): NOT SEALED: no container on an internal network"
    status=1
  else
    echo "$room ($uuid): no sealed containers"
  fi
done
for room in "${EXPECTED_SEALED[@]}"; do
  if [[ -z "${FOUND[$room]+set}" ]]; then
    echo "$room: NOT FOUND"
    status=1
  fi
done
exit "$status"
