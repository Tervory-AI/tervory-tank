#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
market_shared="$PWD"
if [[ -d "$PWD/vendor/tervory-tank/agents/_chassis" ]]; then
  market_shared="$PWD/vendor/tervory-tank"
fi
export PYTHONPATH="$PWD/agents/market_lab:$market_shared/tank:$market_shared/agents/_chassis:$market_shared${PYTHONPATH:+:$PYTHONPATH}"
exec "${TANK_PYTHON:-/workspace/.tervory-setup/venv/bin/python}" agents/market_lab/run.py "$@"
