# Autumbra Cloudflare hand: review evidence

Branch: `codex/autumbra-cloudflare-hand`. Base: `7a5132fa`.
Claude opens the PR; founder merges. No PR, merge, deployment, token creation,
Cloudflare mutation or M24 test was performed by this task.

The Enforce adapter implements rate limits and IP blocks through the Rulesets
API, using only `shields.rule_for` expressions and `PHASES`. It appends a rule,
creating a missing phase entrypoint if needed. Undo verifies the recorded zone,
ruleset, rule ID, ref and expression, then deletes that one rule. It never PUTs
an existing ruleset, deletes a ruleset, or removes another rule.

The founder's 13:40 hold is implemented in code: **runtime remains on the
existing fixture even with CLOUDFLARE_API_TOKEN_ENFORCE set**. The adapter refuses
all non-MockTransport transports while the hold is present. No environment flag
lifts it. Live selection/proxy transport, site-health integration and automatic
restoration of the real control belong to the separately approved follow-up.

## Changed files and lines

- `agents/ghost/cloudflare_edge.py:17`: egress code hold and setting name.
- `agents/ghost/cloudflare_edge.py:34`: site-bound Rulesets control, allowlisted
  zones, fixed API origin, bounded requests and fixed errors.
- `agents/ghost/cloudflare_edge.py:79`: fixed-rule apply and owned rule records.
- `agents/ghost/cloudflare_edge.py:137`: ownership-checked single-rule Undo.
- `agents/ghost/cloudflare_edge.py:155`: health callback, false when absent or
  failed. API reachability is never reported as site health.
- `agents/ghost/enforce_apply.py:32`: Enforce-only setting read, sealed fixture
  fallback, and tenant/site validation for explicit offline controls.
- `agents/ghost/enforce_apply.py:79`: ThreatPayload-only apply, actual control on
  receipts, Cloudflare rate-limit dispatch, modes and automatic health Undo.
- `agents/ghost/enforce_apply.py:213`: fixture cannot claim Undo of a real rule.
- `agents/ghost/enforce_apply.py:309`: pending approval preserves kind/path/control,
  rechecks never-block rules and checks health with automatic Undo.
- `agents/ghost/enforce_app.py:346`: actual control in health metadata.
- `.env.example:465`: setting name, empty value and activation-hold comment.
- `tests/test_autumbra_cloudflare_hand.py:1`: 36 offline contract/integration tests.

Watch's `shields.py`, `fixture_edge.py`, `durable_shields.py`, all network/compose
files and all pages/copy are unchanged. Existing durable storage holds only rule
identifiers/action metadata, never tokens or whole API bodies. Offline restart
coverage restores the table into a fresh mock-backed control; it does not claim
live automatic control restoration is enabled.

## Token permissions: founder creates later

Setting NAME: `CLOUDFLARE_API_TOKEN_ENFORCE`, only in per-client Enforce, never
Watch or the proxy. No real token was created, inspected or set. Test markers
are dummy strings with no credential capability.

Custom API token, resource scope **Include → Specific zone → tervory.com**:

1. **Zone → Zone → Read** (`Zone Zone Read`) for `GET /zones?name=tervory.com`.
2. **Zone → WAF → Edit** (`Zone WAF Write`) for reading phase entrypoints,
   creating a missing zone ruleset, appending and deleting the owned rule.

No account-wide grant, DNS edit, global API key or other zone. Check the zone's
existing feature availability and rule quota before M24; this branch changes
neither plans nor the existing fixed rule parameters.

Official sources checked 1 Nov 2026:

