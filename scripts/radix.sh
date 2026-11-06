#!/usr/bin/env bash
# Rehearse every Radix entry point with fake external I/O and local stores.
set -euo pipefail
if [ "$#" -ne 1 ] || [ "$1" != '--dry-run' ]; then
  echo 'Usage: scripts/radix.sh --dry-run' >&2
  exit 2
fi
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
export RADIX_DRY_RUN=1
echo 'Radix dry run: heartbeat, daily watch, weekly passive/infra, regulation events, code scans, business verification, active scans, legacy headers, and receipts.'
exec "$root/scripts/check.sh"
