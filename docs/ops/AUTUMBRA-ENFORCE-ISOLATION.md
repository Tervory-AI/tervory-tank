# Autumbra Enforce isolation check

Proves a fixture client's Enforce container cannot **resolve** (DNS) Tank, Workspace, or another client's internal hostnames on its isolated network. This is DNS resolution only — not a TCP reachability probe. It does **not** claim `tervory.com` is unreachable (public DNS may resolve that name).

## Founder-only live check, after deployment

The founder runs this read-only command on the host that runs the intended
client's Enforce container, using its actual container name:

```bash
bash ops/seal-check.sh && bash ops/autumbra-enforce-isolation-check.sh <enforce-container-name>
```

Builders do not run this on a live host. The probe reads DNS/connectivity and
holds no Tank key; it changes no controls or client data. A missing mandatory
room or an extra network is a failure, not a skipped room. `agent-ghost` is
required alongside the existing four rooms. `autumbra-enforce` is required only
when an app containing an `enforce` service is present on this host; its absence
on other hosts does not block their deployments. Every such app is audited,
regardless of its Coolify resource name.
Watch's seal means exactly its existing `tervory-gw-ghost` corridor (including
its browser), not an internet-dark process. Before any per-project early return,
Enforce must have exactly one internal network. The labelled-network check then
requires that network to be this project's `enforce_internal`. Its app must also
contain `egress-proxy`, `health-observer` and `health-egress-proxy`, with exactly
their existing declared project networks and internal flags. No extra attachment
is permitted and no outbound network is added here.

## Automated proof: disposable GitHub CI only

The `autumbra-isolation` job in `.github/workflows/tenant-rls.yml` runs
`tests/autumbra_a2/test_compose_probe.py` against
`tests/autumbra_a2/docker-compose.probe.yml`. It builds the existing image and
runs `ghost.enforce_isolation_probe` inside a temporary client network; the hub
and the other synthetic client are on separate internal networks. The same
probe must fail after a deliberate connection to that synthetic hub. All
containers/networks are removed in `finally`; no public ports, host mounts,
credentials or external networks are present. Output is the
`autumbra-isolation` Actions artifact. The test refuses non-GitHub execution
when armed and is skipped during normal local suite runs.

No container probe was run on Boston by the builder. CI proof and the founder's
live check are separate evidence; neither is claimed without its output.

## Existing helper on a test host

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

Live isolation remains unproven until the founder supplies the live command output.
The Enforce memory cap remains `held_until_measured`; this task does not measure or change it.
