# PR #334 numerical claims recheck

Observed on 26–27 October 2026 UTC in fresh clones from GitHub. The tested source and test revision is `fe62268ca6c4f53f0213b213ce26f77d8474e194`. This correction changes documentation and evidence only. It does not change runtime code, tests, seed data or approvals.

The regression baseline is **16 failed, 3 passed**. The previous **12 failed, 3 passed** referred to an intermediate working-copy test file, not the committed 19-case file, and is withdrawn as a reproducible claim. Other earlier aggregate totals are superseded by the runs below, using fixed test selections at the committed revision. Overlapping groups must not be added together.

## Baseline reproduction

Use Python 3.12 with the repository's test dependencies and a disposable PostgreSQL server whose user can create databases. The tests create and drop isolated databases; do not point these variables at production. The run used PostgreSQL 16.15, Python 3.12.14, pytest 9.0.3 and asyncpg 0.30.0. Remaining package and browser versions are recorded in [the machine-readable record](proof/tank-one-door-claims.json).

```sh
export POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/pooltest
export ZENAS_SCHEMA_DATABASE_URL="$POOL_SCHEMA_DATABASE_URL"
export TRAINING_SCHEMA_DATABASE_URL="$POOL_SCHEMA_DATABASE_URL"
export PYTHONPATH=tank LANGSMITH_TRACING=false LANGCHAIN_TRACING_V2=false
export READ1_CHROMIUM_EXECUTABLE=/usr/bin/chromium
unset TANK_URL

git clone --branch codex/tank-one-door --single-branch \
  https://github.com/zenascapetown-code/tervory-tank.git /tmp/tank-review-baseline
cd /tmp/tank-review-baseline
git checkout --detach 90a2a77dcd300a085d38db230f3829e1170a11e1
git show fe62268ca6c4f53f0213b213ce26f77d8474e194:tests/test_tank_review_regressions.py \
  > tests/test_tank_review_regressions.py
sha256sum tests/test_tank_review_regressions.py
python -m pytest -q -p no:cacheprovider --tb=short --disable-warnings \
  tests/test_tank_review_regressions.py
```

Only that committed regression file was added to the baseline clone. No Tank code or other fixture was copied from the working tree. Its SHA-256 is `cc4b2d7411afaf83683fc46dc498c0de44cc51fa3d17306b688f2a4ea5fcaaaf`.

Observed output (exit 1):

```text
16 failed, 3 passed, 5 warnings in 15.44s
```

Part A was checked separately in a fresh clone of audited main `65067a43a0d27d54b48633bf6db4f3fc211ec05f`, adding only `tests/test_tank_tenant_boundaries.py` from `fe62268` and running that file with the same pytest options. Its SHA-256 is `9e79f64c894b67b210bf82b641f4cab9ac83492f2939f36bb161d7ec8567f8f7`.

```text
5 failed, 1 passed, 5 warnings in 4.25s
```

This reproduces the audit's total 3 instead of 1, foreign package visibility, foreign Workspace/Ghost execution returning 200 instead of 403, and five client-derived global screening cases. The pre-existing Base ownership check passes. The separate original two-row ASGI probe was also rerun against this clone: both tenant queries returned `cases=2, accepted=1, rejected=1`, and tenant A's catalogue included tenant B's private package. Its transaction was rolled back.

## Current committed test selections

The record contains each selection's `argv`, source commit, exit code and verbatim pytest summary. To repeat a group, save the record outside the checkout, clone the branch afresh, detach at `fe62268`, and run the recorded selection with the environment above. For example, with `CHECK_RECORD` pointing to that saved JSON:

```sh
python - "$CHECK_RECORD" review <<'PY'
import json, subprocess, sys
record = json.load(open(sys.argv[1]))
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip() == record['code_and_tests_commit']
run = next(row for row in record['results'] if row['id'] == sys.argv[2])
raise SystemExit(subprocess.call([sys.executable, *run['argv'][1:]]))
PY
```

The full run also requires the repository's Node/browser dependencies, PostgreSQL schema-test prerequisites and local tools. These clones reused an untracked `workspace/node_modules` dependency symlink to the installed repository dependencies. Chromium was installed locally; Blender was available, `gltf-transform` was absent. This is an observed environment result, not a guarantee of identical skips or warnings on a differently provisioned machine. Test pass/fail counts below are independent of elapsed time; durations are retained only as raw output.

