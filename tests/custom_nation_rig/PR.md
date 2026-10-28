# Job 8 — Custom Nation on Rig

Branch: `codex/job8-custom-nation-rig`.
Base: `origin/main` at `6c28239`.
Brief: `docs/build/TONIGHT-2026-10-27.md`, section 8, including rules 1–11.
The founder confirmed job 2 (Rig SMTP delivery) complete on 28 October 2026.

## Status

Step 1 is implemented and verified offline. Claude will open the PR; this thread
uses git only and does not call the GitHub API or merge.

1. Store theme and embed snippet: complete offline. The existing settings API
   accepts `theme: neutral | custom-nation`; omitted values preserve an existing
   store's selection. No admin label, control or wording was added.
2. Privacy slot: next. No approved notice text is available in the repository's
   Figma evidence. No Figma reader is connected, and the public file read failed.
   The brief says to build the slot and stop at that point.
3. Notice version/time and restricted quote fields: pending step 2.
4. Custom Nation publishable key: pending step 2 and the founder's test-page
   address. No live key has been issued or inspected.
5. Real catalogue, quotes inbox and founder browser test: pending step 2 and
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
| `agents/rig/rigbox/store.py:293,706,734` | Persist/read the tenant's theme in memory and Postgres; legacy settings/import calls preserve it. |
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

## Founder proof

No founder-browser test or screenshot has been captured for this job. No live
catalogue, quote submission or email delivery is claimed. Offline tests and
file/line changes will be recorded here as each step completes.
