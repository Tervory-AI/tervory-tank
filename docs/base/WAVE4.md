# Base wave 4 prerequisites

F12: missing approved Base audit frame and exported specification in docs/figma.
Required frame: founder audit page, including empty, running, completed and failed
states; measured evidence, source/date, receipt and downloadable results. This is
a frame requirement, not approval of layout or visible wording. No audit page or
UI copy is added by wave 4.

F5: the named enthec/webappanalyzer fingerprint dataset is GPL-3.0, not MIT.
Upstream: https://github.com/enthec/webappanalyzer/blob/main/CONTRIBUTING.md
Base already vendors independently authored MIT OpenTechalyzer fingerprints at
commit a3d30e479c91c06732ef88867d69b7feef8f3f35, with original source and license in
base.site_signals/1.0.1/data. Detection reads fetched site HTML and headers without
additional requests. The explicitly requested MIT WebAppAnalyzer source remains
unavailable; it is not silently substituted or relicensed. Reviews remain absent.

No Google Places, paid feeds or carrier lookup is added. Engine SOT and compliance
flags remain empty. The phone candidate requires Skala approval before runtime
selection; wave 4 does not change lifecycle state or approved versions.

## Implemented and review locations

Branch: `codex/base-w4`, created from `origin/main` at `c4e1395e`.
No main merge, force push, PR creation, label change or merge was performed.

| File and line | Change |
| --- | --- |
| `tank/skills/base.contacts/1.4.0/run.py:153` | New minor candidate; complete metadata line-type mapping, validity and observed ISO region, retaining contact provenance. |
| `tank/skills/base.contacts/1.4.0/skill.yaml:1` | Version and candidate contract; no lifecycle/approval changes. |
| `tank/skills/base.contacts/1.4.0/CHANGELOG.md:1` | New minor behavior and limitations. |
| `tank/skills/base.contacts/1.4.0/evals/cases.jsonl:1` | 25 offline cases, including invalid/unparseable abstentions and must_refuse evidence. |
| `tank/skills/base.contacts/1.4.0/data/PHONE_PROVENANCE.md:1` | Pinned Apache-2.0 phone metadata source and no reachability/carrier claim. |
| `tank/skills/base.contacts/1.4.0/data/UPSTREAM.txt:1` | Existing disposable-email dataset provenance copied into the self-contained candidate. |
| `tank/skills/base.contacts/1.4.0/data/LICENSE.txt:1` | Existing CC0 disposable-email license copied, trailing spaces removed. |
| `tank/skills/base.contacts/1.4.0/data/disposable_email_blocklist.conf:1` | Existing pinned disposable-email data copied unchanged. |
| `tank/base_evidence.py:214` | Region follows the same exact observed-contact source/date guard as phone quality. |
| `tank/base_compare.py:16` | Saved-list and attachment arguments; bounded UTF-8 Apollo CSV parsing, exact unique matching, both unmatched groups and field agreement. Owned tenant/user upload and tenant list checks precede the $0 receipt. |
| `tank/command.py:42` | Expose `base.compare.apollo` to Base; GET adapter at line 1468, outside confirmed-dispatch mutation sets. |
| `tank/main.py:4245` | Register the comparison read router. No routing/model/queue/cache behavior changed. |
| `agents/base/engines/ffl/__init__.py:1` | Explicit FFL package boundary. |
| `agents/base/engines/ffl/manifest.json:1` | Existing entrypoints, versioned Skala assets and byte hashes; existing code/data remains in place. Empty SOT/compliance flags. |
| `agents/base/engines/scaffold.py:9` | Offline new-vertical scaffold; rejects invalid identifiers and existing directories. No activation. |
| `agents/base/engines/template/__init__.py:1` | Empty unregistered vertical package template. |
| `agents/base/engines/template/manifest.json:1` | Neutral manifest with no invented mappings, records, skills, SOT or compliance flags. |
| `agents/base/engines/README.md:1` | Package boundary, scaffold invocation and activation prerequisites. |
| `tests/test_base_wave4.py:1` | Phone/eval, Apollo totals/agreement/ambiguity/ownership/receipt/adapter/card, FFL byte inventory and scaffold regression tests. |
| `tests/base_compare_apollo.cjs:1` | Founder and client card proof using existing Total, Cost, Summary and Records labels. |
| `docs/base/WAVE4.md:1` | F5 licence mismatch, F12 missing frame, per-file handoff and verification. |

## Verification

All checks use synthetic/recorded evidence, no paid feeds, real model calls or live
writes. PostgreSQL proofs use disposable loopback databases with separate worker
copies; no production database or credentials are accessed.

- Full Base: `python -m pytest -q tests/test_base*.py --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1 --timeout=300 --timeout-method=thread -n 4 --dist loadfile --max-worker-restart=0 -rs`, with `BASE_TEST_DATABASE_URL` and `POOL_SCHEMA_DATABASE_URL` pointing to the isolated local fixture.
- Command/token: same options, selecting `tests/test_command.py tests/test_command_code.py tests/test_personal_tokens.py`, with the isolated local fixture.
- Phone candidate: Skala `run_evals`, offline HTTP stub and a model function that raises on any call: **25/25, eligible=true, cost_usd=0**.
- Final parser/card/scaffold focused run: **17 passed**, 3 warnings.
- Earlier broad focused run: **173 passed, 31 skipped**, 3 warnings. The skips required the optional local PostgreSQL fixture, subsequently supplied to the full Base run.

CI tank/workspace results are pending Claude opening the new branch's PR. No PR
exists for this branch at handoff. No founder `/chats` session or live browser proof
is claimed. The phone candidate still requires the existing Skala approval flow.
