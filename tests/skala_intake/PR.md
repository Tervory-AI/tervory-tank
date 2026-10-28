# Version Trigger's free checkers and Tiger's playbook through Skala

Trigger and Tiger currently execute these rules from room files. This change
packages the merged rules as rung-3 skills and switches each room operation to
Skala only after founder approval. Before approval, the existing implementation
continues to produce the same results. An approved execution failure is surfaced;
it never silently falls back to room code. Approval and rollback are resolved on
every call, with no cached version selection.

Branch: `codex/skala-intake-trigger`. Started from main `3f469b0`, which includes
Tiger #391 and Zenas #394. No GitHub API was used. Each finished repository file
was committed and pushed separately. Claude opens the PR; no PR, merge or deployment
was performed in this lane.

## What changed

- Seven `1.0.0` packages under `tank/skills/`: `skill.yaml`, `run.py`,
  `evals/cases.jsonl`, `CHANGELOG.md`, and pinned implementation/data. Each has
  `rung: 3`, no model task, and a 100% eval threshold.
- `agents/_chassis/chassis/tank.py:37`: approved-version resolution through the
  existing Skala endpoints. Only the explicit "no approved version" response
  permits legacy execution. Authentication, network, execution and approval-race
  failures do not activate a fallback.
- `agents/trigger/checkers.py:45,103`, `service.py:47,53`, `app.py:59,64`:
  per-checker switching, tenant voice forwarding and existing report output.
  Approved sections skip their room implementation; mixed approval is supported.
  The report retains skill/receipt references for audit without new UI text.
- `agents/trigger/app.py:72`: authenticated raw transport to the existing private
  LanguageTool service. The package owns response interpretation and checks the
  declared image pin, service version/build and configuration hash. No public
  LanguageTool endpoint, new network or new secret.
- `agents/tiger/app.py:125`, `watch.py:1133`, `domain_playbooks.py:121`:
  approved public-page eligibility, layout reading and state-transition rules.
  Persistence and transaction locks remain in Tiger. Shared state remains public
  layout hashes; tenant observations remain separate.
- `tank/skala_intake.py:23,54`: background evaluation of only these seven new
  versions, using the existing Skala eval recorder. Passing evidence is reused;
  approved/retired versions are untouched. Pending evaluations retry up to ten
  times, 30 seconds apart, for room startup. This never approves a version.
- `tank/main.py:3126,4182`: refuse room-key preview bypass for these skills and
  register the intake startup/shutdown hook. No routing, cache or queue changes.
- `tank/requirements.txt`: pin the native `google-re2==1.1.20251105` dependency.
  The existing Dockerfile's `COPY *.py` includes `skala_intake.py`.
- No schema changes, constructed SQL additions, Workspace changes, or edits to
  `zenas.scope/1.2.0`.

## Eval counts and evidence

All **157/157 cases pass**, at threshold **1.0**, with zero model calls and zero
model cost. The real Skala eligibility check includes passing refusal evidence.

| Skill | Version | Cases | Score | Fixture basis |
| --- | --- | ---: | ---: | --- |
| trigger.proselint | 1.0.0 | 23 | 100% | Existing room example and pinned upstream offline examples |
| trigger.languagetool | 1.0.0 | 22 | 100% | Saved "This are a test" grammar fixture, singular/plural contrast pairs, input refusals |
| trigger.agent_style | 1.0.0 | 21 | 100% | Pinned RULE-05/06 examples, clean/boundary contrasts, refusal |
| trigger.house_style | 1.0.0 | 22 | 100% | Existing selected-book terms, word boundaries, descriptive links, all 11 books |
| trigger.readability | 1.0.0 | 22 | 100% | Existing passive/sentence/fence fixtures and threshold contrasts |
| trigger.voice_check | 1.0.0 | 21 | 100% | Existing banned/required/preferred terms, case/phrase boundaries, absence and refusal |
| tiger.playbook | 1.0.0 | 26 | 100% | #391 saved public shop pages, private-page refusals, promotion/retirement/stale generations |

`ready.json` captures the disposable database's actual staging rows and bulk
approval preview. Its exported token is replaced with the literal
`offline-preview`; no live approval token is stored. `approved.json` is the actual
offline bulk-confirm result. No fixture is loaded into a production database or
live screen.

`languagetool-responses.json` contains responses captured from the exact pinned
internal container for the 20 grammar inputs. Their expected rule IDs were
asserted during capture. The offline test transport replays these responses;
production package code accepts only text and cannot accept injected matches.
Startup evals use the real private service, never these test responses.

## Pins, licences and decisions I made

