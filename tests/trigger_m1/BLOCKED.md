# Historical stop — resolved by the founder on 3 November 2026

The founder approved scheduling an approved GBP post with `limit: none`;
Google's length rejection is terminal for automatic retry, and editing returns
it to draft. That decision supersedes the Marketing SPEC's missing-limit line.
M1 implementation continued on this same branch. Current rule, operations and
acceptance boundaries are in [TRIGGER-GBP.md](../../docs/ops/TRIGGER-GBP.md).
The original stop record below is retained as history, not current status.

---

# Trigger M1 — stopped at the scheduling contract

3 November 2026. No M1 engine, channel connection, page, visible wording,
credential, live write or deployment has been built or performed.

## Exact missing input

An approved scheduling rule for Google Business Profile when W1 has no verified
numeric format limit, or an officially verified numeric GBP post limit.

The current native Marketing SPEC `151:3973`, mirrored in frame `210:2897`, says:

> Missing limits block scheduling.

W1 `agents/trigger/formats.py:26` defines `Google Business Profile post` with
`Format(None, ...)`. Its checker preserves `length.limit = None`; it does not
report a numeric within-limit result. W1's PR documentation explicitly records
that its cited official Google references do not supply a numeric limit and
that a limit must not be invented.

M1 requires GBP approval, scheduling and automatic publication. Implementing that
path now would require guessing a limit or bypassing the SPEC gate. Founder rule
9 requires stopping at this point, so neither was done. This is a contract
blocker, not a request for secret values. No question or workaround is proposed.

Read sources:

- [Marketing SPEC frame](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=210-2897), page `148:9`, native root `151:3973`.
- [W1 format definition](../../agents/trigger/formats.py) and [W1 handoff](../trigger_w1/PR.md).
- [Google LocalPost reference](https://developers.google.com/my-business/reference/rest/v4/accounts.locations.localPosts).
- [Google Business Profile post help](https://support.google.com/business/answer/7342169?hl=en).

The live Figma frame is titled “SPEC · Marketing · Changed after approval,
awaiting founder”. Its changed wording was not put into an app. Both the visible
frame and native spec were read; no Figma content was changed.

## Preserved dependency merge

Own directory: `/workspace/codex-trigger-m1`.
Sole branch: `codex/trigger-m1-marketing`.
Main input: `fb55cd35e6f5c791802a6aaece39a267994cbbcd`.
W1 input: `3838b50ab54448a4b21da276bc564de62acddded` (#595).
Merge: `23a1f930`.

The sole conflict was the appended schema area. `tank/schema.sql` retains both
main's MCP G1 additions and W1's provenance/RLS additions above the generated
agent-memory block. All other W1 changes were merged unchanged. No M1 schema
was added. This dependency merge has been pushed, not merged into main.

## Exact commands and results

```bash
git clone https://github.com/Tervory-AI/tervory-tank.git /workspace/codex-trigger-m1
cd /workspace/codex-trigger-m1
git fetch origin main
git checkout -B codex/trigger-m1-marketing origin/main
git config user.name 'Codex'
git config user.email 'codex@users.noreply.github.com'
# PASS.

git merge origin/codex/trigger-w1-writing
# CONFLICT (content): Merge conflict in tank/schema.sql
# Automatic merge failed; fix conflicts and then commit the result.

ls agents/trigger/README.md tests/trigger_first_build/PR.md tests/trigger_second_build/PR.md agents/trigger/formats.py tank/command.py tank/access.py tank/vault_routes.py tank/trigger_routes.py tank/case_study_sources.py tank/schema.sql tank/main.py tests/test_secrets.py
ls tests/trigger_w1/PR.md
# PASS: all named existing files present. docs/ops/TRIGGER-GBP.md is a
# requested new file, not a missing existing file; it was not created.

# Resolve the one schema conflict by removing its three conflict-marker
# lines and retaining both complete SQL sections. No SQL was executed.
git diff --check
# PASS, exit 0.

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tank:tests /home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m pytest -q -p no:cacheprovider --disable-socket --allow-unix-socket tests/test_trigger_x_length.py --tb=short
# .................................................................... [100%]
# 68 passed in 0.47s

git add tank/schema.sql
git commit -m 'Merge Trigger W1 dependency retaining main MCP and writing schema additions'
# PASS: 23a1f930.
git fetch origin main
git merge origin/main
# PASS: Already up to date.
git push -u origin codex/trigger-m1-marketing
# PASS: new remote branch; tracks origin/codex/trigger-m1-marketing.
```

The 68 tests are only the focused offline W1 format regression, not a full Tank
suite or a schema execution proof. Full Tank/Trigger/Command validation and all
M1-specific tests were not run because implementation stopped at the contract.
No model call, Google account/API write, production SQL or secret access was used.

Founder-browser test and screenshots: **not performed and not available**.
Nothing is claimed done. Claude opens the PR if needed; founder alone merges.
