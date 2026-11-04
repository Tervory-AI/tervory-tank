# Trigger scratch ownership: PR 526 — 4 November 2026

## Current-main check and decision

Checked main `fa34a9f0d9e8323358ebb47c82ba5e9f2eed9fab` and existing PR head
`bb9505ed4de5a8f474258e08faa1e1829accb1b2` through GitHub. Its five 1.1.0
packages and scratch regression test remain additions, absent from main. Main's
1.0.0 engine still owns a TemporaryDirectory while run.py kills the process on
failure/timeout. The regression probe reproduces the leak on SIGKILL, SIGTERM
and timeout; stale-directory sweeping does not replace this root fix. GitHub
reported this PR mergeable, so no main merge was needed.

Keep the proposed implementation: run.py owns the temporary directory, passes it
to the engine, and waits for a failed/killed child before leaving the directory
context. Engines require an existing empty directory. This preserves rule archive
hashes, dependency pins, input/output contracts and golden cases. No approved
1.0.0 file or proposed package content was edited during this completion pass.
A Tank SIGKILL still requires the existing stale-directory safety net.

## Focused checks

`tests/test_trigger_skill_scratch.py` now checks kill, terminate, timeout and
cancellation for all five candidates, plus failed subprocess creation for all
five. Clean calls match 1.0.0; the negative probes prove that the old version leaks.
The test text and spawn error are explicit placeholders.

- Scratch regression and patch-version guard: 97 passed (socket access disabled;
  local Unix event-loop sockets allowed).
- CI Ruff E9/F command with the existing base.socials F401 exception: passed.
- Offline evals use the real versioned engines and Skala scorer, empty environment,
  no database, no HTTP client and a model method that raises. Complete results
  are recorded locally in `/tmp/trigger-backlog-offline-evals.json` after the run.
  These results are not inserted into Skala and do not authorize clients.

## Exact remaining Skala requirements

For EACH of trigger.agent_style, trigger.house_style, trigger.proselint,
trigger.readability and trigger.voice_check:

1. After reviewed source is available in the intended runtime, register/discover
   the unchanged approved 1.0.0 and candidate 1.1.0 packages. Do not approve as
   part of this PR or run production SQL to manufacture evidence.
2. Record baseline eval evidence for approved 1.0.0 if it is missing, then run
   1.1.0's golden cases through Skala's existing eval action
   (`POST /v1/skala/{skill_id}/{version}/evals`) in the intended runtime/region.
   Required case totals: agent_style 21, house_style 22, proselint 23,
   readability 22, voice_check 21. Each candidate has threshold 1.0: every case,
   including refusals, must pass. At least five distinct inputs are required.
3. Evidence must match the exact package/source hash and ordered case hashes;
   every approved baseline case must remain and candidate scores on that baseline
   must not regress. A passing candidate must be present and in staging.
   These are code-only rung-3 packages with no task_type/model calls, so the
   three-consecutive-model-runs rule does not apply.
4. The founder/Zenas reviews the evidence and explicitly approves each 1.1.0
   in Skala (`POST /v1/skala/{skill_id}/1.1.0/approve`, through the existing UI).
   Approval retires the prior approved version. No approval was performed here.
   These IDs are not room-authored *.learned.* packages, so the special learned
   source-review token gate does not apply; ordinary human review still does.

Requirements checked against current-main `tank/skala.py` approval_reason and
review_evidence. Offline result files cannot replace persisted runtime evals or
human sign-off. Merging package source alone does not promote a candidate.

## Publication status

This completion pass is committed locally on the existing PR branch. Publishing
is blocked by session access: shell Git cannot resolve github.com, and the GitHub
write connector refuses changes because approval policy is never. Final-head
hosted CI must run after publication; it is not represented as passing here.
No model call, production SQL, deployment or Skala lifecycle change was made.
