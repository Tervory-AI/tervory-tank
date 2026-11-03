# Autumbra A3 — reviewed Cloudflare hand for tervory.com

Same branch and PR #566. Main is merged; founder commit b4db25f5 and its
.gitleaksignore entry are retained. The founder merges and performs live
acceptance. CI tank is the full-suite test of record; its result for the final
head is recorded in the GitHub PR body after CI completes, without another push.

Enforce uses only the fixed API proxy and the code-allowlisted zone, with its
setting and project health observer configured. The observer has a separate
proxy/network, fetches only the project's allowed health URL, and writes signed
results to a volume Enforce mounts read-only. No direct connection fallback,
other client zone, model call, page, copy, sign-in or production SQL is added.

## Review fixes and source locations

1. `agents/ghost/cloudflare_edge.py:29`: GET /health replaces CONNECT probes.
   Health probes consume no upstream tunnel allowance. The default remains
   **6 tunnels/minute**; the offline test forces one fresh tunnel per API call
   and completes propose/approve/Undo in **5**, plus 20 quota-free health probes.
   No rate increase is necessary. `agents/ghost/enforce_apply.py:34` pins approval
   and Undo to durable shield control metadata even during probe/config outages.
   `agents/ghost/threat_queue.py:494` preserves failed operations for retry with
   the existing fixed Cloudflare error. A failed automatic Undo retries the
   owned Undo, rather than replaying an already completed approval or apply.
2. `agents/radix/egress.py:218` adds opt-in `require_sni=False`;
   `agents/radix/egress.py:300` reuses OpenSSL's ClientHello parser, with bounded
   bytes and a five-second deadline. No certificate or key is created. Only
   an exact SNI match admits the original bytes to the pinned upstream; TLS
   remains end to end. Mismatched, missing, case-changed, trailing-dot SNI,
   plaintext and truncated handshakes are refused. Tests cover TLS 1.2/1.3,
   partial TCP delivery and fragmented TLS records. Radix's default behavior
   and limits are unchanged. Both proxies opt in at
   `agents/ghost/docker-compose.enforce.yml:60` and line 105. CI Compose sends
   ClientHellos and proves rejected SNI as well as host/network isolation.
3. `agents/ghost/docker-compose.enforce.yml:29`: Enforce uses
   `SITE_NAME: ${SITE_NAME:-}`. The operations guide lists SITE_NAME as a
   founder-managed setting name without supplying its value.
4. `agents/ghost/site_health.py:99`: a blank secret or blank/unsupported site
   logs one fixed line once and sleeps without requests or exiting. A valid
   observer fetches only its project's SITE_NAME. Compose supplies the same site
   to the observer at line 90; `site_health.py:29` checks the project binding
   before live selection.
5. `agents/ghost/cloudflare_edge.py:151`: durable apply metadata includes its
   confirmation time. `agents/ghost/site_health.py:61` requires an authenticated
   result whose probe started strictly after that time, waiting up to 60 seconds.
   A pre-apply success never passes. A fresh failure or no qualifying result by
   the deadline triggers the existing automatic Undo. Both automatic apply and
   approval use this check through `enforce_apply.py:84`. The observer timestamps
   probe start, so an in-flight pre-apply request also cannot pass. Successful
   shield latency excludes later observation time; the health stage still
   records the full wait, and failed-health/Undo timing remains end to end.

The existing ownership-checked single-rule deletion, real-control boot
restoration, never-block list, client modes, action cap and one-tap Undo remain.
Watch's shields.py and safety constants are unchanged. All probes/tests are
offline with local fake upstreams; no deployment or live rule mutation is claimed.

