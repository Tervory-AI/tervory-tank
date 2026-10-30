# ZA R2 backup: founder setup and prove-restore

Encrypted nightly Postgres dumps for the South Africa stack land in Cloudflare R2
bucket **`tervory-zenas-za`**. Boston `tervory-zenas` / `tervory-uploads` stay
unchanged. This document is the only prove-restore path for that ZA worker.

## Env names (values stay with the founder)

Coolify apps `tervory-tank-za` and `agent-zenas-za` need these **names** filled
(never invent values in git):

| Name | Where | Notes |
|------|-------|-------|
| `R2_BUCKET_ZENAS_ZA` | both | Must be exactly `tervory-zenas-za` |
| `R2_ACCOUNT_ID` | both | Same Cloudflare account as US rooms |
| `R2_ACCESS_KEY_ID_ZENAS` | both | Token scoped to `tervory-zenas-za` (or that bucket + list) |
| `R2_SECRET_ACCESS_KEY_ZENAS` | both | Pair with the access key |
| `R2_BACKUP_RECIPIENT` | `tervory-tank-za` only | Public age recipient (`age1…`); private identity never on the box |

US `agent-zenas` keeps hardcoded `R2_BUCKET: tervory-zenas`. Do not set
`R2_BUCKET_ZENAS_ZA` on US.

## Founder creates the bucket

1. In Cloudflare R2, create bucket **`tervory-zenas-za`** (name exact).
2. Create an API token that can read/write **only** that bucket.
3. Set the Coolify env names above. Leave secrets out of git and chat.
4. Deploy `tervory-tank-za` from `docker-compose.za.yml` and `agent-zenas-za`
   from `agents/zenas/docker-compose.za.yml` after this PR merges.

## Opt-in worker (off by default)

`docker-compose.za.yml` declares `r2-backup-za` behind profile **`r2-backup-za`**.
Normal Coolify deploy does **not** start it.

```sh
# On the ZA box / Coolify one-shot, after env is filled:
docker compose -f docker-compose.za.yml --profile r2-backup-za run --rm r2-backup-za \
  python jobs/train/backup.py --owner zenas --once
```

Expected stdout (one JSON object; date/run vary):

```json
{"bucket": "tervory-zenas-za", "key": "za/00000000-0000-0000-0000-000000000001/backups/YYYY-MM-DD/HHMMSS-<hex>/database.dump.age/manifest.json", "size_bytes": <int>}
```

Nightly (02:00 UTC) after founder enables the profile in Coolify:

```sh
docker compose -f docker-compose.za.yml --profile r2-backup-za up -d r2-backup-za
```

Confirm it is **not** running after a normal deploy without that profile:

```sh
docker compose -f docker-compose.za.yml ps
# Expected: no r2-backup-za row
```

## Prove restore (encrypted file only)

Decryption stays founder-side. The worker and CI never see a private age key.

From a machine that has the Zenas R2 pair, `R2_BUCKET_ZENAS_ZA=tervory-zenas-za`,
`TANK_REGION=za`, `AGENT_NAME=zenas`, and Python deps for `jobs/train`:

```sh
export TANK_REGION=za AGENT_NAME=zenas
export R2_BUCKET_ZENAS_ZA=tervory-zenas-za
export R2_BUCKET="$R2_BUCKET_ZENAS_ZA"
# plus R2_ACCOUNT_ID / R2_ACCESS_KEY_ID_ZENAS / R2_SECRET_ACCESS_KEY_ZENAS

python - <<'PY'
import asyncio, os
from pathlib import Path
import sys
sys.path.insert(0, 'agents/_chassis')
sys.path.insert(0, 'jobs/train')
from chassis.storage import PLATFORM_TENANT, Storage
from r2_archive import restore_archive

MANIFEST = os.environ['BACKUP_MANIFEST']  # e.g. 2026-10-27/020000-abc…/database.dump.age/manifest.json
OUT = Path('database.dump.age')

async def main():
    store = Storage('zenas')
    try:
        await restore_archive(
            store, MANIFEST, OUT, 'backups',
            tenant_id=PLATFORM_TENANT, public=True)
        print(f'restored_bytes={OUT.stat().st_size} path={OUT}')
    finally:
        await store.close()

asyncio.run(main())
PY
```

Expected:

```
restored_bytes=<positive int> path=database.dump.age
```

Then founder decrypts offline (private identity never on Coolify):

```sh
age --decrypt -i /path/to/founder-backup-identity -o database.dump database.dump.age
pg_restore --list database.dump | head
```

Expected: `pg_restore --list` prints TOC entries; no plaintext dump was ever
written by the Coolify worker.

## What this PR does not do

- Does not merge, deploy, or enable the profile.
- Does not invent bucket tokens or age identities.
- Does not change US `R2_BUCKET: tervory-zenas` or Boston `r2-backup`.
