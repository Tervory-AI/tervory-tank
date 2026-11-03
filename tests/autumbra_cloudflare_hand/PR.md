# Autumbra A3b — Free-plan guards, follow-up to merged #566

PR #607, same branch `codex/autumbra-cloudflare-hand`. The founder merges.
M24 LIVE TEST REMAINS HELD pending A2 real owner-email delivery. This delivery
covers code, docs and offline tests only. No live Cloudflare writes or M24 run.

## Already-present fixes verified before editing

`git fetch origin && git merge origin/codex/autumbra-cloudflare-hand && git merge origin/main`
Exit 0: remote task branch already current; merged main `1ad2c794` without
conflicts in merge `c97ac11f`. Prior work is preserved. `git log -4 --oneline`
confirmed `04867754`, the existing Free-plan implementation. No duplicate code
or test changes were made in this verification round.

- `agents/ghost/cloudflare_edge.py:115` reads `plan.legacy_id` from the zone
  lookup before applying a shield. Free, missing or unrecognized plans refuse
  host-scoped `rate_limit`; `check_managed_plan` applies the same refusal for
  `waf_managed`. Paid managed execution remains unsupported by this hand.
  Successful applied records include `cloudflare_plan`.
- `agents/ghost/enforce_apply.py:92` records `applied=False`,
  `control=cloudflare`, `cloudflare_plan` (null if unknown), and the existing
  fixed error on plan refusal. Approval checks the current plan again, including
  downgrades. There is no fixture fallback or path-only expression rewrite.
- `tests/test_autumbra_cloudflare_hand.py:331` proves Free refuses both kinds
  with only a zone GET and no write, missing/unknown plans refuse, Pro rate
  limiting preserves the host match, Free `block_ip` applies, and approval after
  a downgrade refuses. Lines 375 onward verify `192.0.2.1` passes the unchanged
  payload validator and never-block gate.
- `docs/ops/AUTUMBRA-CLOUDFLARE-LIVE.md` already requires a custom-rule slot on
  Free. M24 uses `block_ip` for RFC 5737 TEST-NET-1 `192.0.2.1` on `tervory.com`,
  through the existing queue, approval, receipt, owner email, signed Undo and
  health checks. Rate limiting remains a Pro-plan variant only.

## Documentation completed in this round

`docs/ops/AUTUMBRA-CLOUDFLARE-LIVE.md:4` identifies merged #566 and follow-up
#607 and explicitly holds live M24 pending A2 real owner-email delivery. The
procedure is retained for later founder acceptance after the hold is lifted.
No validation, never-block rule, mode, cap or Undo behavior was changed.

## Availability rechecked 3 November 2026

Cloudflare's [rate-limit availability table](https://developers.cloudflare.com/waf/rate-limiting-rules/#availability)
allows Path and Verified Bot on Free; Host starts at Pro. Its
[managed-rules availability table](https://developers.cloudflare.com/waf/managed-rules/#availability)
excludes the Cloudflare Managed Ruleset from Free. The distinct Free Managed
Ruleset does not make this shield available. A path-only rewrite would widen
owner approval to every matching host in the zone, so it is never used.

## Offline validation after merging current main

`/home/ammosync/.codex/tervory-integration-closure-evidence-20261101/venv-ci/bin/python .proof/run_review.py tests/test_autumbra_a3_review.py tests/test_autumbra_cloudflare_hand.py tests/test_autumbra_cloudflare_live.py tests/test_bucket1_radix.py tests/test_radix_passive.py`
Exit 0: **192 passed, 6 skipped in 36.55s**. The wrapper uses the repository's
clean offline environment, disables external sockets and permits loopback only.

`/home/ammosync/.codex/tervory-integration-closure-evidence-20261101/venv-ci/bin/python -m ruff check agents/ghost/cloudflare_edge.py agents/ghost/enforce_apply.py tests/test_autumbra_cloudflare_hand.py --select E9,F`
Exit 0: **All checks passed!**

`git diff --check`
Exit 0: no whitespace errors.

CI tank is the full-suite result of record. Its completed result for the final
head will be recorded in the GitHub PR body without another source push. Prior
local full-suite dependency failures are not A3 regressions. Only failures that
do not also fail on origin/main will be fixed. Historical command summaries
remain in `tests/autumbra_cloudflare_hand/EVIDENCE.txt`; no raw CI traces or
Docker/network identifiers are pasted here.

## Founder acceptance outstanding

A2 real owner email, founder-managed Coolify settings, a clean deployed seal and
actual M24 browser screenshots remain outstanding. The live M24 hold remains
in force. No live receipt, inbox delivery, signed Undo, dashboard apply or browser
screenshot is claimed. No secret values were inspected, and no model calls,
production writes, merge to main or deployment were performed.
