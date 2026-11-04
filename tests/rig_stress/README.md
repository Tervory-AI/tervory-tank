# Rig prompt G: preparation, not a capacity result

This adds guarded workload primitives and an offline wiring check. No saturation
run has happened. `harness.py` intentionally performs **preflight only** and emits
`capacity_valid: false`; forge queue and host metrics adapters must be wired to an
assigned spare target before the 15-minute matrix can execute. It never provisions,
seeds, deletes or contacts production resources. No UI or application code changes.

Original prompt recovered from founder attachment
`25c789cf-baca-4ca8-b185-9235bb327ed0/MILESTONES-28OCT-1NOV.md`, lines 134–147.
Current main's milestone document lacks prompt G. Matrix: N=5,10,20,30, 900 seconds
per level; stop at first failure. Limits: search p95 <1s; quote p95 <2s; zero
errors; memory <80%; forge queue wait <300s. Record host and per-container memory,
CPU, disk I/O every 30s; search/quote p50/p95; errors and queue waits. Submit one,
then two concurrent forge jobs. Repeat shared layout only if supported. Tear down
only test-owned resources and prove no test resources remain. Up to 60 minutes
traffic per layout, excluding setup/teardown. Box price must come from actual
assigned infrastructure, not an estimate.

## Explicit inputs, without saturation defaults

`python3 tests/rig_stress/harness.py CONFIG.json --isolated-test-target`

Config must supply `rps_per_store` (aggregate requests/sec/store), integer
`concurrency_per_store`, existing `catalogue_fixture` and `forge_fixture` file paths
(relative to config), all 30 `stores`, `target_allowlist`, `network`, and
`dedicated_spare_host: true`. Each store has `target` and `operations` keyed
`search`, `setup`, `quote`. Each operation has `method`, relative `path`,
`expected_statuses` and optional JSON `body`. No credentials are accepted in target
URLs; this preparation does not issue, store or read keys. Request fixtures must
come from approved isolated inputs. Files are checked for existence only; no
catalogue is installed by this harness. Forge fixture is reserved for the future
queue adapter; it is not executed. No guessed RPS, fixture sizes or concurrency is
presented as a founder-approved workload.

Existing functional routes are reused: GET `/v1/rig/search`, POST
`/v1/rig/setups`, POST `/v1/rig/quote`; future forge adapter must use existing
POST `/v1/rig/admin/3d/jobs` and GET `/v1/rig/admin/3d/jobs/{job_id}`. The existing
`tests/rig_store_job` remains the source of real API fixture contracts. Its runner
is deliberately not invoked: it generates credentials, starts real database and
SMTP services, publishes ports and exceeds this preparation's isolation budget.

Saturation preflight requires an internal `rigstress-` Docker network labelled
`rigstress.isolated=true`. Every member must carry the same label, have only that
network, no mounts/published ports/privileged mode, and an allowlisted RFC1918
literal IP matching an inspected member. DNS names (including Tervory names),
public IPs (including registered ZA), loopback, metadata addresses, default and
Coolify networks fail. HTTP uses direct connections without proxy environment or
redirect following. This is a dedicated-host safeguard, not evidence that a host
is spare: the operator still must verify the assignment. Existing production
containers are never relabelled or reused.

`traffic()` schedules fixed arrivals with bounded concurrency, reports dropped
requests rather than building a backlog, and cycles search/setup/quote equally.
That operation mix is wiring behavior, not an approved shopper profile. Requests
have a five-second timeout and no retries. Quantiles use nearest rank. `report()`
requires supplied measurement samples and queue waits; absent observations fail
limits. It always marks capacity invalid. The caller must stop progression on
`failed_limits`; automated saturation progression is intentionally unavailable.
No model, SMTP or real product calls occur in the smoke test.

## Offline verification and exact evidence

2026-10-30, Boston. Source branch based on main `483bc3d`.

Commands and results:

- `python3 -m py_compile tests/rig_stress/harness.py`: exit 0.
- `python3 -m unittest discover -s tests/rig_stress -v`: exit 0, six tests passed.
- Container command below: exit 0, six tests passed in 1.292s. Fake loopback HTTP
  server only. Report's memory=10/100 and queue waits=[1,2] are **unit inputs**, not
  host measurements. Its response times are fake-server wiring observations.
- Inspection command below: exit 0; network=none, CPU=250000000 nanocpus,
  memory=268435456, swap=268435456 (no extra swap), readonly=true, mounts=0, ports={}.
- `docker rm rigstress-offline-20261030`: exit 0.
- `docker ps -a --filter label=rigstress.isolated=true --format '{{.Names}}'`:
  exit 0, empty output after cleanup.
- `git diff --check`: exit 0.

Exact container command (existing local image, no download/build, no inherited
production container environment, volumes, network or socket):

