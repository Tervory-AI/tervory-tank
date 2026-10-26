# Autumbra Enforce isolation check

Proves a fixture client's Enforce container cannot reach Tank, Workspace, tervory.com, or another client's network.

## One command (Coolify **test** host only — never live Boston)

```bash
bash ops/autumbra-enforce-isolation-check.sh <enforce-container-name>
```

### Expected output (pass)

```
network=autumbra-enforce-net-<tenant> internal=true
{"ok": true, "tank_reachable": false, "workspace_reachable": false, "other_client_reachable": false, "public_egress": false}
```

Exit code `0`. Probe module: `agents.ghost.enforce_isolation_probe`.

### Expected output (fail — network not internal)

```
network=bridge internal=false
FAIL: no internal:true network attached
```

Exit code `1`.

### Expected output (blocker — missing container)

```
BLOCKER: container <name> not on this docker host
```

Exit code `2`.

Until a test host exists, the isolation claim stays **unproven** in code plans only (`plan_create` isolation flags + unit probe with mocked dark network).
