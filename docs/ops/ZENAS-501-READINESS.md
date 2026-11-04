# PR #501: quote verification before masking

Reviewed against main fa34a9f0d9e8323358ebb47c82ba5e9f2eed9fab on 4 November 2026.
The existing branch is grok/zenas-rule-card-dated-quotes. The real merge conflict
was supported_quotes in selftest.py: keep main's memo-body sentence acceptance,
answer-failure diagnostics and cross-case attribution checks, and additionally
accept a masked card quote only after checking its fingerprint and length
against the expected judgment. Reject a masked card quote assigned to another
case even when the memo separately gives the correct citation and raw quote.

The engine copies remain identical. verify_unmasked and allow_masked default to
False, preserving the approved 1.0.x skill behavior. Only the room callers and
proposed rule_card/cite_check 1.1.0 opt in. Approved version folders, the scope
rules, routing, lifecycle and production data are unchanged. Fingerprints and
lengths preserve verification evidence without storing the unmasked identifier.
Wrong dates/numbers, edited surrounding words, unresolved citations, missing
fingerprints, excess lengths and exhausted scan budgets fail closed.

## Narrow offline proof

Use PYTHONPATH=.:tank with the repository's development dependencies:

    pytest -q tests/test_zenas_rule_card_dated_quotes.py tests/test_zenas_selftest_misses.py
    pytest -q tests/zenas_za_meaning_search/test_sa_scope.py
    ruff check tank tests --select E9,F --per-file-ignores "tank/skills/base.socials/1.0.0/run.py:F401"

The dated-quote suite includes actual skala.run_evals invocations: rule_card
1.1.0 must pass 11/11 and cite_check 1.1.0 must pass 17/17, with eligible=true.
Contexts reject network and live model use; the rule-card model responses are
saved fixture output. The suite also exercises unchanged approved 1.0.x versions,
room/Tank masking, wrong fingerprints, oversized scans and cross-case attribution.
These local results do not write deployed Skala evidence or approve anything.

## Remaining evaluation and approval steps (separate from source readiness)

After review/merge and separately authorized deployment, on EACH regional Tank:

1. Check the currently approved version and baseline eval evidence for each of
   zenas.rule_card and zenas.cite_check. If baseline evidence is missing, record
   its non-model fixture eval through POST /v1/skala/{id}/{approved-version}/evals.
2. Record THREE consecutive complete fixture eval runs through POST
   /v1/skala/zenas.rule_card/1.1.0/evals and POST
   /v1/skala/zenas.cite_check/1.1.0/evals, using the authorized operator identity.
   Require 11/11 and 17/17 respectively, eligible=true, matching package/case
   hashes, passing refusal cases and no regression against the approved suite.
   Fixture evals must not fall through to a live model.
3. Inspect the region's latest made-up-case gate: current Skala requires 50/50
   from answer_question on that box. If absent or failing, a separately
   authorized selftest is required. It can invoke models and is NOT part of
   the non-model proof or authorized execution here. No build-policy edits,
   corpus renormalisation or production SQL are performed by this work.
4. An authorized human reviews both new packages and the shared engine, then
   approves ONLY those two 1.1.0 versions individually via their /approve
   endpoints. Do not bulk-confirm unrelated candidates. This work grants no
   Skala approval and does not retire existing approved versions.

Final-head hosted CI must pass before code is declared ready to merge. No
production selftest, approval, deployment or corpus write was performed here.
