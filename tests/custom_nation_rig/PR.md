# Job 8 — Custom Nation on Rig

Branch: `codex/job8-custom-nation-rig`.
Base: `origin/main` at `6c28239`.
Brief: `docs/build/TONIGHT-2026-10-27.md`, section 8, including rules 1–11.
The founder confirmed job 2 (Rig SMTP delivery) complete on 28 October 2026.

## Status

Stopped at the explicit step-2 wording gate. Step 1 and the empty privacy slot
are implemented and verified offline. Claude will open the PR; this thread uses
git only and does not call the GitHub API or merge. Custom Nation is not live.

1. Store theme and embed snippet: complete offline. The existing settings API
   accepts `theme: neutral | custom-nation`; omitted values preserve an existing
   store's selection. No admin label, control or wording was added.
2. Privacy slot: complete, empty and hidden in both existing quote forms. No
   wording, link, visible layout or form field was invented. Approved notice
   text/frame evidence is unavailable to this task; see the blocker below.
3. Notice version/time and restricted quote fields: not started, because step 2
   explicitly requires stopping at the wording gate.
4. Custom Nation publishable key: not started; also needs the founder's test-page
   address. No live key has been issued or inspected.
5. Real catalogue, quotes inbox and founder browser test: not started; needs
   founder-provided inputs. No live store data has been changed.

## Commands and evidence

Run from `/workspace/tervory-tank`:

```text
git status --short
  No output: the previous task's worktree was clean.
git fetch origin main
  origin/main advanced from 62db0f8 to 6c28239.
git show origin/main:docs/build/TONIGHT-2026-10-27.md
  Read section 8 and its rules 1–11.
git switch -c codex/job8-custom-nation-rig origin/main
  Created the job branch from main.
```

Early checkpoint `23108f4` was pushed with:

```sh
git add tests/custom_nation_rig/PR.md
git commit -m 'docs(rig): record job 8 scope and proof checkpoints'
git push -u origin HEAD:refs/heads/codex/job8-custom-nation-rig
```

Result: branch created on origin; main was not pushed.

### Step 1

| File and line | Change |
| --- | --- |
| `agents/rig/schema.sql:129` | Add `retailers.theme`, default neutral, constrained to the two existing skins. |
| `agents/rig/rigbox/store.py:293,705,734` | Persist/read the tenant's theme in memory and Postgres; legacy settings/import calls preserve it. |
| `agents/rig/rigbox/retailer.py:78,98,112` | Return and validate the setting; generate that store's snippet using its saved theme. |
| `agents/rig/rigbox/quotes/keys.py:29` | Validate the theme and include it in the existing snippet; neutral remains the default. |
| `tests/test_custom_nation_rig.py:22` | Two-store memory/Postgres checks, schema reapplication, reload, unchanged settings, snippet ownership and invalid-value refusal. The snippet test stubs issuance; it creates no key. |
| `tests/test_rig_store_job.py:21` | Existing empty-settings assertion includes the neutral default. |

```sh
source /workspace/tervory-env/activate.sh
python -m pytest -q tests/test_custom_nation_rig.py tests/test_rig_store_job.py tests/test_rig_feeds_retailer.py tests/test_rig_quotes_hosting.py > /tmp/job8-step1-tests.log 2>&1
```

First run: `2 failed, 45 passed, 1 warning, 1 error in 1.40s`; all three database
failures were connection refusals at the stopped local test Postgres service.
Started the existing disposable stores, then reran the same command:

```sh
bash /workspace/tervory-env/start.sh stores
```

Result: launcher exited 0; rerun: `48 passed, 1 warning in 2.20s`.

```sh
ruff check agents/rig/rigbox/retailer.py agents/rig/rigbox/store.py agents/rig/rigbox/quotes/keys.py tests/test_custom_nation_rig.py tests/test_rig_store_job.py --select E9,F
git diff --check
```

Results: `All checks passed!`; whitespace check exited 0 with no output.

Step 1 was committed as `8d97533` and pushed before starting step 2:

```sh
git commit -m 'fix(rig): persist each store theme in its embed snippet'
git push origin HEAD:refs/heads/codex/job8-custom-nation-rig
```

Result: origin advanced from `23108f4` to `8d97533`.

### Step 2: the inert slot only

| File and line | Change |
| --- | --- |
| `agents/rig/rigbox/quotes/widget-source.patch:1,116,123,130` | Extend the existing patch against widget source `f382f8da90944a3176c1bd43cfc77f14e78c6a0f`: an empty, hidden slot after the submit button in each quote form, plus source tests for both existing themes. |
| `agents/rig/rigbox/quotes/widget/manifest.json:1` | Select the rebuilt content-addressed bundle and its integrity hash. |
| `agents/rig/rigbox/quotes/widget/tervory-rig.4b815c02b954ffdfbef833736dfa92a2cfacf1e0b57d68238c151c3fc3962a4d.umd.js:1` | Existing widget rebuilt with the hidden slot. Replaces `tervory-rig.500d8e8c4a5b11b22fc4530f2bdc00385910410dedfaa2afb7565b0e68a79b7f.umd.js`; only the manifest-selected bundle remains. |
| `tests/test_custom_nation_rig.py:107` | Real Chromium checks of the shipped bundle, both themes, 390/1440 widths, both quote forms; slots are hidden, empty, without links or inputs. Requests are confined to the offline fixture server. |
| `tests/custom_nation_rig/PR.md:1` | PR description, commands, results and exact stopping point for Claude. |

