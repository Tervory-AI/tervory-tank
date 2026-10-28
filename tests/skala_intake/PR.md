# Skala intake: Trigger free checkers as versioned skills

Branch: `skala/trigger-intake-1.0.0`, started from `origin/main` at `9769998`. Tip: `d8bcbd9` (packaging `aca3481`). Claude opens the PR. No GitHub API, merge, deployment, main push, production SQL, or model call was used.

**Build and offline proof are complete; live founder acceptance is pending.** Done when the founder opens Skala, sees the six Trigger skills ready with their eval scores, presses "Approve all ready", and Trigger keeps working.

## What changed (file and line)

| File | Result |
|---|---|
| `tank/skills/trigger.proselint/1.0.0/` | New rung-3 skill: pinned proselint 0.16.0 findings. `skill.yaml`, `run.py`, `evals/cases.jsonl` (23), `CHANGELOG.md`. |
| `tank/skills/trigger.languagetool/1.0.0/` | New rung-3 skill: maps LanguageTool 6.8 v2/check JSON (room fetches on the private checker network). Fixtures under `evals/fixtures/`. 20 cases. |
| `tank/skills/trigger.agent_style/1.0.0/` | New rung-3 skill: vendored agent-style RULES.md + detectors (`vendor/agent_style/`, pin d1bdb0f). 22 cases. |
| `tank/skills/trigger.house_style/1.0.0/` | New rung-3 skill: vendored stylebooks + `data/book_terms.json` Avoid candidates. 22 cases. |
| `tank/skills/trigger.readability/1.0.0/` | New rung-3 skill: passive-voice candidates + Practical Prose F3 fence balance. 22 cases. |
| `tank/skills/trigger.voice_check/1.0.0/` | New rung-3 skill: banned/required terms and sentence-length override. 22 cases. |
| `tank/requirements.txt` | Adds `proselint==0.16.0` so Tank can load `trigger.proselint` (already Trigger's free pin). |
| `agents/trigger/checkers.py` | Dual-path: for each skill, call approved Skala via Tank; on 409/missing `run_skill`, keep today's local copy. Room still fetches LanguageTool on the private network. Proselint registry guarded against double-load. |
| `agents/trigger/service.py` | `check_text` / `write` pass `tank` + `tenant_id` into `check`. |
| `agents/trigger/app.py` | `/check` passes `app.state.tank`. |
| `tests/skala_intake/test_trigger_skills.py` | Offline: packages load, evals pass at threshold, unapproved never runs for a client, approved path uses Skala not the room copy, rollback keeps the package loadable. |
| `tests/skala_intake/CASE_COUNTS.json` | Case counts per skill. |
| `tests/skala_intake/PR.md` | This proof. |

No Workspace page, UI copy, Figma frame, pricing, secrets, or other room was edited.

## Case counts (evals from existing offline fixtures / known answers)

| Skill | Cases | Refusals (`must_refuse`) |
|---|---|---|
| `trigger.proselint@1.0.0` | 23 | 3 |
| `trigger.languagetool@1.0.0` | 20 | 3 |
| `trigger.agent_style@1.0.0` | 22 | 3 |
| `trigger.house_style@1.0.0` | 22 | 3 |
| `trigger.readability@1.0.0` | 22 | 3 |
| `trigger.voice_check@1.0.0` | 22 | 3 |

Each package is rung 3, `eval_threshold: 1.0`, no `task_type` (no model). Until the founder approves 1.0.0, Trigger keeps today's in-room checkers. After approval, the room calls Skala for that skill and never its own copy for that part.

## Follow-ups skipped (not merged on main as packable work)

| Item | Why skipped |
|---|---|
| `tiger.playbook` | Not present under `tank/skills/` or as a merged Trigger/Tiger free tool on main. |
| `market.research` 2.0.0 (GPT-Researcher) | Only `1.0.0` and `1.1.0` on main; no GPT-Researcher 2.0.0 package. |
| `zenas.scope` with SA criminal phrases | `zenas.scope` 1.0.0 / 1.1.0 already on main; no separate SA-phrase packaging change merged for intake. |
| `zenas.meaning_search` | Not on main as a skill package. |
| `tisan.visual_check` (pixelmatch) | Not on main as a skill package. |
| `base.audit_sample` | Not on main as a skill package. |

## Exact commands and results

```bash
git fetch origin main
git checkout -B skala/trigger-intake-1.0.0 origin/main
# … package work …

PYTHONPATH=tank:agents:agents/_chassis \
  pytest -q tests/skala_intake/test_trigger_skills.py --tb=line
# 7 passed

PYTHONPATH=tank:agents:agents/_chassis \
  pytest -q tests/trigger_first_build/test_trigger.py tests/skala_intake/test_trigger_skills.py \
  -k 'not real_room and not real_schema' --tb=line
# 34 passed, 2 deselected (real Postgres/LanguageTool integration)

PYTHONPATH=tank pytest -q tests/test_skills_offline.py::test_every_skill_package_has_required_files --tb=line
# 1 passed
```

## Founder's test

1. Open Skala.
2. See `trigger.proselint`, `trigger.languagetool`, `trigger.agent_style`, `trigger.house_style`, `trigger.readability`, `trigger.voice_check` at 1.0.0 ready with eval scores.
3. Press **Approve all ready**.
4. Run a Trigger check; the room still returns mechanical findings (via Skala for approved skills).
5. Rollback of an approved version restores the previous approved package behavior; an unapproved version never runs for a client (409 from Tank; room local path until approved).
