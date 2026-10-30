#!/usr/bin/env bash
# Reproduce the retailer UMD from its upstream source plus the reviewed copy patch.
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
build_dir=$(mktemp -d)
trap 'rm -rf -- "$build_dir"' EXIT
git init "$build_dir/source"
cd "$build_dir/source"
git fetch --depth 1 https://github.com/Tervory-AI/tervory-rig.git f382f8da90944a3176c1bd43cfc77f14e78c6a0f
git checkout --detach FETCH_HEAD
git apply --unidiff-zero "$root/widget-source.patch"
npm ci --no-audit --no-fund
npm run build
npx vitest run
node scripts/package-widget.mjs "$root/widget"

npm ci --prefix widget/src/three --no-audit --no-fund
node widget/src/three/build.mjs --site-only
three_widget=$(cd -- "$root/../three_d/widget" && pwd)
node widget/src/three/package-widget.mjs "$three_widget"
