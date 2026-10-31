# Deterministic site fonts — 2026-10-31 02:24 PDT / 09:24 UTC

PR #471 fixes the public site's repeated build failure shared by unrelated PRs.
It retains the already-working typography; no page text, design, font family,
weight, fallback face or metric changes are proposed.

## Exact failure and its limits

[Rig CI attempt 2, job 124497397087](https://github.com/Tervory-AI/tervory-tank/actions/runs/41187217375/attempts/2)
failed during `docker build --memory=1g -t tervory-rls-site:test site`.
`site/app/layout.tsx` requested Jost 300/400, Inter 400/500/600 and JetBrains
Mono 400 through the pinned Next 15.5.28 Google font loader.

The published `next-15.5.28.tgz` package's
`dist/compiled/@next/font/dist/google/loader.js:122` performs:

```js
const ext = /\.(woff|woff2|eot|ttf|otf)$/.exec(googleFontFileUrl)[1];
```

The captured stack fails exactly there with `Cannot read properties of null
(reading '1')`, after the font download and before emission. That establishes
the unchecked URL-extension assumption failing. The historical offending URL
was not logged, so its exact value and why Google's response differed remain
unverified. Current Google CSS fetched with the loader's Chrome 104 user agent
returned valid `.woff2` URLs. This is not evidence of a memory/OOM failure.

The offline RED build below establishes a second precise fact: the original
source requires an external Google Fonts response during compilation. Its
`EAI_AGAIN` is not claimed to reproduce the historical extension exception.

## Source and asset provenance

- `site/app/layout.tsx:2`: replaces the Google loader with local CSS.
- `site/app/layout.tsx:20`: retains the three Latin font preloads, font MIME type
  and anonymous cross-origin attribute.
- `site/app/fonts.css:1`: all 36 existing deployed font-face declarations,
  including unicode subsets, six family/weight combinations, display swap and
  the exact existing fallback metrics. The three CSS variables retain their
  existing family/fallback values.
- `site/public/fonts/manifest.json`: original face declarations and SHA-256 of
  every one of the 16 original WOFF2 files, plus source provenance.
- `site/public/fonts/OFL-*.txt`: existing repository SIL OFL 1.1 licenses for
  Jost, Inter and JetBrains Mono, copied unchanged from Workspace.
- `site/Dockerfile:7`: compilation runs with `--network=none`. Dependency
  installation remains the existing pinned-lockfile `npm ci` step.
- `tests/site_fonts/test_preserved_fonts.py`: font byte/declaration/license,
  weight, variable and preload regression checks.
- `tests/site_fonts/browser-parity.mjs`: offline disposable-browser comparison
  against the already-deployed working image, with exact screenshots, geometry,
  computed typography and multilingual glyph metrics.

Read-only source: container
`site-xnmc0jkz8j9i5jh1jwanbsfv-20261031T005559`, image
`sha256:a5e1a44a8161c65d74b1dfac8e7edceb2b53c93c8ec99f87e098890b960aaa0a`.
The copied `/app/out/_next/static/css/cd05e883114c7a07.css` SHA-256 is
`161581798b88599542bd64e8514f53286ef2d5525d54ec607c7e74a08ff5a80c`.
Only font asset URLs change from `/_next/static/media/` to `/fonts/`.
No font binaries were transformed. All subsets remain available, not only Latin.

## Commands and results

Work began on current main `d8277ded` with:

```sh
git fetch origin main
git worktree add -b codex/site-font-build-rootcause-20261031 /tmp/tervory-site-font-rootcause-20261031 origin/main
```

Both succeeded. A local `npm ci --ignore-scripts --no-audit --no-fund` hit the
host's write quota; its partial task-owned `site/node_modules` was removed.
Later `/tmp` Git index writes also hit quota, so a fresh isolated checkout of
the same remote branch was made under
`/home/ammosync/.codex/site-font-rootcause-20261031`. The pending layout edit
was retained. No failed push or history rewrite occurred. Every finished file
was committed and normally pushed.

1. RED, before changing the layout: a temporary Dockerfile installed the same
   locked dependencies, then executed `RUN --network=none npm run build`.
   `docker build --memory=1g --progress=plain -f /tmp/tervory-site-font-offline.Dockerfile -t tervory-site-font-offline:rootcause site`
   exited 1 trying to resolve `fonts.googleapis.com`.
   Full output: [offline-before.log](proof/offline-before.log).
2. GREEN: `docker build --memory=1g --progress=plain -t tervory-site-font-local:test site`
   exited 0, including the production Dockerfile's network-disabled compilation,
   type checks and static export. Full output:
   [offline-after.log](proof/offline-after.log). Image manifest:
   `sha256:584868e8a7aa68baffb4a22200b3f3b0cd4578458aab2b9dc26eafba713a8104`.
3. `python3 -m unittest discover -s tests/site_fonts -v`: four passed in 0.003s.
4. Disposable old/candidate images were started on loopback ports 18471/18472,
   with 256 MiB limits and no production mounts or credentials. Browser command:

   ```sh
   PLAYWRIGHT_MODULE=/tmp/command-workspace-tools/node_modules/playwright \
   CHROMIUM_PATH=/home/ammosync/.cache/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-linux64/chrome-headless-shell \
   FONT_PROOF_OUTPUT=/home/ammosync/.codex/site-font-rootcause-20261031/tests/site_fonts/proof \
   node tests/site_fonts/browser-parity.mjs
   ```

   Exit 0: 1440/375 screenshots byte-identical; all body geometry and computed
   typography equal; all six family/weight combinations have equal Latin,
   Greek and Cyrillic glyph metrics. All 16 font URLs return 200, `font/woff2`
   and the exact expected bytes. Cache-Control is absent in both old and new
   responses; `site/server.mjs` and its cache/CSP behavior are unchanged.
   [Machine-readable proof](proof/browser-parity.json).
5. `docker run --rm --network none --memory=1g --entrypoint node tervory-site-font-local:test -e ...`
   used an inline harness to start `server.mjs`, assert non-root UID and
   writable `/data`, then GET localhost homepage/font. Exit 0:
   `PASS uid 1000 offline homepage200, font200/font-woff2, /data writable`.
6. `git diff --check`: exit 0.

## Browser images

These are local disposable-browser checks, not founder acceptance screenshots.

| Width | Existing build | Candidate |
| --- | --- | --- |
| 1440 | [Before](proof/1440-before.png) | [After](proof/1440-after.png) |
| 375 | [Before](proof/375-before.png) | [After](proof/375-after.png) |

Independent exact-head review and final hosted CI remain required. Founder
alone merges; production deployment and founder walkthrough have not occurred.
No worker/ZA investigation, paid/model calls, secrets, production SQL, live
settings changes or production writes were performed.
