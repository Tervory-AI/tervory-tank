#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
root=$PWD
if [[ -x /workspace/.tervory-env/venv/bin/python3 ]]; then
  export PATH="/workspace/.tervory-env/venv/bin:$PATH"
fi
export PYTHONPATH="$root:$root/tests:$root/agents/base:$root/agents/_chassis:$root/tank:$root/vendor/tervory-tank:$root/vendor/tervory-tank/tank:$root/vendor/tervory-tank/agents/_chassis${PYTHONPATH:+:$PYTHONPATH}"
exec python3 agents/base/training_day.py "$@"
