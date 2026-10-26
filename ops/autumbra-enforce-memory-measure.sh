#!/usr/bin/env bash
# Measure Autumbra Enforce RSS on dogfood so the container mem_limit / host cap
# is a number, not a guess. Run on Coolify TEST host only — never live Boston.
#
# Usage:
#   bash ops/autumbra-enforce-memory-measure.sh <enforce-container-name>
#
# Prints Peak RSS (MiB) and a suggested mem_limit headroom (+50%).
set -euo pipefail

container="${1:?usage: bash ops/autumbra-enforce-memory-measure.sh <enforce-container>}"

if ! docker inspect "$container" >/dev/null 2>&1; then
  echo "BLOCKER: container $container not on this docker host" >&2
  exit 2
fi

# Sample docker stats once (and peak from cgroup if present).
stats_line=$(docker stats --no-stream --format '{{.MemUsage}}' "$container")
echo "docker_stats_mem_usage=$stats_line"

cgroup_peak=""
if docker exec "$container" sh -c 'test -r /sys/fs/cgroup/memory.peak' 2>/dev/null; then
  cgroup_peak=$(docker exec "$container" cat /sys/fs/cgroup/memory.peak)
  peak_mib=$(awk -v b="$cgroup_peak" 'BEGIN { printf "%.1f", b/1024/1024 }')
  suggest=$(awk -v b="$cgroup_peak" 'BEGIN { printf "%.0f", (b*1.5)/1024/1024 }')
  echo "cgroup_memory_peak_bytes=$cgroup_peak"
  echo "cgroup_memory_peak_mib=$peak_mib"
  echo "suggested_mem_limit_mib=${suggest} (peak * 1.5)"
  echo "NOTE: paste this into PR #337 and set compose mem_limit + host container cap from the number."
else
  echo "cgroup_memory.peak unavailable inside container; use docker stats above as soft signal"
  echo "suggested_mem_limit_mib=HOLD — re-run after dogfood load with cgroup v2 peak"
fi
