# Radix

Radix is the security auditor. It looks at code that is handed to it and reports what it finds. It does not clone a repository and it does not use the internet while it scans.

## Room

Own Coolify resource. Base directory `/agents/radix`. Compose location `/docker-compose.yml`. No public domain. Predefined network: isolated network only.

The corridor is `tervory-gw-radix`. It is an **internal** network, created on the server with `docker network create --internal tervory-gw-radix`. On that corridor Radix can reach Tank, Postgres, and Hermes. It has no direct route to the internet.

The only other path is an internal link to `egress-proxy`. That proxy may open `lokd.co.za` on port 443. It refuses every other destination. The room compose is not a deploy.

Login `agent_radix`. Schema `agent_radix`. Key `TANK_KEY_RADIX` on Tank and on Hermes. In the room compose, `RADIX_ALLOWED_HOSTS` is the literal `lokd.co.za`. An empty list still refuses every host.

`agents/radix/net.py` is the only way Radix code makes an HTTP call outside Tank and Hermes. It refuses any host that is not on `RADIX_ALLOWED_HOSTS`. An empty list refuses every host. A real call dials `http://egress-proxy:8080` and no other proxy. The proxy, not the agent, opens the socket to `lokd.co.za` port 443. A scan of handed-over code does not call `net.py`.

## Scan job

`POST /jobs` with `kind` `scan`. The input is `{tenant_id, source, ref}`.

- `tenant_id` must be the same tenant as the job. Findings are stored only for that tenant.
- `source` is the repo, sent by the caller. It may be base64 (optionally prefixed with `b64:`) of a `.tar.gz`, a zip, or a git bundle, or `file:<name>` for a file already stored under `/data/<tenant_id>/`. A web address is refused.
- `ref` is a label, such as a branch or commit. Radix does not fetch it.

The image bakes in Gitleaks 8.28.0, Semgrep 1.181.0, and pip-audit 2.10.1. Semgrep rules are the file `scanlib/semgrep.yml`. Advisory data is the OSV JSON under `scanlib/osv`, copied to `/opt/osv` at build. pip-audit and npm audit call a live service, so the dependency scan reads that OSV directory and does not run those clients.

## What a scan returns

A plain-English summary, and one row per finding in `agent_radix.findings`: `tenant_id`, `scan_id`, `tool`, `severity`, `file`, `line`, `rule`, `fix`. Severity `critical` means the build must not deploy. Tisan reads that later.

The secret text is not a column. It is masked out of the summary, the rows, and the log line.

## The three skills

1. `scan.secrets` — Gitleaks. Reports type, file, line, and rule.
2. `scan.dependencies` — npm and Python packages against the baked OSV data. Reports package, version, advisory id, severity, and the fixed version.
3. `scan.static` — Semgrep with the vendored rules. Looks for SQL built by string formatting.

## What Radix never does

- Scan a target the tenant has not registered and proven it owns (DNS TXT or a file token). That check is a later skill.
- Run exploits, or anything beyond detection.
- Store a secret it finds. It records the type, the file, and the line. Never the value.
- Reach another Squad member's corridor.

## RX-2 preparation

[RX-2 controlled egress preparation](RX2-egress-plan.md) records the host approval
gate, the prepared HTTP checks, and the network tests still required. The only approved external name is `lokd.co.za` (HTTPS, port 443). The agent
stays on the internal corridor plus a link that reaches only `egress-proxy`.
`egress-proxy` is the only service with a path out, and it refuses every
destination except that host and port. The room is not deployed by this change.

## First live check

`live.py` is a passive header and certificate check of `https://lokd.co.za/`
only. It does not follow a redirect to any other host, and it does not read or
store a cookie value. It dials the room proxy. It does not open its own socket
to the site. Run it inside the room:

`python live.py`

This check is not a job on the service. If the proxy is stopped, missing, or
revoked, the check fails closed.

The guard accepts exact ASCII DNS names and HTTP/HTTPS default ports only.
It returns redirects without following them, refuses a different Host header,
and ignores environment proxy settings. This application check is not a
substitute for the approved egress proxy and network isolation.

Guard tests run in GitHub Actions with the repository's existing `pytest -q`
command. A cloud worker can run them directly with
`pytest -q agents/radix/tests/test_egress_guard.py`; do not run builds on the
founder's laptop.
