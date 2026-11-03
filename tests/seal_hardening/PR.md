# Seal hardening: private Tiger OCR, Base-owned rendering

The main Coolify application no longer runs the shared `tiger` browser. Tank sends PNG OCR to `tiger-ocr`, deployed in Tiger's existing raw-mode resource with only `tervory-gw-tiger-ocr`, no internet, no Tank key, no persistent volume, `/data` tmpfs, dropped capabilities and no-new-privileges. The existing `tiger_data` volume declaration stays; no server volume is deleted.

Base skills use their own authenticated browser for every execution context, including founder previews, Skala evals and model-free code candidates. The shared helper preserves Base's existing headers and browser policy. Base caller checks, preview permissions and eval gates are unchanged. The existing Tiger application, pool, OCR implementation and approved skill files are unchanged.

## Changes for review

- `agents/tiger/docker-compose.yml:93`: OCR service, 1 GiB memory limit, 256 MiB shm, 64 MiB `/data` tmpfs; external OCR corridor declaration at 127. Its only explicit setting is `TIGER_MAX_PAGES`.
- `docker-compose.yml:211`: remove old main-stack browser; `:279` OCR URL; `:290` Tank attachment; `:531` one-time internal-network declaration. Main and its regional copy redeploy because the root compose and Tank change; Tiger redeploys because its room compose changes.
- `tank/agent_skills.py:502`: one browser-binding helper; `guard_base_run` rebinds after task/free-pass processing without nesting HTTP adapters.
- `tank/main.py`: bind all Base contexts in `make_ctx` and the separate model-free candidate path. No routing, queue or cache policy changes.
- `ops/seal-check.sh:171`: exact OCR attachment and internal flag enforced. `EXPECTED_SEALED`, including `agent-tiger`, is unchanged. Existing Autumbra logic is preserved.
- `agents/check_isolation.sh:76,111`: old `tiger` DNS allowances removed; OCR allowed only on its dedicated corridor. The obsolete Base network inventory allowance is removed.
- `.github/scripts/deploy_changed.py:42,87`: `tiger/` changes deploy `agent-tiger`, rather than the main stack.
- `docs/cursor/ROOMS.md:7,27,61`: shared-browser descriptions replaced and founder network/deploy/acceptance steps documented.
- `.github/workflows/seal-hardening.yml`: build the unchanged Dockerfile, run disposable Compose runtime tests with every test network internal, and upload the log with peak memory. Dependency installation/build occurs before the offline runtime proof.

## Every Tank TIGER_URL reader

| Reader / execution path | Result |
| --- | --- |
| `tank/main.py:112-115` SKILL_ENV; copied by `make_ctx` | Defaults to `http://tiger-ocr:3000`; Base ownership immediately overrides it through the shared helper. |
| `tank/main.py` `_run_code_candidate` context | Base candidates also bind the Base browser; other skills keep the OCR URL. No model is invoked. |
| `tank/main.py` `_run_one_skill` founder preview and regular run | Uses `make_ctx`; all Base versions use the Base browser, regardless of caller. Existing gates retained. |
| `tank/main.py` `run_skill_evals` | Uses `make_ctx`; both Base skills use the Base browser, including revalidation contexts. |
| `tank/agent_skills.py:502-508,529` Base room runs | Same Base gateway, authenticated headers and HTTP policy as before; task headers are refreshed after task extraction. |
| `tank/skills/tiger.price_ocr/1.0.0/run.py:59`, `1.0.1/run.py:59-66` | `/ocr` on `tiger-ocr`. |
| `tank/skills/base.find_site/{1.2.0,1.3.0,1.4.0}/run.py` (`61,68,68`), `{1.5.0,1.6.0}/run.py` (`91,95`), `{1.7.0,1.7.1}/run.py:101-105` | Every Base context points to `base-browser-gateway/render`; no approved version is edited. |
| `tank/skills/base.scrape_site/1.1.0/run.py:19`, `{1.2.0,1.2.1}/run.py:39`, `1.3.0/run.py:42-46` | Same Base gateway override for every version and caller. |

