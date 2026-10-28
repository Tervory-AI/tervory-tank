# Fix the public Autumbra shell and remove its private-console link

Branch: `codex/autumbra-public-bugs`, from `origin/main` at `4e74b42`.
Rules: `docs/build/MILESTONES-28OCT-1NOV.md`, “The rules block”, rules 1–11.
Claude opens the draft PR. No GitHub API, main push, merge or deployment used.

## What changed

`protect.tervory.com/` rewrites to `/autumbra`, but Next's browser pathname
remains `/`. The existing `usesOwnShell()` already recognizes `/autumbra` and
`/autumbra/...` on main; checking only the browser pathname still wrapped the
rewritten public page in the app sidebar. The shell now recognizes the matched
Autumbra route before applying that existing helper. `/admin/autumbra` has the
`admin` route root, so it keeps its normal shell and existing sign-in gate.

| File and line (branch) | Change |
| --- | --- |
| `workspace/app/shell.tsx:5,32` | Read Next's matched layout segments; use `/autumbra` for an Autumbra route, including the public-host rewrite. Other routes retain the browser pathname. |
| `workspace/app/autumbra/page.tsx:1,34` | Delete the unused Link import and private-console paragraph. Keep the footer wrapper, styles, logo, colours and all other wording. |
| `tests/autumbra_public_bugs/test_page.py:1,40,87` | Real local Next/browser test with an offline Clerk adapter in a temporary copy. Check public server HTML and DOM, admin shell and sign-in redirect. Optional screenshot capture. |
| `tests/shell_nav.test.ts:83` | Exact/nested Autumbra route boundaries, admin routes and similarly named paths. |
| `tests/shell_popout.ts:23` | Supply the new Next hook in the existing offline shell test adapter. |
| `tests/autumbra_public_bugs/PR.md:1` | This description and verification record. |
| `tests/autumbra_public_bugs/evidence/` | Command outputs and three offline screenshots linked below. |

No production auth, middleware, host mapping, CSS, asset, Tank, data or setting
changes. No new UI or copy. `product-nav.ts` already had the requested route
boundaries and is unchanged.

## Offline verification

`test_public_host_and_direct_page_have_no_shell_admin_keeps_gate` runs the real
Next middleware, root layout, Shell and public/admin pages locally. Only Clerk
is replaced at the import boundary, using an offline founder identity. Tank
points to a closed loopback port; the browser blocks non-local requests. No real
sign-in, credentials or production data are used. Host routing is exercised
through the real middleware using `x-forwarded-host`.

- Direct `/autumbra` on the app host and `/` on the protect host return 200 and
  have no sidebar in server HTML or browser DOM, and no private-console text/link.
- Anonymous `/admin/autumbra` requests on both hosts get the existing 307
  sign-in redirect, without visiting the external identity service.
- The offline founder's real admin page still has Workspace navigation,
  Dashboard and Billing. No browser page errors occur.
- The route-helper test covers `/autumbra/`, nested owner/report paths,
  `/admin/autumbra`, nested admin paths, `/autumbra-private` and `/autumbran`.

This verifies application routing/rendering, not live DNS, reverse-proxy
deployment or Clerk service behaviour.

## Exact commands and results

From the repository root unless stated otherwise. The existing cloud activation
supplies Python, Node and installed dependencies; no new service or key added.

```bash
git status --short
git fetch origin main
git switch -c codex/autumbra-public-bugs origin/main
```

Clean worktree; fetch advanced main from `6c28239` to `4e74b42`; created this
branch. Initial scope checkpoint `f47eade` was committed and pushed before
product changes.

```bash
source /workspace/tervory-env/activate.sh
python -m pytest -q tests/autumbra_public_bugs/test_page.py > /tmp/autumbra-before.log 2>&1
```

Against unchanged main product code: **1 failed in 11.81s**, on the rendered
private-console text. [Output](evidence/before-private-link.txt).

```bash
source /workspace/tervory-env/activate.sh
python -m pytest -q tests/autumbra_public_bugs/test_page.py > /tmp/autumbra-host-before.log 2>&1
```

After removing only the paragraph/import, before the shell fix: **1 failed in
20.72s**, because the protect-host root still had one sidebar. Direct `/autumbra`
passed its checks. [Output](evidence/before-host-shell.txt).

```bash
source /workspace/tervory-env/activate.sh
python -m pytest -q tests/autumbra_public_bugs/test_page.py > /tmp/autumbra-after.log 2>&1
```

After the shell fix: **1 passed in 19.20s**. [Output](evidence/after-first-pass.txt).
These three runs preceded the extra server-HTML assertion and optional
screenshot capture in the final test version.

```bash
source /workspace/tervory-env/activate.sh
AUTUMBRA_PUBLIC_PROOF_DIR=tests/autumbra_public_bugs/evidence python -m pytest -v tests/autumbra_public_bugs/test_page.py tests/test_shell_nav.py tests/test_shell_1.py tests/test_bf1_workspace_access.py > /tmp/autumbra-tests.log 2>&1
node --experimental-strip-types --test tests/product_hosts.test.ts > /tmp/autumbra-hosts.log 2>&1
ruff check tests/autumbra_public_bugs --select E9,F
git diff --check
```

