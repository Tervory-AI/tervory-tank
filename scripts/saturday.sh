#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ $# != 1 || $1 != --dry-run ]]; then
  printf '%s\n' 'Usage: scripts/saturday.sh --dry-run' >&2
  exit 2
fi
# Reuse the complete offline suite: every handler, real source adapter,
# schedule and receipt, with disposable PostgreSQL and fake provider responses.
printf '%s\n' 'Tisan Saturday dry run: local data and fake services; no launch.'
exec scripts/check.sh