Reused the pinned widget repository and its existing build/package scripts.
The selected `/workspace/tervory-rig` checkout remains clean; only the Tank branch
contains changes. No 3D bundle was rebuilt or changed.

```sh
git clone --no-hardlinks /workspace/tervory-rig /tmp/rig-job8-widget
git -C /tmp/rig-job8-widget checkout --detach f382f8da90944a3176c1bd43cfc77f14e78c6a0f
git -C /tmp/rig-job8-widget apply --unidiff-zero /workspace/tervory-tank/agents/rig/rigbox/quotes/widget-source.patch
# After adding the empty slot and its source test in this temporary checkout:
cd /tmp/rig-job8-widget
git add -N tests/custom-nation-privacy-slot.test.ts
git diff --no-ext-diff --unified=0 > /workspace/tervory-tank/agents/rig/rigbox/quotes/widget-source.patch
source /workspace/tervory-env/activate.sh
npm ci --cache /workspace/tervory-env/cache/npm --no-audit --no-fund > /tmp/job8-widget-install.log 2>&1
npm run lint > /tmp/job8-widget-checks.log 2>&1
npm run build >> /tmp/job8-widget-checks.log 2>&1
npx vitest run >> /tmp/job8-widget-checks.log 2>&1
node scripts/package-widget.mjs /workspace/tervory-tank/agents/rig/rigbox/quotes/widget >> /tmp/job8-widget-checks.log 2>&1
```

Results: install, lint, TypeScript and Vite builds exited 0. The existing bundle
check reported `no sample data (18 names checked)`. Vitest: `3 passed (3)` test
files, `23 passed (23)` tests. Shipped UMD: 66,033 bytes; 17,474 bytes gzipped,
within the existing 150 KB limit. Removed only the superseded generated UMD.

```sh
git -C /workspace/tervory-rig apply --check --unidiff-zero /workspace/tervory-tank/agents/rig/rigbox/quotes/widget-source.patch
```

Result: exit 0 against the clean pinned source checkout.

From `/workspace/tervory-tank`, final offline regression run:

```sh
source /workspace/tervory-env/activate.sh
python -m pytest -q tests/test_custom_nation_rig.py tests/test_rig_store_job.py tests/test_rig_feeds_retailer.py tests/test_rig_quotes.py tests/test_rig_quotes_postgres.py tests/test_rig_quotes_hosting.py tests/test_rig_quotes_limits.py tests/test_tank_one_door.py > /tmp/job8-final-tests.log 2>&1
```

Result: `118 passed, 1 warning in 25.93s`. Includes real temporary Postgres,
schema reapplication, two stores, both browser sizes/themes and the one-door
guard. An earlier run had `4 failed, 114 passed, 1 warning in 48.00s`: the four
new browser cases did not reach the missing-product form with the original
search probe. Reusing the established no-results probe fixed the test setup;
the widget or search logic was not changed to make those checks pass.

```sh
python -m pytest -q tests/test_secrets.py tests/test_tank_boots.py > /tmp/job8-ci-tests.log 2>&1
ruff check agents/rig/rigbox/retailer.py agents/rig/rigbox/store.py agents/rig/rigbox/quotes/keys.py tests/test_custom_nation_rig.py tests/test_rig_store_job.py --select E9,F
git diff --check
```

Results: `3 passed in 12.95s` (including real Tank startup twice on an empty
database); changed-file lint passed; whitespace check passed.

Repository-wide lint is **not green**, due to an existing main failure:

```sh
ruff check tank tests --select E9,F --per-file-ignores 'tank/skills/base.socials/1.0.0/run.py:F401'
git show origin/main:tests/test_workers_command.py > /tmp/job8-main-test-workers-command.py
ruff check /tmp/job8-main-test-workers-command.py --select E9,F
git diff origin/main -- tests/test_workers_command.py
```

Both lint runs report `291:72: F811 Redefinition of unused api from line 22`.
The diff is empty. That worker test is outside job 8 and was not edited.

Step-2 checkpoint commands (the resulting commit is the branch head):

```sh
git add agents/rig/rigbox/quotes/widget-source.patch agents/rig/rigbox/quotes/widget tests/test_custom_nation_rig.py tests/custom_nation_rig/PR.md
git commit -m 'feat(rig): add inert quote privacy slot pending approved wording'
git push origin HEAD:refs/heads/codex/job8-custom-nation-rig
```

## Required stopping point

Section 8, step 2 says: **“Until that text is in Figma, build the slot and stop,
reporting that it waits on the wording.”** The missing input is the founder's
approved privacy notice wording/frame evidence from Rig Figma file
`uRpPy3Hns0WxWZYTPwZ2ni`, frames 01–05. The existing widget evidence at
`/workspace/tervory-rig/docs/rig4b-visual-review.md:10` records unavailable source
frame exports. No Figma reader is connected in this task. A credential-free
`urllib.request.urlopen` read of
`https://www.figma.com/design/uRpPy3Hns0WxWZYTPwZ2ni/` returned
`Figma public page access failed: OSError`. This does not claim that the live
Figma file contains no text; it means approved text could not be obtained here.

No privacy sentence, version, approval record, privacy URL, test-page origin,
catalogue product or quotes inbox has been guessed. Steps 3–5 remain pending.
The widget currently has a slot, **not a privacy notice or consent record**.

## Founder proof

No founder-browser test or screenshot has been captured for this job. No live
catalogue, quote submission or email delivery is claimed. All product data used
by the checks stayed in disposable local test stores. No production SQL,
deployment, live key issuance, live quote or live-store mutation was performed.
The founder's browser/inbox test remains outstanding; this is not launch proof.
