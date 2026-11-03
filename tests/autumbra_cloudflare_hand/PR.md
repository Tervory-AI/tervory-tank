# Autumbra A3: the Cloudflare hand for tervory.com

PR #566; branch `codex/autumbra-cloudflare-hand`. Claude's main merge
`53814105` was retained. Latest main was merged cleanly as `e70638ee`.
Founder merges; no merge to main or deployment was performed by this task.

Enforce previously stayed on the fixture even with its Cloudflare setting
configured. The founder's 3 November 02:47 PT approval now permits the real
control only through the fixed API proxy, for the code-allowlisted zone, with
signed site health configured. An absent token, disallowed zone, unavailable
proxy or unconfigured observer keeps the fixture. There is no direct fallback.

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
  health mount. Line 48 API proxy, line 74 observer, line 92 health proxy.
  Radix's existing Proxy/Server/image are reused with storage disabled and the
  approved default limits unchanged. Separate outbound/private networks; proxies
  bind their private NIC and publish no ports. Line 120 gives the health volume
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
  scripts and full results, including failures, rather than a green-suite claim.

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
`git diff --check` pass. Full commands and outputs are in EVIDENCE.txt.

CI Compose proof after the socket-binding review fix:
[successful run on e1d64827](https://github.com/Tervory-AI/tervory-tank/actions/runs/41626330407).
Both viewpoints prove their allowed tunnel works and refuse the other proxy,
other hosts, direct egress, Tank and another client's network. Fake upstream
bindings were changed from wildcard to their exact private addresses in response
to the CodeQL review comment. No review finding is disputed.

The initial full Tank diagnostic was **not green**: its main pytest group
reported **218 failed, 4992 passed, 638 skipped, 97 errors** in 965.09 seconds;
its wrapper exited 143. This started before two A3 test/config fixes and used an
incomplete local environment. The two isolated groups failed collection for
missing `aiosmtpd`. All initial output is retained. A second full run uses the
existing complete CI environment; its result will be appended when available.
Neither missing dependencies nor earlier failures are represented as passing
final-code proof.

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
