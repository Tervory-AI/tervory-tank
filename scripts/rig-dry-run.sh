#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$PWD/agents/rig:$PWD/vendor/tervory-tank/agents/_chassis:$PWD/vendor/tervory-tank/agents/_brain:$PWD/vendor/tervory-tank${PYTHONPATH:+:$PYTHONPATH}"
exec "${RIG_PYTHON:-python3}" -m rigbox.dry_run "$@"
