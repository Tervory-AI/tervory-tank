# Autumbra A3: the Cloudflare hand for tervory.com

PR #566; branch `codex/autumbra-cloudflare-hand`. Claude's main merge
`53814105` was retained. Founder commit `b4db25f5` is retained, including its
`.gitleaksignore` entry. Latest main `b2fa83bd` merged cleanly as `b835204b`.
Founder merges; no merge to main or deployment was performed by this task.

Enforce previously stayed on the fixture even with its Cloudflare setting
configured. The founder's 3 November 02:47 PT approval now permits the real
control only through the fixed API proxy, for the code-allowlisted zone, with
signed site health configured. An absent token, disallowed zone, unavailable
proxy or unconfigured observer keeps the fixture. There is no direct fallback.

## Egress proposal — approved and implemented

The approved path reuses Radix Proxy/Server and its image, storage disabled,
fixed to `api.cloudflare.com:443`, on Enforce's internal network plus its own
outbound network. The second proxy is fixed to `tervory.com:443` on the separate
observer network and a separate outbound network. Neither publishes a port;
both bind only their private NIC. The proposal's HTTPS_PROXY/NO_PROXY settings
are retained, while Cloudflare always uses its explicit transport with
trust_env=False. Radix limits are unchanged.

## Changed files and source locations

- `agents/ghost/cloudflare_edge.py:21`: fixed explicit
  `httpx.HTTPTransport(proxy="http://egress-proxy:8080")`, no retries/direct
  fallback; private proxy tunnel probe at line 28. Constructor accepts only that
  transport or the offline MockTransport. Rulesets apply and ownership-checked
  single-rule Undo remain in this PR's adapter at line 56.
- `agents/ghost/enforce_apply.py:34`: all four runtime gates and actual control
  receipt metadata; existing modes, never-block checks and health Undo retained.
- `agents/ghost/enforce_app.py:124`: real control restoration from durable records;
  line 176 retains the selected control for queue processing. Empty queue polls
  do not spend the approved proxy tunnel allowance.
- `agents/ghost/site_health.py:27`: bounded HMAC validation, exact site/URL,
  freshness <=30 seconds, failed/absent/unsigned health false. Line 52 sends only
  a bodyless GET, discards response bodies, clears cookies and follows no
  redirects. Line 70 writes one atomic signed result every 15 seconds from the
  separate observer. No queue/data mount, no Enforce input.
- `agents/ghost/docker-compose.enforce.yml:10`: Enforce settings and read-only
  health mount. Line 50 API proxy, line 76 observer, line 94 health proxy.
  Radix's existing Proxy/Server/image are reused with storage disabled and the
  approved default limits unchanged. Separate outbound/private networks; proxies
  bind their private NIC and publish no ports. Line 122 gives the health volume
  a stable tenant-bound name.
- `ops/seal-check.sh:91`: collect project identity from read-only inspection;
  line 133 verifies exact logical networks, project ownership and Internal flags
  for Enforce, observer and both proxies. Missing required services fail.
- `.env.example:479`: token activation prerequisites; health setting name added
  with an empty value. Existing Cloudflare and TRIGGER_CRM blocks are retained.
- `docs/ops/AUTUMBRA-CLOUDFLARE-LIVE.md:1`: founder token scope/permissions, quota
  check, settings by name, deployment/seal, actual browser M24, evidence and kill
  switch. A2 email delivery is an explicit prerequisite.
- `tests/test_autumbra_cloudflare_hand.py:1`: existing 36 offline adapter/ownership
  tests from this branch. `tests/test_autumbra_cloudflare_live.py:1`: 46 additional
  checks for gates, HMAC/freshness, failure Undo, real boot restoration, proxy
  refusal/no direct fallback, one-way mounts and seal failures.
- `tests/autumbra_cloudflare_hand/compose_probe.py:1` and
  `.github/workflows/autumbra-cloudflare-hand.yml:1`: CI Compose network proof
  with local fake upstreams, using the production topology and proxy commands.
  Every test network is internal; DNS/connect injection is confined to CI fake
  upstream routing. No outside network or credential is used during probes.
- `tests/autumbra_cloudflare_hand/EVIDENCE.txt:1`: exact verification commands,
  exit codes, summaries and CI links; raw traces and infrastructure IDs removed.

## Proof and limits

All completed files were committed and pushed individually, with
`git merge origin/main` before every push. All pushes succeeded. A2 was fetched
and has not landed on main; its action cap, owner email and webhooks were not
changed. Empty protected-file diffs are recorded for `shields.py`,
`never_block.py` and `client_settings.py`. The action cap and one-tap Undo path
remain in place. No page, button, copy, Figma frame, sign-in, price or live
fixture was added.

Final Autumbra/Ghost/root boundary command: **446 passed, 3 skipped** (134.50 s).
Final room-seal command: **89 passed** (80.71 s). Ruff E9/F, shell syntax and
`git diff --check` pass. Commands, exit codes and summary lines are in EVIDENCE.txt.