`git grep -n '/render' -- tank/skills` finds only Base skill implementations. `tiger-ocr` reuses the unchanged application image: `/render` remains implemented there, but it cannot open public pages because the sole runtime network is internal. No page or product wording is added.

## Intentional updates to main-stack assertions

- `tests/test_agent1_isolation.py:47-48`: old main Tiger attachments become absence of `tiger` plus Tank's OCR URL.
- `tests/test_tiger.py` former `458-467`: only Tank/Postgres/Hermes join the Tiger corridor; old Tiger service absent; OCR URL checked; old volume remains.
- `tests/test_tiger.py` former `484-487`: OCR-only DNS allowance replaces shared-browser allowance; `tiger` cannot resolve.
- `tests/test_b3_base_room.py:317-318`: old browser corridor assertions become old-service absence and Tank OCR attachment; obsolete Base DNS/network inventory expectations also updated.
- `tests/test_room_seal.py`: OCR is a sealed raw-mode service. Fixture passes with its one internal network and returns `LEAK` for either extra internal or extra outbound attachment.
- `tests/test_deploy_changed.py`: all four Tiger image-source paths deploy the Tiger room, with combined Tank changes still deploying main.
- `tests/test_seal_hardening_routes.py`: both specified Base versions actually execute a render-required preview, eval and Base-room run against mocked HTTP, with Base headers; no render goes to OCR. The OCR skill reaches its new `/ocr` URL.

## Verification status — not acceptance

Exact commands/results and raw logs are recorded in `VERIFICATION.txt` once the runs finish. Current results:

- Routing: **7 passed**, including both skills in preview/evals/Base-room modes and OCR routing.
- Initial related suite: **203 passed, 1 failed**; the failure was an obsolete Base isolation assertion, corrected.
- Related rerun: **209 passed, 2 failed**; two existing Rig fixture subprocesses timed out at 30 seconds under host load above 50. Separate rerun: **6 passed**, 87 deselected.
- Ruff (`E9,F`, existing approved-skill F401 exception only) and `git diff origin/main --check`: passed.
- Offline image build with `--network=none`: failed because the dependency-install layer was not cached. Local Compose proof uses the existing main-head Tiger image; CI builds the unchanged Dockerfile.
- First Compose proof: network denials passed; price comparison failed because the OCR image does not contain Tank's `selectolax` dependency. The probe now parses on the test runner with Tank's pinned existing dependency.
- Second Compose proof: network denials passed; OCR comparison exceeded its 30-second probe request timeout on the busy host. Probe-only timeout now allows 120 seconds; production timeouts are unchanged.
- Third Compose proof: OCR exited at startup. Diagnostics were not retained by that run; the probe now captures its disposable service logs before cleanup on failure.
- Full Tank offline suite: running; failures and a timed-out worker have been observed. **No green full-suite result is claimed.**
- CI Compose peak memory: **pending**. No peak is invented. Claude opens the PR; this new workflow runs on that PR, and its log/peak must be added here.

Main was merged before every push. Fresh main `8299ff94` merged cleanly, preserving both sides, while verification was in progress. Final-head verification is still required after all changes finish.

## Founder steps and remaining acceptance proof

Before deploy, once:
```sh
docker network create --internal tervory-gw-tiger-ocr
```
Keep Tiger's existing Raw Compose Deployment enabled. Founder merges; Claude opens the PR. No PR merge, production network creation, deployment, production SQL, live-data mutation, or old-volume deletion has been run by this branch.

After the authorized deploy:
1. In `/chats`, founder runs `tiger.watch` and `tiger.read` on a page needing OCR and sees prices. **Founder screenshots pending; none fabricated.**
2. On the host, `bash ops/seal-check.sh` must print `agent-tiger ... sealed` and exit 0. **Live output pending; fixture output is not host proof.**
3. In Coolify, main app no longer lists a `tiger` container. **Founder verification pending.**

Tests passing alone does not complete this job.
