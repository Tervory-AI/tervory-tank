#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONDONTWRITEBYTECODE=1
rig_shared="$PWD"
if [[ -d "$PWD/vendor/tervory-tank/agents/_chassis" ]]; then
  rig_shared="$PWD/vendor/tervory-tank"
fi
export PYTHONPATH="$PWD/agents/rig:$rig_shared/agents/_chassis:$rig_shared/agents/_brain:$rig_shared${PYTHONPATH:+:$PYTHONPATH}"
exec "${RIG_PYTHON:-python3}" -m rigbox.dry_run "$@"
