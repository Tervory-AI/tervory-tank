#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -f /workspace/.tervory-setup/env.sh ]; then
  source /workspace/.tervory-setup/env.sh
fi
export PYTHONDONTWRITEBYTECODE=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export LANGSMITH_TRACING=false LANGCHAIN_TRACING_V2=false
exec python3 scripts/skala_dry_run.py "$@"
