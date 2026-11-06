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
export PYTHONPATH="$PWD:$PWD/tank:$PWD/agents/_chassis:${PYTHONPATH:-}"
exec python3 - "$@" <<'PYTEST'
from pathlib import Path
import pytest
files = sorted(str(p) for p in Path('tests').rglob('test_*.py')
               if p.name.startswith('test_tisan') or p.parts[1].startswith('tisan'))
raise SystemExit(pytest.main(['-q', '--disable-socket', '--allow-unix-socket',
    '--allow-hosts=127.0.0.1,localhost,::1', *files]))
PYTEST