**9 passed in 25.30s**, exit 0: final real Next/browser regression, route
boundaries, existing responsive shell/pop-out checks and access tests.
[Output with test names](evidence/tests.txt).
Host routing: **7 passed, 0 failed**, exit 0. [Output](evidence/host-routing.txt).
Ruff: `All checks passed!`, exit 0. [Output](evidence/lint.txt).
The unstaged diff check had no output, exit 0. Once the evidence was staged,
`git diff --cached --check` identified trailing spaces in two pytest failure
output lines. Only trailing whitespace in those two evidence files was
trimmed; failure text and results are unchanged. The final full-branch check
is `git diff 4e74b42 --check` (no output, exit 0).

### TypeScript limitation, reproduced on main

From `workspace/`:

```bash
source /workspace/tervory-env/activate.sh
./node_modules/.bin/tsc --noEmit --incremental false > /tmp/autumbra-typecheck.log 2>&1
```

Exit 2: existing `.next` cache references a missing Market Lab route; also
`app/tiger/plugins-data.test.ts:3` imports a `.ts` path without the compiler
option allowing it. [Initial output](evidence/typecheck-initial.txt).

To distinguish generated-cache state from source errors, the same tsc command
was run in a `git archive 4e74b42 workspace` extraction and a branch copy, both
without `.next`, using the same node_modules. Both report the Tiger TS5097
error. The main archive initially also lacked the untracked Next-generated
image declarations (three SVG import errors). With the branch's generated
`next-env.d.ts` copied into the temporary main archive, both report **only the
same Tiger error**, exit 2. Exact reproduction commands are recorded below.

- [Main without generated declarations](evidence/typecheck-base.txt)
- [Main with matching generated declarations](evidence/typecheck-base-generated.txt)
- [Branch without stale cache](evidence/typecheck-branch.txt)

No unrelated file was changed to suppress this error. A repository-wide clean
typecheck is not claimed; the actual Next routes compile in the passing test.

<details>
<summary>TypeScript reproduction commands (repository root)</summary>

```bash
source /workspace/tervory-env/activate.sh
python - <<'PY'
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path.cwd()
scratch = Path(tempfile.mkdtemp(prefix='autumbra-typecheck-', dir='/tmp'))
base = scratch / 'base'
base.mkdir()
archive = subprocess.run(['git', 'archive', '4e74b42', 'workspace'], check=True, stdout=subprocess.PIPE)
subprocess.run(['tar', '-x', '-C', str(base)], input=archive.stdout, check=True)
branch = scratch / 'branch'
shutil.copytree(root / 'workspace', branch / 'workspace', ignore=shutil.ignore_patterns('node_modules', '.next', '.env*', '*.tsbuildinfo'))
for name, tree in [('base', base), ('branch', branch)]:
    work = tree / 'workspace'
    (work / 'node_modules').symlink_to(root / 'workspace/node_modules', target_is_directory=True)
    result = subprocess.run(['./node_modules/.bin/tsc', '--noEmit', '--incremental', 'false'], cwd=work, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    output = f'{name} (no generated .next cache), exit {result.returncode}\n{result.stdout}'
    (Path('/tmp') / f'autumbra-typecheck-{name}.log').write_text(output)
    print(output, end='')
PY
```

```bash
source /workspace/tervory-env/activate.sh
python - <<'PY'
from pathlib import Path
import shutil
import subprocess
scratch = max((path for path in Path('/tmp').glob('autumbra-typecheck-*') if path.is_dir()), key=lambda path: path.stat().st_mtime)
base = scratch / 'base/workspace'
shutil.copy2(scratch / 'branch/workspace/next-env.d.ts', base / 'next-env.d.ts')
result = subprocess.run(['./node_modules/.bin/tsc', '--noEmit', '--incremental', 'false'], cwd=base, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
output = f'base with the same Next-generated next-env.d.ts, exit {result.returncode}\n{result.stdout}'
Path('/tmp/autumbra-typecheck-base-generated.log').write_text(output)
print(output, end='')
PY
```

</details>

## Screenshots and founder acceptance

These are **offline automated screenshots**, at a 1440 × 1000 browser viewport,
captured by the final test. The admin screenshot shows the existing
backend-unavailable state because this test has no Tank connection.

- [Public protect-host root](evidence/offline-protect.tervory.com.png)
- [Direct public app route](evidence/offline-app.tervory.com.png)
- [Admin with normal shell](evidence/offline-admin-autumbra.png)

**Founder-browser screenshots are missing.** The branch is not deployed and no
founder browser/session was available. Rule 11's founder-test proof and live
acceptance remain pending; these local images do not substitute for them.
After the founder's normal review/deployment process, acceptance is opening
`protect.tervory.com/` and `app.tervory.com/autumbra` with no Workspace navigation
or private-console text, and confirming `/admin/autumbra` requires sign-in and
retains its normal shell for the founder. No merge is requested.
