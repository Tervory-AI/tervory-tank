# Autumbra Enforce memory measurement

Founder lock: **do not guess** the Enforce container cap or treat compose `mem_limit: 256m` as measured.

## Method (Coolify **test** host only — never live Boston)

1. Stand up one fixture Enforce via `agents/ghost/docker-compose.enforce.yml`.
2. Run dogfood load (fixture attack + own-site exercise pass).
3. Measure:

```bash
bash ops/autumbra-enforce-memory-measure.sh <enforce-container-name>
```

4. Paste `cgroup_memory_peak_mib` and `suggested_mem_limit_mib` into draft PR #337.
5. Set compose `mem_limit` and (only then) a host container cap from the number.
6. Pin `EXPECTED_SEALED` after first clean dogfood.

## Builder-box status (2026-10-26 America/Los_Angeles)

```
$ docker ps
permission denied while trying to connect to the Docker daemon socket ...
```

**BLOCKER on this Grok Bot worker:** Docker socket not usable (`box` not in `docker` group). Cap remains **held_until_measured**. Re-run the script on the Coolify test host.