| Selection ID | Observed pytest summary | Exit |
| --- | --- | --- |
| `review` | 73 passed, 5 warnings in 53.04s | 0 |
| `related` | 326 passed, 16 warnings in 66.45s (0:01:06) | 0 |
| `learning` | 31 passed, 5 warnings in 29.57s | 0 |
| `guard_dogfood` | 30 passed, 1 skipped, 1 warning in 12.31s | 0 |
| `base_wiring` | 77 passed, 1 skipped, 18 warnings in 235.10s (0:03:55) | 0 |
| `agent_worker` | 405 passed, 16 warnings in 13.78s | 0 |
| `part_a` | 92 passed, 5 warnings in 42.81s | 0 |
| `part_b` | 217 passed, 5 warnings in 93.63s (0:01:33) | 0 |
| `expanded` | 178 passed, 16 warnings in 70.22s (0:01:10) | 0 |
| `retry` | 124 passed, 5 warnings in 47.58s | 0 |
| `research` | 47 passed, 5 warnings in 1.94s | 0 |
| `batch` | 11 passed, 5 warnings in 12.09s | 0 |
| `graduation` | 1 passed, 5 warnings in 1.89s | 0 |
| `baseline_review` | 16 failed, 3 passed, 5 warnings in 15.44s | 1 |
| `main_boundaries` | 5 failed, 1 passed, 5 warnings in 4.25s | 1 |
| `full` | 4 failed, 3367 passed, 15 skipped, 53 warnings, 437 subtests passed in 755.99s (0:12:35) | 1 |
| `main_known_failures` | 4 failed, 1 passed, 4 deselected, 1 warning in 22.02s | 1 |
| `guard_current_313` | 27 passed in 18.77s | 0 |
| `guard_plant` | 1 failed in 19.04s | 1 |
| `guard_current_312` | 27 passed in 19.04s | 0 |

The earlier Part B / expanded / retry totals of 214 / 176 / 123 are replaced by **217 / 178 / 124** for these committed selections. The earlier guard+dogfood total of 28 passed, 1 skipped (25 guard cases) is replaced by **30 passed, 1 skipped (27 guard cases)**. The older broad-run total of 3345 passes and five failures is superseded by this fresh run: **3367 passed, 15 skipped, 437 subtests passed, 4 failed**. The migration assertion now passes, including its complete **47-pass** suite.

All four full-run failures reproduce on audited main with the `main_known_failures` selection above: Rig catalogue dates (`2026-03-01` expected, `2026-10-18` observed), shell fixture page loading, and both Forge samples at `dedup` with no local `gltf-transform`. That selection also has one passing control and four deselected cases. There were no collection errors in the full run.


## Guard, source quantities and fixture record

A separate fresh clone at `fe62268` ran the one-door file unchanged on Python 3.12.14 and Python 3.13.5: **27 passed** on each. An untracked `agents/ghost/_one_door_probe.py` containing `import openai` at line 1 and `client.chat.completions.create(...)` at line 4 made the selected `test_no_new_tank_bypass` fail:

```text
agents/ghost/_one_door_probe.py:1: provider import [8ce9e2c61044b12d]
agents/ghost/_one_door_probe.py:4: model invocation [20d720b3eeb87fca]
1 failed in 19.04s
```

The probe was never executed. It was removed in a `finally` block; the full guard then reported `27 passed in 19.04s`, and `git status --short` was empty. The registry has **64 identities covering 113 occurrences**. CI scope selects the guard for **seven** room lanes: Base, Market Lab, Radix, Rig, Tiger, Tisan and Zenas.

A fresh schema applied twice to an isolated database produced **13 platform policies**: four Base rows and nine Zenas rows, matching the audit's table. With no approved packages, Base rows remain rung 3 decisions with Luna fallback; Zenas rows start at rung 1/Astra with semantic and matter matching enabled. Reapplication left those rows unchanged. The regression suite separately exercises approved, candidate, missing and retired pins, tenant overrides and the one-time repair.

Source inspection and executed tests agree on these other quantities in the audit and PR:

| Claim | Check at `fe62268` |
| --- | --- |
| Three Base versions required for code | `base.normalize@1.0.0`, `base.extract@2.0.0`, `base.business_data@2.0.0`; conditional seed and repair regression tests |
| Base confidence floors | 0.80 for normalize/extract/planner, 0.40 for business_data; queried seed rows |
| Cache lifetime / similarity | 604800 seconds (seven days), threshold 0.97; `main.CACHE_TTL_S`, `graduate.SEMANTIC_THRESHOLD`, cache tests |
| Client acceptance / collection | 86400-second default; collector sleeps 300 seconds (five minutes); rejection adds 0.1 with cap 1; training and tenant-isolation tests |
| Batch defaults | `TANK_BATCH_MIN=50`; 24-hour completion window; standard cost × 0.5; at most one normal retry; $1 default cap; six decimal ledger precision; batch tests and schema |
| Ghost / Context.dev limits | Ghost output cap 200 tokens; unchanged Context.dev `BRAND_CREDITS=10`; source inspection and Ghost guard test |
| Browser source graph | 52 client roots, zero value-import paths to key-reading modules; the AST script below was rerun on the fresh clone |
| First fixture graduation | Replay: 30 samples across two tenants, agreement 1.0, threshold 0.97, automatic promotion, rung 3; $0.001 before, $0 after, $0.030 fixture total and $0 external spend |