```sh
tar --exclude=__pycache__ -C tests/rig_stress -cf - harness.py test_harness.py | docker run --name rigstress-offline-20261030 --label rigstress.isolated=true -i --network none --cpus 0.25 --memory 256m --memory-swap 256m --pids-limit 64 --read-only --cap-drop ALL --security-opt no-new-privileges --tmpfs /tmp:rw,noexec,nosuid,size=16m --entrypoint python 59f8cnpelzwsyte1atyjc4fv-agent-rig:latest -B -c 'import sys,tarfile,unittest; from pathlib import Path; p=Path("/tmp/rig_stress");p.mkdir();tarfile.open(fileobj=sys.stdin.buffer,mode="r|*").extractall(p,filter="data");sys.path.insert(0,str(p));result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover(str(p)));sys.exit(not result.wasSuccessful())'
docker inspect --format '{{.State.ExitCode}} network={{.HostConfig.NetworkMode}} cpu={{.HostConfig.NanoCpus}} memory={{.HostConfig.Memory}} swap={{.HostConfig.MemorySwap}} readonly={{.HostConfig.ReadonlyRootfs}} mounts={{len .Mounts}} ports={{json .HostConfig.PortBindings}}' rigstress-offline-20261030
docker rm rigstress-offline-20261030
```

Earlier preparation failures recorded: first commit attempt lacked checkout-local
git identity (fixed using existing Codex identity); first docker-cp attempt failed
because rootfs was read-only (container removed; stdin tar into bounded tmpfs used
instead). Neither failure involved a push failure or production mutation.

## Target evidence and remaining work

At 2026-10-30 14:55:10 PDT / 21:55:10 UTC, registered Coolify servers were Boston
and ZA Afrihost. Projects Tervory AI, Tervory ZA, AmmoSync each had only production
environments; no registered spare/test project or Enforce test container. Docker
had only default local context. This does not rule out an unregistered external
host. Boston: 8 CPUs, 32089 MiB RAM, 23150 MiB used, 8939 MiB available, no swap.
`/tmp` is tmpfs, 6.0 GiB free. A full Rig compose stack has ceilings totalling
9.25 GiB/5 CPUs, not reserved or measured consumption. Docker network isolation
cannot make saturation on shared production CPU/RAM/disk a valid spare-box test.

Still required: assigned isolated host and actual price; reviewed traffic profile;
private catalogue/forge fixtures; host/forge measurement adapters; real runs,
cleanup evidence and independent review. A dedicated 8 CPU/32 GiB target is a
proposed comparison to Boston, not a measured minimum requirement. Autumbra's
existing memory-measure script remains unchanged and test-host-only. No production
SQL, data, settings, caps, model calls or load. Founder browser acceptance remains
last and is not claimed by unit tests. No screenshots exist for a founder capacity
test because that test has not run.

## Independent review fixes — 2026-10-30 15:03 PDT / 22:03 UTC

`preflight` now requires `dedicated_spare_host is True`; false, strings, numbers
and null fail. `load_config` binds operation names to exactly GET
`/v1/rig/search`, POST `/v1/rig/setups`, POST `/v1/rig/quote`. Dot segments,
encoded traversal, duplicate slashes, query/fragment additions, wrong methods and
cross-operation paths fail. Forge remains unimplemented and cannot be selected
as a traffic operation; no prefix-based forge escape is enabled.

RED/GREEN proof: loaded `git show ee1996f:tests/rig_stress/harness.py` into an
in-memory module and ran the two new regression methods using unittest: original
head produced 10 assertion failures, no test errors. Current head:
`python3 -m unittest discover -s tests/rig_stress -q` exit0, eight tests passed in
1.212s. Regression method names: `test_spare_confirmation_requires_boolean_true`
and `test_config_binds_exact_operation_routes`. No network is involved in those
mocked metadata/config checks.

Reran the exact container command above with the final eight-test suite: exit0,
eight passed in1.309s. Inspection again exit0: network=none, CPU250000000,
RAM268435456, swap268435456, readonly=true, mounts0, ports{}. Removed container;
label-filtered `docker ps -a` empty. One preceding capped run exposed a flaky
assumption that CPU-constrained fake HTTP could never drop arrivals. That run
exited1, then was cleaned up. The final test records real traffic drops but tests
report arithmetic with deterministic inputs. All printed report latencies now
also are unit values (.01/.02/.03 seconds), never a benchmark. The separate
overload regression still requires dropped arrivals to be reported, and dropped
arrivals still fail the limits.

## Backlog completion — 4 November 2026

This section supersedes the old six/eight-test preparation results, not the
founder's capacity acceptance. Source/preflight is complete for review; **no
capacity measurement has run** and every report still has `capacity_valid: false`.

### Current-main and replacement check

