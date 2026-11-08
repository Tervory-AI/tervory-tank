# Isolated Redis outage/recovery acceptance

This opt-in command tests the real LiteLLM 1.106.4 SDK and callback headers against disposable Redis and a deterministic loopback HTTP stub. It makes no model/provider calls, uses no provider credentials, and changes no production settings. Run only in an isolated cloud checkout with local Docker and sufficient disk for the pinned image.

```sh
git fetch origin pull/794/head:refs/remotes/origin/cache-callback-candidate
python scripts/cache_redis_acceptance.py --run-isolated --pull --candidate-ref cd2e2ed1eabd59c93b58914a62d2a52989025b43
```

Omit `--pull` when both immutable images are already present. The candidate commit must exist locally. Output is `.checks/cache-redis/report.json` plus `gateway.log`. Exit zero requires all nine functional cases. This is isolated source/dependency equivalence, **not production outage proof or activation**.

## Source and image evidence

`tools/cache_redis/pins.json` records the seven deployed callback/config source hashes at `687753acd45123ef9dc364762540f34404560b3d`, immutable upstream gateway and Redis image digests, and the coordinator's reported Boston custom image ID. Recorded sources are read from Git and hash checked, so later callback merges do not silently change this control. `--candidate-ref` replaces only `tenant_traces.py`; the report lists all effective source hashes and labels the override as deployment-unverified.

The gateway base is `ghcr.io/berriai/litellm@sha256:c169fb3adc514fcf210377c203f3de406d54f10bfdacf13948a4a839db9af7de` (SDK 1.106.4). Redis is `redis:7.4.12@sha256:bd28fff4b665fdf1b73e8b5b73ec05d2f858f4fa3c8ea0d7c9bc09f7f6bf7039`. The observed local gateway image ID is `sha256:5aba1de29b3469c13b842102b0820f654e4d3288c2ad56559f1506e25334a4a1`; it is **different** from Boston's reported custom ID `sha256:6f8b4ffbd0e13d8d86a8f87f88dae58f27f2020d70aef53511d5af4e4942809f`. The harness does not independently inspect Boston or claim byte identity.

Without `--candidate-ref`, the command replays the recorded control. That source exposes a real accounting defect: Redis reuse occurs in a cold process but LiteLLM's leaf-class capability discovery skips the inherited response-header hook. The cold-repeat receipt assertion fails. Runtime-only PR #794 adds the explicit leaf forwarder; it must deploy separately before relying on candidate receipts. Per AGENTS rule 11 its merge redeploys the main app and `tervory-tank-za`; this does not enable C1.

## Functional evidence and bounds

The nine cases require: initial miss; repeat in a new process without another stub call (excludes in-process cache); warm-process priming; two uncached requests while Redis is unreachable with positive synthetic price and no C1 header; recovery reading the original entry in the same warm process; new recovered write; cold-process read of that write; warm repeat. The fault closes a local relay and its active connections, leaving disposable Redis data intact. No production Redis is stopped.

Recovery waits for the SDK's observed circuit-breaker recovery timeout, without overriding it. The measured setting was 60 seconds; the harness waited 60.5. Fixture TTL is 900 seconds, beyond the 600-second probe budget. A separate cold-start-with-Redis-unavailable diagnostic records success/failure and upstream-call delta; it is not substituted for same-process recovery evidence. In the completed candidate run it succeeded: HTTP 200, one stub call, no C1, positive synthetic price. Earlier startup uncertainty is resolved by that result; this is not a claim about production startup latency or other failure modes.

Only a synthetic rate is used to test zero-on-hit versus positive-on-upstream accounting. Reported dollar savings remain null. Assertions use actual C1 headers plus stub counts, never zero price alone. No downstream model quality or production savings are measured.

The command forces the local Unix Docker socket and ignores remote Docker selectors. Containers have no published ports, no Docker socket, no provider environment, an internal-only network, dropped capabilities, no-new-privileges, read-only roots, bounded tmpfs and PID count. Gateway: two CPUs/2 GiB; Redis: one CPU/128 MiB. Each image pull is bounded to 600 seconds; the probe to 600 seconds; each cold worker to 70 seconds. Cleanup removes only resources bearing this run's matching ownership label. Image downloads require network; the probe does not. A failed run exits nonzero and retains local logs.

The independent fixture command `python scripts/cache_rollout_readiness.py` remains the acceptance gate for tenant/user scope, correction and negative-feedback invalidation, embedding dedupe, per-layer receipts and approved deadline-bound off-peak replay. Its Qdrant outage fixture does not prove Redis behavior. Signed-out HTTP availability checks also do not prove activation.

## Coordinator handoff: names only

At the coordinator's last read-only observation all these layers were disabled. First review/merge/deploy #794, verify actual deployed source hashes against the report, and retain both regional deployment/image evidence. The isolated result cannot establish deployed equivalence without that comparison. Review the separate harness PR and its hosted CI. Do not inject a live outage to repeat this fixture.

For a separately authorized rollout, review one layer at a time: `ENGINE_C1_ENABLED` in Tank and LiteLLM; `ENGINE_C4_ENABLED` in Tank and Hermes; `ENGINE_I8_ENABLED` in Tank. Verify existing `REDIS_URL` for Tank and gateway roster Redis host/port; C4 uses `QDRANT_URL` and `QDRANT_API_KEY`. No new setting names are required. Local serving URLs and Langfuse are not prerequisites for this isolated proof. Preserve tenant/user scope, `cache_scope`, `cache_ttl_s`, Ask/Auto approval and truthful per-layer receipts.

Rollback disables the corresponding layer's settings in the same services. Do not flush shared Redis, delete ledger/approvals/jobs, or silently cancel explicit approved work. Disabling I8 stops new automatic deferral; existing explicit jobs retain their lifecycle. Disabling C1 retains the legacy SQL cache. The coordinator owns actual settings and post-deployment acceptance; this document does not authorize or assert activation.

## Remaining router evidence

PR #790's final source was `67280a6faf813c8f0e4e56098e6d153b8f9afabd`. Actual CPU measurements used four frozen synthetic cases (two development, two holdout), rather than fixtures posing as model runs. Arch produced four strict-format abstentions/escalations; RouteLLM produced zero abstentions and one strong selection. Strict matches: Arch 0/2 development and 0/2 holdout; RouteLLM 0/2 and 1/2. These are insufficient to estimate general accuracy or downstream answer quality.

Arch load 9.730 s, first inference 9.326 s, warm 6.543–7.436 s, peak 9.05 GiB. RouteLLM load 7.405 s, first inference 78.2 ms, warm 65.4–67 ms, peak 1.02 GiB. Report SHA-256: `6af914c7cbb7372e31973588f985459c5a6602342d426e2234ceb1fddc9874b6`. Raw data SHA-256: `337da525e2521e3091d1c7a9be0411a2a33e3b5ebec475359d7104cad87b9bbf`. The PR records full checkpoint/runtime/data hashes and pinned licence/attribution evidence. Dollar inference cost, downstream quality and savings are unknown; commercial permission remains pending counsel review. Larger untouched holdout evaluation and strict-format compatibility remain follow-up work. No production routing activation follows from these measurements.