The replay's `FIRST_GRADUATION` output is retained in the JSON record. The original patent record's **2026-10-26 15:10:53 UTC** timestamp identifies its first run, not this later replay; it agrees with the retained first-run output. Production approval state and live provider batch pricing were not queried. The local fixture costs are not customer savings.

The browser check excludes type-only imports and stops at server actions. It is a source import-graph check, not deployed-bundle inspection. Run this script with the fresh clone's absolute path as its argument and installed TypeScript under `workspace/node_modules`:

```javascript
const fs=require('node:fs'), path=require('node:path'), cp=require('node:child_process');
const root=path.resolve(process.argv[2], 'workspace');
const ts=require(path.join(root,'node_modules/typescript'));
const files=cp.execFileSync('git',['ls-files','-z','workspace'],{cwd:path.dirname(root)}).toString().split('\0').filter(x=>/\.(tsx?|jsx?|mjs)$/.test(x)).map(x=>path.join(path.dirname(root),x));
const graph=new Map(), clients=[], secretModules=[];
function resolve(p,from){const base=p.startsWith('@/')?path.join(root,p.slice(2)):p.startsWith('.')?path.resolve(path.dirname(from),p):null;return base&&[base,...['.ts','.tsx','.js','.jsx','/index.ts','/index.tsx'].map(x=>base+x)].find(x=>fs.existsSync(x)&&fs.statSync(x).isFile());}
for(const f of files){const text=fs.readFileSync(f,'utf8'), source=ts.createSourceFile(f,text,ts.ScriptTarget.Latest,true);const directive=source.statements.find(s=>ts.isExpressionStatement(s)&&ts.isStringLiteral(s.expression))?.expression.text;
if(directive==='use client') clients.push(f);
if(/process\.env(?:\.(?:TANK_API_KEY\w*)|\[["']TANK_API_KEY\w*["']\])/.test(text)) secretModules.push(f);
const edges=[];if(directive!=='use server')for(const s of source.statements){if(ts.isImportDeclaration(s)&&s.importClause?.isTypeOnly)continue;if(ts.isImportDeclaration(s)&&s.importClause?.namedBindings&&ts.isNamedImports(s.importClause.namedBindings)&&!s.importClause.name&&s.importClause.namedBindings.elements.every(e=>e.isTypeOnly))continue;if((ts.isImportDeclaration(s)||ts.isExportDeclaration(s))&&s.moduleSpecifier&&ts.isStringLiteral(s.moduleSpecifier)&&!s.isTypeOnly){const r=resolve(s.moduleSpecifier.text,f);if(r)edges.push(r);}}
graph.set(f,edges);}
const leaks=[];for(const client of clients){const queue=[[client]], seen=new Set();while(queue.length){const chain=queue.shift(),file=chain.at(-1);if(seen.has(file))continue;seen.add(file);if(secretModules.includes(file))leaks.push(chain.map(f=>path.relative(root,f)));for(const edge of graph.get(file)||[])queue.push([...chain,edge]);}}
console.log(JSON.stringify({client_roots:clients.length,key_modules:secretModules.map(f=>path.relative(root,f)),client_import_paths_to_keys:leaks},null,2));if(leaks.length)process.exitCode=1;
```

Ruff passed for `tank tests --select E9,F --per-file-ignores 'tank/skills/base.socials/1.0.0/run.py:F401'` and for `agents/base/base_brain.py agents/base/room.py agents/ghost/dogfood_hf.py tests/test_tank_one_door.py --select E9,F`. The exception is the existing unused import in an approved skill, whose source is unchanged. `git diff --check` passed for the documentation correction.

## CI scope

GitHub check runs were queried for **`fe62268`**, separately from these local results. Workspace, savings-page and forge-image succeeded. Tank failed; its test annotations name `tests/test_shell_nav.py:23` and `tests/test_rig_postgres.py:92`. Tisan's gate failed at `Run npx playwright install --with-deps chromium`. Job URLs and statuses are retained in the JSON record. These are statuses of the tested implementation commit, not a prediction of the documentation commit's CI. No green full-suite, deployment or production validation is claimed.
