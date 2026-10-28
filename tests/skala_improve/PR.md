# Skala improvement loop — blocked on required failure records

Branch: `codex/skala-improve`, from main `3f469b0`.

Stopped under founder rule 9: “If something blocks you … stop at that point and
report exactly what is missing. Do not ask, do not guess, do not work around it.”
No improvement-loop implementation, migration, candidate version or schedule is
claimed. This is a blocker report, not an implementation ready to merge.

## Missing inputs

1. **Trigger learning records do not exist in this main revision.**
   `agents/trigger/schema.sql:1` defines only `agent_trigger.voices`.
   `agents/trigger/app.py:49` / `:58` / `:63` expose voice, check and write;
   `tank/trigger_routes.py:93` accepts only write/check. There is no persisted
   user rejection/correction with the original input, corrected answer, confirming
   person and producing skill/version. `agents/trigger/service.py:73` routes
   `trigger.write` as a task, without a Skala skill reference; no Trigger package
   exists under `tank/skills`. The requested Trigger learning source and its
   skill/version attribution are missing.
2. **Base audit wrong verdicts have no corrected expected answer.**
   `tank/base_audit.py:91` (`checked_verdicts`) accepts only verdict-cell changes
   to the 200-record CSV and rejects changes to the other columns. The review
   persists the verdict map and reviewer, not a replacement answer. A wrong
   verdict alone does not meet this brief's definition of a confirmed labelled
   failure: a person or official source must supply the right answer. Missing:
   that corrected answer and attribution to the skill/version that produced the
   failed field. No label was inferred from the verdict.
3. **Tiger's local correction helper is not tenant-attributed confirmation.**
   `agents/tiger/gold_feedback.py:42` writes a page and expected price to a local
   inbox with `verified: false` (`:76`); the record has no tenant ID, producing
   skill version or confirming reviewer. It cannot safely be treated as confirmed
   tenant-scoped evidence. No tenant or verification was guessed.

The existing eval and approval primitives were located in `tank/skala.py`, gold
intake in `tank/gold.py`, and room proposals in `tank/agent_skills.py`. They do not
supply these missing source records. A generic intake endpoint alone would not
connect the required real mistakes and would not satisfy the brief.

## Completed work and exact command proof

All operations ran in the managed cloud checkout `/workspace/tervory-tank`.
Read `AGENTS.md`, `docs/cursor/CONTEXT.md`, the rules block in
`docs/build/MILESTONES-28OCT-1NOV.md`, and the source files cited above.

```sh
git status --short
# exit 0, clean previous branch
git fetch origin main
# exit 0, main advanced from 678d47e to 3f469b0
git switch -c codex/skala-improve origin/main
# exit 0
git add tests/skala_improve/PR.md
git commit -m 'Record Skala improvement loop scope and proof plan'
git push -u origin codex/skala-improve
# exit 0; f2af10b pushed, remote branch created
```

Read-only source checks:

```sh
rg -n '^(async )?def |^class |@app\.|@router\.' agents/trigger/app.py agents/trigger/service.py tank/trigger_routes.py
# Only voice, check, write and their routing/receipt helpers; no feedback/learning operation.
rg -n 'learning_record|learning_records|trigger\.learn|trigger\.feedback|agent_trigger\.' tank agents/trigger -g '*.py' -g '*.sql' -g '!vendor/**'
# Only agent_trigger.voices schema and voice-store queries returned.
rg --files tank/skills | rg 'trigger'
# No matching skill package (rg exit 1).
cat agents/trigger/schema.sql
sed -n '47,110p' agents/trigger/service.py
sed -n '1,170p' tank/base_audit.py
sed -n '165,205p' tank/base_audit.py
rg -n '^async def|^def |tenant_id|verified|expected_price' agents/tiger/gold_feedback.py
# Reads completed; supporting fields/behavior described above.
```

Final blocker-report publication:

```sh
git diff --check
git add tests/skala_improve/PR.md
git commit -m 'Document missing confirmed-failure sources for Skala loop'
git push origin codex/skala-improve
```

Only `tests/skala_improve/PR.md:1` changed. No source edits, tests, model calls,
production SQL, secret access, GitHub API, deployments, merges or live-data changes.
No nightly command is offered because no nightly implementation exists yet. Grok
has no task to configure from this branch. No screenshots or founder-browser
acceptance are claimed. Claude opens the PR; founder merges.
