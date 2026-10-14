# Radix

Radix is the security auditor. It looks at code that is handed to it and reports what it finds. It has no skills yet. The first day a skill is approved, this room is already running.

## Room

Own Coolify resource. Base directory `/agents/radix`. Compose location `/docker-compose.yml`. No public domain. Predefined network: isolated network only.

The only corridor is `tervory-gw-radix`. It is an **internal** network, created on the server with `docker network create --internal tervory-gw-radix`. Radix can reach Tank, Postgres, and Hermes, and nothing else. No internet.

Login `agent_radix`. Schema `agent_radix`. Key `TANK_KEY_RADIX` on Tank and on Hermes. `RADIX_ALLOWED_HOSTS` is empty.

`agents/radix/net.py` is the only way Radix code makes an HTTP call outside Tank and Hermes. It refuses any host that is not on `RADIX_ALLOWED_HOSTS`. An empty list refuses every host. When the first scanning skill needs the internet, Claude adds an egress proxy that enforces the same list. Until then the list stays empty.

## First three skills

These run on code handed to Radix. None of them need the internet.

1. `scan.secrets` (Gitleaks)
2. `scan.dependencies` (npm audit and pip audit)
3. `scan.static_analysis` (Semgrep)

## What Radix never does

- Scan a target the tenant has not registered and proven it owns (DNS TXT or a file token). That check is Radix's first skill.
- Run exploits, or anything beyond detection.
- Store a secret it finds. It records the type, the file, and the line. Never the value.
- Reach another Squad member's corridor.
