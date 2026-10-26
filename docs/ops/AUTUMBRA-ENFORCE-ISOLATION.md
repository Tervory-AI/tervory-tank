# Autumbra Enforce isolation check

Proves a fixture client's Enforce container cannot reach Tank, Workspace, tervory.com, or another client's network.

## One command (Coolify **test** host only — never live Boston)

```bash
bash ops/autumbra-enforce-isolation-check.sh <enforce-container-name>
```

### Expected output (pass)

The script prints each attached network, then the probe module's JSON (exact shape from `ghost.enforce_isolation_probe`):

```
network=autumbra-enforce-net-<tenant> internal=true
{
  "probe": {
    "has_tank_key": false,
    "public_443": false,
    "resolve": {
      "agent-other": false,
      "autumbra-enforce-other": false,
      "base": false,
      "hermes": false,
      "litellm": false,
      "market_lab": false,
      "postgres": false,
      "qdrant": false,
      "redis": false,
      "tank": false,
      "tiger": false,
      "workspace": false
    },
    "role": "enforce",
    "shares_network_with_other_client": false
  },
  "report": {
    "fails": [],
    "kind": "isolation_probe",
    "ok": true,
    "passes": [
      "tank does not resolve",
      "postgres does not resolve",
      "hermes does not resolve",
      "workspace does not resolve",
      "redis does not resolve",
      "qdrant does not resolve",
      "litellm does not resolve",
      "tiger does not resolve",
      "base does not resolve",
      "market_lab does not resolve",
      "agent-other does not resolve",
      "autumbra-enforce-other does not resolve",
      "public internet unreachable",
      "no shared network with other client",
      "no TANK_KEY",
      "role=enforce"
    ],
    "product": "Autumbra",
    "viewpoint": "inside_fixture_enforce"
  }
}
```

Exit code `0` when `report.ok` is true. Probe module path inside the container: `python -m ghost.enforce_isolation_probe`.

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

Until a test host exists, the isolation claim stays **unproven** in live networks; unit tests cover `evaluate_probe` with a dark fixture network. Cap remains `held_until_measured`.