TLS parser format references: [RFC 6066 section 3](https://www.rfc-editor.org/rfc/rfc6066#section-3)
and [RFC 8446 section 4.1.2](https://www.rfc-editor.org/rfc/rfc8446#section-4.1.2).

## Offline commands and results

Working directory: /workspace/codex-autumbra-a3. `.proof/run_review.py` wraps
pytest with the repository's `offline_suite.clean_env`, removes database
settings, and uses `--disable-socket --allow-unix-socket
--allow-hosts=127.0.0.1,localhost,::1`. No external inference is armed.

Review 1 command:
`/home/ammosync/.codex/tervory-integration-closure-evidence-20261101/venv-ci/bin/python .proof/run_review.py tests/test_autumbra_a3_review.py tests/test_autumbra_cloudflare_hand.py tests/test_autumbra_cloudflare_live.py`
Exit 0: **84 passed in 13.24s**.

Review 2 commands:
`/home/ammosync/.codex/tervory-integration-closure-evidence-20261101/venv-ci/bin/python .proof/run_review.py tests/test_autumbra_a3_review.py`
Exit 0: **17 passed in 7.50s**.
`/home/ammosync/.codex/tervory-integration-closure-evidence-20261101/venv-ci/bin/python .proof/run_review.py tests/test_bucket1_radix.py tests/test_radix_passive.py`
Exit 0: **48 passed, 6 skipped in 2.23s**; existing Radix opaque relay/pinned
network behavior remains covered with SNI admission off.

Review 3 command:
`/home/ammosync/.codex/tervory-integration-closure-evidence-20261101/venv-ci/bin/python .proof/run_review.py tests/test_autumbra_a3_review.py::test_project_site_is_a_founder_setting`
Exit 0: **1 passed in 0.16s**.

Review 4 command:
`/home/ammosync/.codex/tervory-integration-closure-evidence-20261101/venv-ci/bin/python .proof/run_review.py tests/test_autumbra_a3_review.py tests/test_autumbra_cloudflare_live.py`
Exit 0: **69 passed in 21.25s**.

Final offline command (all five fixes, both apply modes, retry and Radix):
`/home/ammosync/.codex/tervory-integration-closure-evidence-20261101/venv-ci/bin/python .proof/run_review.py tests/test_autumbra_a3_review.py tests/test_autumbra_cloudflare_hand.py tests/test_autumbra_cloudflare_live.py tests/test_bucket1_radix.py tests/test_radix_passive.py`
Exit 0: **182 passed, 6 skipped in 37.91s**. The deadline tests use a virtual
clock: a pre-apply success waits, a new success passes, a new failure undoes,
and no new result undoes at exactly 60 seconds. Proxy outages during Undo retain
the original rule/control and retry that Undo. No fixture claims a real Undo.

Static command:
`/home/ammosync/.codex/tervory-integration-closure-evidence-20261101/venv-ci/bin/python -m ruff check agents/ghost/cloudflare_edge.py agents/ghost/enforce_apply.py agents/ghost/site_health.py agents/ghost/threat_queue.py agents/radix/egress.py tests/test_autumbra_a3_review.py tests/test_autumbra_cloudflare_hand.py tests/test_autumbra_cloudflare_live.py tests/autumbra_cloudflare_hand/compose_probe.py --select E9,F`
Exit 0: **All checks passed!**
`git diff --check`: exit 0.

Earlier local iterations included an absent pytest-socket package (exit 4 in
the smaller environment), old Undo error expectations, and test assertions that
needed to include the newly added fragmented matching case. Each was corrected
before the final passing command above. These are not full-suite claims.
Historical local full-suite failures came from incomplete packages on this box;
the compact EVIDENCE.txt retains their summaries. Only CI tank on the final
head is the full-suite result of record. Only failures absent from origin/main
will be treated as A3 regressions.

## Founder acceptance remains outstanding

A2 production email, founder-managed Coolify settings (including SITE_NAME),
the clean deployed seal, and actual M24 browser screenshots remain outstanding.
The exact steps are in `docs/ops/AUTUMBRA-CLOUDFLARE-LIVE.md`. No live receipt,
inbox delivery, screenshot, or founder Undo proof is claimed. No token/secret
value was inspected or supplied, and no merge or deployment was performed.