CI Compose proof after the socket-binding review fix:
[successful run on e1d64827](https://github.com/Tervory-AI/tervory-tank/actions/runs/41626330407).
Both viewpoints prove their allowed tunnel works and refuse the other proxy,
other hosts, direct egress, Tank and another client's network. Fake upstream
bindings were changed from wildcard to their exact private addresses in response
to the CodeQL review comment. No review finding is disputed.

**CI's `tank` job is the full-suite test of record.** The result for the final
pushed head is recorded in this PR's body with the exact head SHA and CI job
link after the job completes. Updating that body does not create another head.
Only failures absent from `origin/main` are eligible for A3 fixes.

The local full-suite failures came from incomplete package installations on
this box, including `jsonschema`, `aiosmtpd`, `playwright`, `numpy` and other
required dependencies. Their compact diagnostic summaries remain in
EVIDENCE.txt; they are not attributed to A3 and do not replace CI's tank result.

After retaining the approved HTTPS_PROXY/NO_PROXY settings, the two Compose
contract checks passed (46.34 seconds), and the [network CI proof on
8b628518](https://github.com/Tervory-AI/tervory-tank/actions/runs/41628312785)
passed. Current main has been merged; A2 production email remains outstanding.

Read-only `bash ops/seal-check.sh` exited 1: existing Trigger network leaks;
no deployed Autumbra Watch/Enforce rooms were present. Passing Compose tests do
not claim a clean deployed seal. No production SQL, secret inspection, model
inference, Cloudflare mutation or live-data change was performed by this task.

## Founder acceptance still required

There are **no founder-test screenshots, live receipt, inbox delivery or live
Undo proof yet**. This is not DONE under the brief. The founder must merge,
provide setting values directly in Coolify, deploy, obtain a clean seal and
follow the operations guide. Current owner-email runtime remains the fixture
transport until A2 supplies production delivery; an inbox result cannot be
claimed from it. Screenshots must show the actual founder browser, matching
Cloudflare rule and receipt/timing/health, actual owner inbox, and rule absent
after the founder presses Undo. Secret values and signed-link tokens must not
appear in screenshots.

Clearing the token setting returns Enforce to the fixture on its next deploy;
it preserves real rule records and cannot pretend the fixture undid a real rule.

## Review fix 1 — tunnel budget and pinned control

`cloudflare_edge.proxy_answers` now uses GET /health. Approval and Undo select
from the shield's recorded control even when the probe is down; a fixed
Cloudflare error retains the action in the queue for retry. Durable ownership
and pending approval records are retained on failure. The API proxy remains at
Radix's unchanged limit of **6 tunnels/minute**: the regression forces one new
tunnel per API call and needs **5** for propose/approve/Undo; 20 health probes
consume **0** tunnels. No Enforce-specific rate increase is necessary.

Command: `/home/ammosync/.codex/tervory-integration-closure-evidence-20261101/venv-ci/bin/python .proof/run_review.py tests/test_autumbra_a3_review.py tests/test_autumbra_cloudflare_hand.py tests/test_autumbra_cloudflare_live.py`
Exit 0: **84 passed in 13.24s**. The wrapper strips provider credentials and
database settings and restricts sockets to loopback. An initial invocation with
the smaller local environment exited 4 because pytest-socket was absent; the
existing CI environment supplied it. One old expectation was updated to the
required fixed error when a real shield's token is unavailable.

## Review fix 2 — opt-in exact SNI admission

`agents/radix/egress.py` adds `Proxy(require_sni=False)`. Both Enforce proxies
opt in. OpenSSL's existing ClientHello parser reads bounded bytes with a
five-second deadline and admits only an exact `verified_host` SNI; it forwards
the original bytes unchanged and creates no certificate or key. Mismatched,
missing, case-changed and trailing-dot SNI, plaintext and truncated handshakes
are refused before opening the upstream connection. Radix defaults remain off.
The CI Compose probe now sends actual ClientHellos and checks rejected SNI too.
TLS layout references: [RFC 6066](https://www.rfc-editor.org/rfc/rfc6066#section-3)
and [RFC 8446](https://www.rfc-editor.org/rfc/rfc8446#section-4.1.2).

Command: `/home/ammosync/.codex/tervory-integration-closure-evidence-20261101/venv-ci/bin/python .proof/run_review.py tests/test_autumbra_a3_review.py`
Exit 0: **17 passed in 7.50s**.
Command: `/home/ammosync/.codex/tervory-integration-closure-evidence-20261101/venv-ci/bin/python .proof/run_review.py tests/test_bucket1_radix.py tests/test_radix_passive.py`
Exit 0: **48 passed, 6 skipped in 2.23s**, including existing opaque relay and
pinned-destination behavior with SNI admission disabled.

## Review fix 3 — project site setting

Enforce now reads `SITE_NAME: ${SITE_NAME:-}`. The operations guide lists
`SITE_NAME` among the founder's Coolify setting names without supplying a value.
Command: `/home/ammosync/.codex/tervory-integration-closure-evidence-20261101/venv-ci/bin/python .proof/run_review.py tests/test_autumbra_a3_review.py::test_project_site_is_a_founder_setting`
Exit 0: **1 passed**.

## Review fix 4 — idle unconfigured observer and project-only requests

With a blank/whitespace secret, blank SITE_NAME or unsupported site, the
observer logs one fixed line and sleeps without creating a request transport,
writing a result, or exiting. A configured observer fetches only this project's
SITE_NAME. Compose passes the same site setting to Enforce and the observer;
activation verifies that the observer is configured for the requested site.
Command: `/home/ammosync/.codex/tervory-integration-closure-evidence-20261101/venv-ci/bin/python .proof/run_review.py tests/test_autumbra_a3_review.py tests/test_autumbra_cloudflare_live.py`
Exit 0: **69 passed in 21.25s**. Tests cover three sleep cycles with one log line
and no request, unsupported/blank sites, and fetching only the selected site.
