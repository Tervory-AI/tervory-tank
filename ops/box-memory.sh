#!/usr/bin/env bash
# Read-only Boston capacity report. Record the measurement date with its output.
# Usage: bash ops/box-memory.sh
# Only free and formatted Docker stats/inspect are called; no environment values.
set -euo pipefail

memory=$(free -b)
memory_found=false
while read -r kind total used unused shared cache available; do
  if [[ "$kind" != 'Mem:' ]]; then
    continue
  fi
  for value in "$total" "$used" "$available"; do
    case "$value" in
      ''|*[!0-9]*) printf 'ERROR: free -b returned invalid memory bytes\n' >&2; exit 2 ;;
    esac
  done
  printf 'host_memory_total_bytes=%s\n' "$total"
  printf 'host_memory_used_bytes=%s\n' "$used"
  printf 'host_memory_available_bytes=%s\n' "$available"
  memory_found=true
done <<< "$memory"
if [[ "$memory_found" != true ]]; then
  printf 'ERROR: free -b returned no Mem row\n' >&2
  exit 2
fi

# --all also enumerates stopped containers, so the total includes every mem_limit.
# Only running containers have their current use printed below.
stats=$(docker stats --all --no-stream --format '{{.ID}} {{.Name}} {{.MemUsage}}')
limits=0
running_limits=0
containers=0
running_containers=0
unlimited=0
while read -r container_id container_name usage; do
  [[ -n "$container_id" ]] || continue
  inspected=$(docker inspect --format '{{.State.Running}} {{.HostConfig.Memory}}' "$container_id")
  read -r running limit <<< "$inspected"
  case "$running:$limit" in
    true:*|false:*) ;;
    *) printf 'ERROR: docker inspect returned no running state\n' >&2; exit 2 ;;
  esac
  case "$limit" in
    ''|*[!0-9]*) printf 'ERROR: docker inspect returned invalid memory bytes\n' >&2; exit 2 ;;
  esac
  limits=$((limits + limit))
  containers=$((containers + 1))
  if [[ "$limit" == 0 ]]; then
    unlimited=$((unlimited + 1))
  fi
  if [[ "$running" == true ]]; then
    running_limits=$((running_limits + limit))
    running_containers=$((running_containers + 1))
    printf 'running_container=%s memory_usage=%s mem_limit_bytes=%s\n' "$container_name" "$usage" "$limit"
  fi
done <<< "$stats"

printf 'container_count=%s\n' "$containers"
printf 'running_container_count=%s\n' "$running_containers"
printf 'container_mem_limit_sum_bytes=%s\n' "$limits"
printf 'running_container_mem_limit_sum_bytes=%s\n' "$running_limits"
# A zero Docker limit is unlimited, not evidence that the container needs no RAM.
printf 'unlimited_container_count=%s\n' "$unlimited"
