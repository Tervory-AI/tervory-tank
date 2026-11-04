# Moot wave 4

Branch codex/moot-w4 starts from origin/main at 981ac096. No main merge.

Gate 1 reuses the existing AIExecutor, founder-operated hearings, TankClient,
persistent HearingStore, publication projection and public unverified reader.
No new page, UI wording, provider, key, audio service or model bypass is added.

The source builder previously labelled any worked civil case a civil appeal.
It now requires stored appeal=true; false, unknown, string and integer flags are
refused. Criminal matters still hit the existing civil_only gate first. The
source chooser now limits suggestions to decided appeals and filters criminal
metadata; the full source quote, tenant, region and holdout checks remain at
creation/edit time.

Gate 1 checks: test_sources.py and test_api.py, network disabled: 14 passed,
5 database-dependent tests skipped. The durable database path is checked in gate 2.
Required exact repository CI lint passes before push.

Model task types remain moot.counsel and moot.judge through Tank. The existing
policy seeds use rung 1 / luna; a seed is not evidence that the live cheapest
quality threshold passed. No real model call is made for coding/checking, no
price or model-quality result is invented, and no policy is promoted without
actual evaluated evidence. Offline scripted responses prove wiring/guards only.

## Gate 2: saved all-AI match and public reader

The existing court-source recording for Kuzwayo v Estate late Masilela [2010]
ZASCA 167 supplies paragraphs 3–5 (facts), paragraph 27 (source-backed legal
passage), and the separate recorded order. No new source feed or live fetch is
introduced. The recording is already in tests/fixtures/za/precedent and its
original court listing is recorded in tests/fixtures/za/archive.

The new offline test installs that recording in an isolated court pool/worked
matter, creates an all-AI hearing through the existing API, starts its swapped
pair, and drives both counsel and the judge through the REAL chassis TankClient
against a recorded HTTP transport. Eight /v1/route requests use moot.counsel and
moot.judge; none selects a model in room/browser code. Both hearings persist
transcripts/receipts and publish atomically through the existing HearingStore.
The public regional reader returns two saved matches, labelled unverified.
The actual holding/bench notes never reach the model context. Unknown costs and
settings remain unknown. This scripted run is not a model-quality evaluation.

Criminal source metadata is refused before any model request, including explicit
criminal metadata with a civil-looking SA caption. Unknown/non-boolean appeal
flags are refused; a trial case is never relabelled as an appeal. Foreign region,
tenant/holdout and unsupported-source quote guards remain in place.

The existing reader did not actually contain a visible unverified label on main.
The requested exact word is now present on the public index and match reader,
and watch_payload always supplies verificationStatus=unverified. A stored value
claiming verified cannot change the visible label. No other UI wording/page is
added. Public source verification is not a verification of the AI's legal result.

### Founder operation using existing controls

1. Open the Moot court panel in Zenas, in the home region holding the case.
2. Select a stored, decided Civil appeal. Keep applicant, respondent and judge
   selectors on their existing AI choice. Create hearing.
3. Review its source-backed facts/issues and lock the problem. Start the hearing.
   The existing AI controller advances turns through Tank. A failed or uncertain
   call is not blindly repeated; use the existing explicit continuation/recovery
   controls after inspecting its state.
4. Complete the existing swapped-seat run. Both sides must submit before a ruling;
   paired publication waits for both hearings. The judge can remain uncertain on
   insufficient evidence rather than inventing a confident winner.
5. Use Publish paired hearings. Until publication the public reader returns no
   match. Published matches appear at /moot in that region and retain unverified.

No live match, public fixture, actual provider call or founder browser completion
was created or claimed. A genuine stored source must be present at runtime.

### Model-cost evidence still required

The existing policy seeds are rung 1 / luna, but live routing remains entirely
Tank-owned and may differ from seeds. The repository provides no evaluated Moot
candidate/model-cost comparison establishing the cheapest sufficient legal
quality. The standing prohibition on real model calls for coding/checking is
preserved. Consequently this gate does NOT claim to have proven or promoted a
cheapest passing model, and it changes no policy/price/approval row. The actual
Tank-recorded candidate evaluation is still required for that part of the brief;
scripted responses, quote gates, or the court's known outcome cannot substitute
for it. Existing reasoning.py also explicitly distinguishes structural grounding
checks from correctness of legal reasoning.

### Verification and files

Full offline Moot + execution-receipt regression: **131 passed**, 14 warnings,
27.86s, no skips. Uses disposable loopback PostgreSQL databases and no provider
credentials/calls. Exact invocation, with MOOT_TEST_DATABASE_URL ending in _test
and POOL_SCHEMA_DATABASE_URL pointing only to the local fixture:

    python -m pytest -q tests/moot_hearing tests/test_moot*.py tests/test_execution_receipt.py --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1 --timeout=180 --maxfail=2

Required repository lint before each push:

    ruff check tank tests --select E9,F --per-file-ignores "tank/skills/base.socials/1.0.0/run.py:F401"

Result: All checks passed!

| File and line | Change |
| --- | --- |
| agents/zenas/core/moot/hearing_sources.py:42 | Criminal metadata/caption guard; :54 requires stored appeal=true before constructing the source-quoted problem. |
| agents/zenas/core/moot/hearing_api.py:66 | Existing chooser limits suggestions to decided appeals and excludes criminal records; creation still revalidates the full stored source. |
| agents/zenas/core/moot/session.py:139 | Public match verificationStatus is always unverified. |
| workspace/app/moot/WatchPanel.tsx:25 | Required literal unverified label, independent of stored verification claims. |
| workspace/app/moot/page.tsx:37 | Same requested label on each published index entry. |
| tests/moot_hearing/test_sources.py:19 | Appeal fixtures and negative unknown/trial/criminal metadata regressions. |
| tests/moot_hearing/test_wave4.py:1 | Recorded real appeal through source selection, API, TankClient, paired AI seats, storage and publication; no direct model selection/calls. |
| tests/moot_hearing/public_label.cjs:1 | Server-rendered reader stays unverified even with a forged verified input. |
| docs/moot/WAVE4.md:1 | Gates, evidence, founder controls and unresolved real model-quality/cost evaluation. |

Code under agents/zenas deploys the Zenas room on merge under the existing deploy
rules. No runtime configuration, auth, routing ladder, schema or paid provider is
changed. Claude owns PR creation/review/merge; no PR is opened by this task.
