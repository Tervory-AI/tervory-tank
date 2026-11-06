#!/usr/bin/env bash
set -euo pipefail
if [ "$#" != 1 ] || [ "$1" != --dry-run ]; then
  echo 'Use --dry-run. This command never launches paid work or training.' >&2
  exit 2
fi
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
node tests/gate3_data.cjs
node tests/gate4.cjs
NODE_OPTIONS="${NODE_OPTIONS:-} --preserve-symlinks --preserve-symlinks-main" node --experimental-strip-types --import ./tests/base_page_register.mjs --test tests/w2/billing.test.ts
echo 'Workspace owns no scheduled backend jobs or training commands. Nonempty and empty client data, receipts, billing and recovery were proven offline; no work was submitted to a live service.'
