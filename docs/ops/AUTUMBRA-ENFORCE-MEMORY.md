# Autumbra Enforce memory measurement

Founder lock: **do not guess** the Enforce container cap or treat compose `mem_limit: 256m` as measured.
`DEFAULT_CONTAINER_CAP` stays **`held_until_measured`** (`None`) until this script returns a number.

## One command (Coolify **test** host only — never live Boston)

```bash
bash ops/autumbra-enforce-memory-measure.sh <enforce-container-name>
```

### Expected output (success)

```
docker_stats_mem_usage=42.1MiB / 256MiB
cgroup_memory_peak_bytes=44167232
cgroup_memory_peak_mib=42.1
suggested_mem_limit_mib=63 (peak * 1.5)
NOTE: paste this into PR #337 and set compose mem_limit + host container cap from the number.
```

### Expected output (blocker — wrong host / missing container)

```
BLOCKER: container <name> not on this docker host
```

Exit code `2`. Cap stays held.

### Expected output (cgroup peak unavailable)

```
docker_stats_mem_usage=...
cgroup_memory.peak unavailable inside container; use docker stats above as soft signal
suggested_mem_limit_mib=HOLD — re-run after dogfood load with cgroup v2 peak
```

## Method

1. Stand up one fixture Enforce via `agents/ghost/docker-compose.enforce.yml`.
2. Run dogfood load (fixture attack + own-site exercise pass).
3. Run the one-command measure above.
4. Paste `cgroup_memory_peak_mib` and `suggested_mem_limit_mib` into draft PR #337.
5. Set compose `mem_limit` and (only then) a host container cap from the number.
6. Pin `EXPECTED_SEALED` after first clean dogfood.

## Builder-box status (2026-10-26 America/Los_Angeles)

Docker socket not usable on the Grok Bot worker. Cap remains **held_until_measured**. Re-run on the Coolify **test** host the founder picks (never Boston).