- [Zone lookup permission](https://developers.cloudflare.com/api/resources/zones/methods/list/)
- [Zone ruleset creation permission](https://developers.cloudflare.com/ruleset-engine/rulesets-api/create/)
- [Zone rate-limiting API](https://developers.cloudflare.com/waf/rate-limiting-rules/create-api/)
- [Zone custom-rule API](https://developers.cloudflare.com/waf/custom-rules/create-api/)
- [Append rule API](https://developers.cloudflare.com/api/resources/rulesets/subresources/rules/methods/create/)

## Egress proposal for founder and Grok: NOT applied

Enforce stays on its existing per-client internal-only network and queue/data
volumes. One proxy joins that private network and its own outbound network. Only
`api.cloudflare.com:443` is accepted. It publishes no port, binds the private
NIC, pins a public DNS answer and refuses private/special destinations. TLS stays
end-to-end; the token stays in Enforce.

Reuse the existing Radix `egress.py` Proxy/Server, fixed to Cloudflare with storage
disabled. Reuse its image build, not its room or shared network. Exact proposed
change to `agents/ghost/docker-compose.enforce.yml`:

```diff
@@ services.enforce.environment
+      CLOUDFLARE_API_TOKEN_ENFORCE: ${CLOUDFLARE_API_TOKEN_ENFORCE:-}
+      HTTPS_PROXY: http://egress-proxy:8080
+      NO_PROXY: localhost,127.0.0.1
@@ services (new sibling of enforce)
+  egress-proxy:
+    build:
+      context: ..
+      dockerfile: radix/Dockerfile
+    command:
+      - python
+      - -c
+      - >-
+        from egress import Proxy, Server, private_bind_address, system_resolve;
+        allowed = 'api.cloudflare.com';
+        proxy = Proxy(verified_host=allowed, allow_storage=False,
+          resolve=lambda host: system_resolve(host, verified_host=allowed));
+        Server(proxy, host=private_bind_address(), port=8080).serve_forever()
+    restart: unless-stopped
+    mem_limit: 128m
+    cpus: 0.25
+    read_only: true
+    tmpfs: [/tmp]
+    cap_drop: [ALL]
+    security_opt: [no-new-privileges:true]
+    environment:
+      PYTHONDONTWRITEBYTECODE: "1"
+    networks:
+      enforce_internal:
+        interface_name: radix-link
+      egress: {}
@@ networks (enforce_internal stays internal: true, unchanged)
+  egress: {}
```

This proposal is not applied or deployment-tested. The approved follow-up must
wire `httpx.HTTPTransport(proxy="http://egress-proxy:8080")`, prohibit direct
fallback, update lifecycle metadata and real-control boot restoration, test
proxy allowed/refused destinations and per-client isolation, and run a clean
live seal before lifting the hold. The current adapter deliberately ignores
ambient proxies (`trust_env=False`), so HTTPS_PROXY or token alone enables
nothing. Compose would redeploy the per-client Enforce project and add its proxy;
changes under agents/ghost may also select the Ghost deploy-on-merge job.

**Site health is another prerequisite:** an API-only proxy cannot GET
`https://tervory.com/`. Keep the proxy API-only. Founder/Grok must approve the
health observer and how its result reaches Enforce without raw input or a Watch
write path. The callback is an offline seam, not a live observer. An absent or
failed probe returns false and auto-undoes a mock-applied shield. Mock timing is
not M24 timing.

## Exact commands and results

Working directory: `/workspace/codex-autumbra-edge`. The existing local Python
supplies application dependencies. Pinned test tools are checkout-local only:

```bash
/tmp/base-reliability-venv/bin/python -m pip install --no-deps --target /workspace/codex-autumbra-edge/.proof/python pytest-socket==0.8.1
/tmp/base-reliability-venv/bin/python -m pip install --no-deps --target /workspace/codex-autumbra-edge/.proof/python starlette==1.7.0 pytest==9.1.1 pytest-asyncio==1.4.1 ruff==0.17.2
```

Both succeeded. An initial proof directory in /tmp hit a user quota, so proof
and temporary files moved into the checkout. An initial suite with unpinned
Starlette 1.10 had 396 passed, 3 skipped and a recovery-test teardown KeyError.
With the repository's Starlette 1.7 pin, all 7 tests in that file passed, followed
by the complete passing suite below. No unrelated test/route was changed.

Final regression command uses the existing CI clean_env to strip credentials
and additionally removes database settings to avoid production data:

```bash
PYTHONPATH=tank:.proof/python TMPDIR=/workspace/codex-autumbra-edge/.proof/tmp /tmp/base-reliability-venv/bin/python - <<'PY'
import runpy
import subprocess
import sys
from pathlib import Path

clean_env = runpy.run_path('.github/scripts/offline_suite.py')['clean_env']
env = clean_env()
# Never attach the offline suite to any existing database, even on this host.
for name in list(env):
    if 'DATABASE' in name.upper() or name == 'POOL_SCHEMA_DATABASE_URL':
        del env[name]
files = sorted(str(p) for glob in ('test_ghost_*.py', 'test_autumbra_*.py') for p in Path('tests').glob(glob))
cmd = [sys.executable, '-m', 'pytest', '-q', '--disable-socket', '--allow-unix-socket',
       '--allow-hosts=127.0.0.1,localhost,::1', *files, 'tests/test_tank_one_door.py']
with open('.proof/final-suite.txt', 'w') as output:
    result = subprocess.run(cmd, env=env, stdout=output, stderr=subprocess.STDOUT)
print(Path('.proof/final-suite.txt').read_text())
raise SystemExit(result.returncode)
PY
```

Exit 0: **400 passed, 3 skipped, 14 warnings in 35.82 s**. Skips concern opt-in
live inference and absent local schema/tenant databases. No model or Cloudflare
network call. Full output is appended below.

```bash
PYTHONPATH=tank:.proof/python TMPDIR=/workspace/codex-autumbra-edge/.proof/tmp /tmp/base-reliability-venv/bin/python -m pytest -q --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1 tests/test_ghost_airgap_slo_wraith.py tests/test_autumbra_dogfood_airgap.py tests/test_autumbra_enforce_isolation_probe.py tests/test_ghost_isolation_profile.py tests/test_autumbra_enforce_infra.py
```

Exit 0: **23 passed in 1.58 s**. Separate air-gap and isolation output below.

```bash
PYTHONPATH=tank:.proof/python TMPDIR=/workspace/codex-autumbra-edge/.proof/tmp /tmp/base-reliability-venv/bin/python -m pytest -q --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1 tests/test_autumbra_cloudflare_hand.py
```

Exit 0: **36 passed in 0.84 s**. MockTransport checks methods, API origin, phase
paths and exact bodies; unrelated rules survive Undo. Coverage includes zone and
expression refusal, report/approve/automatic modes, restart records, health Undo,
queue apply/Undo, token redaction, provider errors, raw input refusal, tenant/site
mismatch, and sealed fixture fallback with empty or populated token setting.

```bash
PYTHONPATH=.proof/python /tmp/base-reliability-venv/bin/python -m ruff check agents/ghost/cloudflare_edge.py agents/ghost/enforce_apply.py agents/ghost/enforce_app.py tests/test_autumbra_cloudflare_hand.py --select E9,F
git diff --check
git diff origin/main -- agents/ghost/shields.py agents/ghost/docker-compose.enforce.yml
```

All exit 0: `All checks passed!`, clean diff check, no protected-file diff.
No Workspace build: no Workspace change.

```bash
bash ops/seal-check.sh
```

**Exit 1, not a clean seal.** Trigger and Radix network leaks were reported.
Their files/networks were not changed. No Autumbra Watch/Enforce test rooms are
running: offline isolation passes do not prove deployed Autumbra isolation.
Full host output is appended below.

## Founder browser proof and PR status

No live receipt, email, screenshot or founder Undo tap is claimed: those belong
to the separate M24 step after egress/health approval and the founder setting.
No live screen contains these fixtures; no new UI/copy was introduced.

```bash
gh run list --repo Tervory-AI/tervory-tank --branch codex/autumbra-cloudflare-hand --limit 5 --json status,conclusion,url,headSha
```

Returned `[]` at the check: no PR CI run yet. Claude opens the PR from this branch;
local passes are not a claim of green PR CI or successful live M24.

## Full regression output

```text
......................................................s................. [ 17%]
........................................................................ [ 35%]
...................................................s.................... [ 53%]
........................................................................ [ 71%]
................s....................................................... [ 89%]
...........................................                              [100%]
=============================== warnings summary ===============================
tests/test_autumbra_dogfood_hf.py:45
  /workspace/codex-autumbra-edge/tests/test_autumbra_dogfood_hf.py:45: PytestUnknownMarkWarning: Unknown pytest.mark.integration - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    @pytest.mark.integration

../../tmp/base-reliability-venv/lib/python3.12/site-packages/fastapi/testclient.py:1
  /tmp/base-reliability-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

tank/main.py:737
  /workspace/codex-autumbra-edge/tank/main.py:737: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
  
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
          
    @app.on_event("startup")

../../tmp/base-reliability-venv/lib/python3.12/site-packages/fastapi/applications.py:4723
../../tmp/base-reliability-venv/lib/python3.12/site-packages/fastapi/applications.py:4723
../../tmp/base-reliability-venv/lib/python3.12/site-packages/fastapi/applications.py:4723
../../tmp/base-reliability-venv/lib/python3.12/site-packages/fastapi/applications.py:4723
../../tmp/base-reliability-venv/lib/python3.12/site-packages/fastapi/applications.py:4723
  /tmp/base-reliability-venv/lib/python3.12/site-packages/fastapi/applications.py:4723: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
  
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
          
    return self.router.on_event(event_type)  # ty: ignore[deprecated]

tank/main.py:791
  /workspace/codex-autumbra-edge/tank/main.py:791: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
  
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
          
    @app.on_event("shutdown")

../../tmp/base-reliability-venv/lib/python3.12/site-packages/pydantic/_internal/_fields.py:192
  /tmp/base-reliability-venv/lib/python3.12/site-packages/pydantic/_internal/_fields.py:192: UserWarning: Field name "register" in "TriggerWriteArgs" shadows an attribute in parent "TriggerCheckArgs"
    warnings.warn(

tank/agent_skills.py:531
  /workspace/codex-autumbra-edge/tank/agent_skills.py:531: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
  
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
          
    @router.on_event("startup")

tank/skala_intake.py:71
  /workspace/codex-autumbra-edge/tank/skala_intake.py:71: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
  
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
          
    @app.on_event("startup")

tank/skala_intake.py:77
  /workspace/codex-autumbra-edge/tank/skala_intake.py:77: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
  
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
          
    @app.on_event("shutdown")

tank/skala_revalidation.py:192
  /workspace/codex-autumbra-edge/tank/skala_revalidation.py:192: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
  
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
          
    @app.on_event("startup")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
400 passed, 3 skipped, 14 warnings in 35.82s
```

## Air-gap and isolation output

```text
.......................                                                  [100%]
23 passed in 1.58s
```

## Live read-only seal output (exit 1)

```text
tervory-tankmain-xnmc0jkz8j9i5jh1jwanbsfv (xnmc0jkz8j9i5jh1jwanbsfv): not a room, skipped
trigger-crm (aty7tukal0rlksfpet1mzplb): not a room, skipped
agent-zenas (r7qzm460bc4scnskurlowbvn): no sealed containers
agent-trigger (yzq4jrwa6fipvwb7lzcx4nmo): LEAK: agent-trigger-yzq4jrwa6fipvwb7lzcx4nmo-20261101T154548 on tervory-gw-trigger; LEAK: agent-trigger-yzq4jrwa6fipvwb7lzcx4nmo-20261101T154548 on yzq4jrwa6fipvwb7lzcx4nmo; LEAK: trigger-languagetool-yzq4jrwa6fipvwb7lzcx4nmo-20261101T154548 on yzq4jrwa6fipvwb7lzcx4nmo
agent-tisan (lblbn0wjaz30hhdur9l3pylg): no sealed containers
agent-tiger (fro6z8xlh579owlp1wwrjr8n): sealed
agent-rig (59f8cnpelzwsyte1atyjc4fv): sealed
agent-radix (liv4x7vshraiwnnowjv0kgfd): LEAK: liv4x7vshraiwnnowjv0kgfd-passive-egress-1 on liv4x7vshraiwnnowjv0kgfd_egress
agent-market-lab (xt0vc7rnr45flw2wg3iyjpmn): no sealed containers
agent-base (r8aprclj8nooe9keywrp9dmb): sealed
agent-ghost (nypsvvcxjpdebaa204smtqtd): no sealed containers
agent-template (jodjyt6vsyoyhfr6axtuc8ij): no sealed containers
autumbra: no Watch/Enforce rooms running (ok until dogfood; pin EXPECTED_SEALED after first clean run)
```