Checked GitHub main `fa34a9f0d9e8323358ebb47c82ba5e9f2eed9fab` and PR #456 head
`ce1b93b29a14d3fe0f01c4778cc80e733c282ebe`. GitHub returned 404 for each of this
PR's three `tests/rig_stress/` files on that main commit. Repository code searches
for `rigstress`, `rig_stress` and stress tests, plus the PR search for `stress`,
found no replacement Rig saturation harness. #486 is offline functional CI, not a
capacity runner. Current `agents/rig/rigbox/api.py:175,260,322` still binds GET
search, POST setups and POST quote to the exact routes used here. Current root
AGENTS.md was read. #456 is mergeable; no verified conflict exists, so main was
not merged, in accordance with this assignment. GitHub will test the PR merge.

### Completed safeguards

* Reject nonfinite, negative, boolean and malformed observations. Unknown memory
  or queue measurements fail rather than looking idle; zero/invalid memory totals
  do not crash the report or prove capacity.
* Require explicit nonempty integer 2xx `expected_statuses` per operation. A 500
  or redirect cannot be declared a successful observation. Reject unreviewed
  operation fields, including arbitrary headers. Existing exact route/method and
  RFC1918 allowlist checks remain.
* Reject missing/literal-false spare confirmation **before any Docker inspection**;
  the network's Internal field must be literal True. This confirms operator input,
  not independent proof of a spare host.
* Exercise CLI refusal and preflight-only behavior; it never calls `traffic()`.
* Replace loopback HTTP and thread-pool test workers with HTTP and asynchronous
  doubles. All 13 tests now require no socket, Docker service or worker threads.
  They assert requests, error/redirect rejection, close behavior, overload reporting,
  exact thresholds and isolation metadata. These are functional checks only.

### Accessible inventory and the one capacity blocker

No connected Coolify/server-inventory tool is available in this session. Read-only
inspection covered the historical inventory in this PR and current-main
`docs/ops/AUTUMBRA-ENFORCE-ISOLATION.md`. That document identifies a disposable
GitHub CI DNS-isolation probe and says live isolation is unproven; it does **not**
assign a Rig stress server. It is not a replacement workload or spare assignment.
The 30 October Boston/ZA entries above are historical production inventory,
not evidence those hosts are spare today. Neither production host was inspected
or used. No hardware, cloud resource, container or test network was provisioned.

**One remaining capacity blocker: an explicitly assigned, approved isolated Rig
stress target/workload package.** It must identify the dedicated server/network,
30 isolated tenant stores, resource ownership/cleanup boundary and reviewed request
profile/fixtures. A boolean or private IP alone is not an assignment. No such
package was found in accessible sources; this does not assert that none exists
outside those sources.

This assignment is what the missing real adapters must bind to:

| Adapter/input | Exact missing contract; no substitute measurement claimed |
| --- | --- |
| Shopper workload/auth | Reviewed tenant identity, search query parameters, body contracts and existing authentication-by-name on the assigned isolated Rig target. The primitive has exact paths and optional JSON body only; it does not yet model query parameters, embed/origin authentication, shopper journeys or a representative mix. Fixture existence is not ingestion or validation of a real catalogue. Never run a production quote handoff. |
| Forge queue | Isolated forge submission/status contract using existing admin job routes, fixture/artifact ownership, enqueue/start times for one and two concurrent jobs, completion and cleanup. No queue wait may be inferred from HTTP response time. The reserved forge fixture is not executed. |
| Host/container metrics | Target-side read-only host and per-container memory/CPU/disk-I/O sampling every 30s, with timestamps, memory denominators and coverage of each 900s level. No local CI memory stands in for that host. Docker inspect metadata alone is not a measurement adapter. |
| Matrix and teardown | Execute N=5/10/20/30 only after the above bindings are reviewed; stop on first failure; verify cleanup of test-owned resources only. The preflight CLI intentionally has no execute mode and cannot run this matrix. |

No clients-per-box number, minimum server size, cost or saturation result can be
derived from these offline tests. No provider/model/SMTP call, credential access,
production SQL/load/mutation, deployment or Skala action was performed.

### Focused verification on this revision

Own checkout: `/home/ammosync/.codex/rig-stress-456-20261104` (the session permits
writes there, not `/workspace`). Shell GitHub fetch was attempted once and failed
with `Could not resolve host: github.com`; publication uses the connected GitHub
Git-object API with a normal fast-forward and expected old head, never force.
An initial baseline/local threaded test attempt stalled in this restricted
session and was interrupted; it is not claimed as a passing run. The replacement
socket/thread-free regression run completed:

```sh
python3 -m py_compile tests/rig_stress/harness.py tests/rig_stress/test_harness.py
timeout 20s python3 -m unittest discover -s tests/rig_stress -v
git diff --check
```

Results: compile exit 0; **13 tests passed in 0.191s**, exit 0; diff check exit 0.
No full local suite was run. Final-head hosted CI and the published head are
recorded in #456. The earlier capped-container output is historical, not rerun
or capacity evidence for this revision. Founder review/merge remains outstanding.