- **Current main contains Trigger's first build, not its second-build house-style
  module.** `trigger.house_style` therefore packages the merged selected-stylebook
  checks. It does not introduce an unmerged house default or change no-voice
  behavior. The eleven stylebooks are all included; books with no implemented
  mechanical rule do not acquire invented checks.
- Preserve the merged checker implementation in each package. `rules.zip` is
  package data, including tool source, rule files, voice format and full upstream
  attribution/licences. `run.py` enforces its SHA-256, which is included in Skala's
  source/evidence fingerprint. Each invocation uses an isolated Python process,
  so different approved versions cannot reuse each other's imported rule modules.
- Proselint: source `a83a6164999803909f69eb3274d783c7070e73c1` / 0.16.0, BSD.
  The native regex dependency and Pydantic 2.10.6 are checked at execution;
  dependency drift fails closed instead of changing approved behavior.
- Agent-style: `d1bdb0fa0c6305942bf43805edeae330946e8cf7`, rules CC BY 4.0,
  scripts MIT. Existing code checks remain RULE-05, 06, 12, A, B, C, D, E.
  **Skipped:** RULE-01, 02, 03, **04**, 07, 08, 09, 10, 11, F, G, H, I.
  No semantic detector or model scorer is introduced.
- Agent-stylebooks: `85b318fcb69fbb50b9f066aadf81750d368c6988`, MIT.
  Package data includes 18F, Apple, GitHub, GitLab, Google, GOV.UK, Kubernetes,
  Mailchimp, MDN, Microsoft and Red Hat. Their original upstream guidance is not
  represented as newly relicensed material.
- Practical Prose: `fc0b2a725dd3d8b0dd347f92058b184a01eac44d`, rubric CC BY 4.0,
  code MIT. Preserve the existing code checklist/fence check; never its scorer.
- Brand Voice Spec: Hugging Face dataset revision
  `e9d26dbecb2a0d5c023d4fb8d8f954e0ca4cdd54`, CC BY 4.0. Format only; no coffee
  example, imported tenant data or invented tenant rules.
- Readability owns sentence length (including RULE-12), passive candidates and
  the existing Practical Prose fence check. Agent-style excludes RULE-12 from its
  output; voice_check owns banned/required terms. This prevents duplicate findings.
- LanguageTool: `meyay/languagetool:6.8-13@sha256:062924c66c649d706d60aed80af6bab207bb50a053733e7ac1ca0d8446d150f1`,
  LGPL, pinned in `service.json`. Existing 2 GiB container / 1536 MiB Java heap;
  budget at least 3 GiB additional box memory for Trigger plus LanguageTool.
  The container remains private and its configuration is unchanged.
- Rollback uses Skala's existing previously-approved-version rule. The test creates
  1.1.0 only in a temporary directory, approves it, then restores 1.0.0 and verifies
  subsequent room calls select it. No fake historical version ships. Future
  dependency/image upgrades must preserve the pinned runtime needed by older
  versions; this build fails closed on incompatibility.

## Exact verification commands and results

All commands ran in the saved cloud environment, in `/workspace/tervory-tank`.
The saved `/tmp/trigger-venv` supplies the pinned repository test dependencies.
The Docker test uses the saved `trigger-first-build:test` Python image with the
current repository and test packages mounted; this is **not** a fresh Tank image
build or production validation.

```bash
PYTHONPATH=tank:. /tmp/trigger-venv/bin/pytest -q \
  tests/trigger_first_build/test_trigger.py \
  tests/tiger_playbooks/test_playbooks.py --tb=short
# 42 passed, 12 skipped (database/live-service fixtures), 1.31s

PYTHONPATH=tank:. /tmp/trigger-venv/bin/pytest -q \
  tests/test_agent_chassis.py tests/test_skala_approval_safety.py \
  tests/test_skala_eval_contract.py tests/test_skala_eval_record.py \
  tests/test_skala_call_cost.py tests/test_tank_boots.py tests/test_room_seal.py --tb=short
# 183 passed, 16 skipped (optional database/service fixtures), 54.52s

docker exec skala-intake-pg createdb -U postgres intake_final
docker run --rm --network skala-intake-test \
  -v /workspace/tervory-tank:/workspace/tervory-tank \
  -v /tmp/trigger-venv/lib/python3.12/site-packages:/test-packages:ro \
  -v /tmp:/proof -w /workspace/tervory-tank \
  -e PYTHONPATH=/test-packages:/workspace/tervory-tank/tank:/workspace/tervory-tank \
  -e SKALA_INTAKE_TEST_DATABASE_URL=postgresql://postgres@skala-intake-pg/intake_final \
  -e SKALA_INTAKE_PROOF_DIR=/proof/skala-intake-proof \
  --user 0 trigger-first-build:test python -m pytest -q \
  tests/skala_intake/test_intake.py --tb=short
# 21 passed, no skips, 113.81s; includes real persisted approval and rollback.

SKALA_ESBUILD_PATH=/tmp/trigger-browser-tools/node_modules/esbuild \
SKALA_PLAYWRIGHT_PATH=/tmp/trigger-browser-tools/node_modules/playwright \
node tests/skala_intake/browser.mjs
# PASS: unchanged Skala UI, seven 100% code skills, bulk confirmation, 1440px and 375px

/tmp/trigger-venv/bin/ruff check tank/skala_intake.py tank/skills/trigger.* \
  tank/skills/tiger.playbook tests/skala_intake agents/trigger/checkers.py \
  agents/trigger/app.py agents/trigger/service.py agents/tiger/app.py \
  agents/tiger/watch.py agents/tiger/domain_playbooks.py \
  agents/_chassis/chassis/tank.py --select E9,F
# All checks passed.
git diff --check
# Passed.
```

