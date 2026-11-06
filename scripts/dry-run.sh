#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
dry_python="${PYTHON:-python3}"
if [ -x .venv/bin/python ]; then dry_python=.venv/bin/python; fi
exec "$dry_python" scripts/dry_run.py "$@"
