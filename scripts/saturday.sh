#!/usr/bin/env bash
set -euo pipefail
if [ "$#" != 1 ] || [ "$1" != --dry-run ]; then
  echo 'Use --dry-run. This command never launches paid work or training.' >&2
  exit 2
fi
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
node tests/gate4.cjs
echo 'Workspace owns no scheduled backend jobs or training commands. Its client read paths were run with empty offline responses; no work was submitted.'