The disposable services used `docker network create --internal skala-intake-test`,
`postgres:16` with trust authentication only on that isolated network and no host
port, and the exact LanguageTool digest above with the shipped configuration,
2 GiB memory limit, read-only root, no capabilities and no public port.
No production SQL was run.

Earlier harness attempts exposed a missing repository root on PYTHONPATH, missing
isolated Tank import settings, and a temporary rollback package directory without
its skill-id parent. Those test setup errors were corrected. One initial eval
incorrectly assigned the descriptive-link fixture to GOV.UK; the merged checker
implements that rule for Google/GitHub, so the fixture now selects Google. No
rule was changed to make that expectation pass.

Security commands used the repository's pinned CLI installer and baseline
`3f469b0`:

```bash
RUNNER_TEMP=/tmp/skala-intake-security \
GITHUB_PATH=/tmp/skala-intake-security/path bash .github/scripts/install-security-tools.sh
PATH=/tmp/skala-intake-security/security-bin:$PATH \
python .github/scripts/security_scan.py gitleaks --base 3f469b0 \
  --output /tmp/skala-intake-security/results
# Clean.
RUNNER_TEMP=/tmp/skala-intake-security GITHUB_WORKSPACE=/workspace/tervory-tank \
PATH=/tmp/skala-intake-security/security-bin:$PATH \
python .github/scripts/security_scan.py semgrep --base 3f469b0 \
  --output /tmp/skala-intake-security/results
# Incomplete: no report, exit 2. Not claimed clean.
PATH=/tmp/skala-intake-security/security-bin:$PATH \
python .github/scripts/security_scan.py osv --base 3f469b0 \
  --output /tmp/skala-intake-security/results
# Incomplete. Focused diagnostic: api.osv.dev/v1/querybatch returns Forbidden.
RUNNER_TEMP=/tmp/skala-intake-security GITHUB_WORKSPACE=/workspace/tervory-tank \
/tmp/skala-intake-security/security-bin/semgrep scan \
  --config agents/radix/scanlib/semgrep.yml --metrics off --disable-version-check \
  --disable-nosem --baseline-commit 3f469b0 --json \
  --output /tmp/skala-intake-security/local-rules.json .
# Bundled rules: zero findings, zero errors; includes constructed-SQL rules.
```

## Acceptance still required

CI starts when Claude opens the PR. Full CI security scans, the normal deployment
and the founder's own browser test are **pending**. No CI-green, production-ready
or live acceptance claim is made.

After authorized deployment of Tank and the two rooms, the founder should see the
seven evaluated versions in Skala, choose **Approve all ready**, confirm the
listed versions, and check/draft through Trigger in `/chats`. Before approval the
room retains its existing behavior; after approval the checker receipts identify
the approved packages. Check that pasted text produces checker issues with no
model call. The existing first-build requirement for a tenant voice before
writing is preserved.

## What changed, tests and screenshots

- Changed: seven pinned code packages and their authenticated room integration;
  the existing founder approval interface is unchanged.
- Tested: 157 package cases, 21 intake tests with real local Postgres, 42 room
  regressions and 183 chassis/Skala/boot/isolation checks; limitations above.
- Screenshots below are **offline browser proof using captured test-database
  results**, not screenshots of the founder's live session. Live screenshots
  remain outstanding under rule 11.

| State | Desktop | Mobile |
| --- | --- | --- |
| Ready, scores visible | [1440px](ready-1440.png) | [375px](ready-375.png) |
| Existing bulk confirmation | [1440px](bulk-1440.png) | [375px](bulk-375.png) |
| Approval recorded | [1440px](approved-1440.png) | [375px](approved-375.png) |
