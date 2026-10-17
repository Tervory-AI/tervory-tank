# Radix

Radix is the security auditor. It looks at code that is handed to it and reports what it finds. It does not clone a repository and it does not use the internet while it scans.

## Room

Own Coolify resource. Base directory `/agents/radix`. Compose location `/docker-compose.yml`. No public domain. Predefined network: isolated network only.

The only corridor is `tervory-gw-radix`. It is an **internal** network, created on the server with `docker network create --internal tervory-gw-radix`. Radix can reach Tank, Postgres, and Hermes, and nothing else. No internet.

Login `agent_radix`. Schema `agent_radix`. Key `TANK_KEY_RADIX` on Tank and on Hermes. `RADIX_ALLOWED_HOSTS` is empty.

`agents/radix/net.py` is the only way Radix code makes an HTTP call outside Tank and Hermes. It refuses any host that is not on `RADIX_ALLOWED_HOSTS`. An empty list refuses every host. A scan does not call `net.py`.

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
gate, the prepared HTTP checks, and the network tests still required. No external
host is approved by this change; the room remains sealed. RX-3 and RX-4 wait.

The guard accepts exact ASCII DNS names and HTTP/HTTPS default ports only.
It returns redirects without following them, refuses a different Host header,
and ignores environment proxy settings. This application check is not a
substitute for the approved egress proxy and network isolation.

Guard tests run in GitHub Actions with the repository's existing `pytest -q`
command. A cloud worker can run them directly with
`pytest -q agents/radix/tests/test_egress_guard.py`; do not run builds on the
founder's laptop.
