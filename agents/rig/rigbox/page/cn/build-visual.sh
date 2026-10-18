#!/bin/sh
# Rebuild visual.js without whitespace minification.
# Versions are pinned in package.json. node_modules stays out of git.
set -eu
HERE=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
WORK=$(mktemp -d)
cp "$HERE/package.json" "$WORK/package.json"
cp "$HERE/visual.jsx" "$WORK/visual.jsx"
(
  cd "$WORK"
  npm install --ignore-scripts --no-audit --no-fund
  ./node_modules/.bin/esbuild visual.jsx \
    --bundle \
    --format=iife \
    --outfile="$HERE/visual.js" \
    --jsx=automatic \
    --banner:js="/* Built from visual.jsx. React Flow is MIT. */"
)
python3 - "$HERE/visual.js" <<'PY'
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
pattern = re.compile(
    r"(?ix)(?:^|[^A-Za-z0-9])(?:api[_-]?key|secret[_-]?key|client[_-]?secret|password|passwd|access[_-]?token|auth[_-]?token)\s*[:=]\s*['\"]?(?P<val>[^\s'\"\#]{12,})"
)
bad = [f"{n}: {line[:80]}" for n, line in enumerate(text.splitlines(), 1) if pattern.search(line)]
if bad:
    raise SystemExit("secret scan would flag visual.js:\n" + "\n".join(bad[:10]))
print("visual.js lines", text.count("\n") + 1, "bytes", len(text.encode()))
PY
