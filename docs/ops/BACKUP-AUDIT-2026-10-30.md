# Backup audit: 30 October 2026

Observed on Boston `ammosync-us-boston`, 09:36:32–09:37:36 PDT / 16:36:32–16:37:36 UTC, against main `a6a655fcc2aa5d43e8ae6499dcd5bd58d8b1c25c`.

## Findings

| Store / region | Current evidence | Remaining gap |
| --- | --- | --- |
| Boston US Docassemble | Running backup sidecar; dated encrypted R2 object verified below | No SQL restore, row comparison or restore duration established |
| Boston main-stack SQL | `docker ps -a --filter name=backup` returned only the Docassemble sidecar, no `r2-backup` container | Main-stack backup runtime absent from this inventory; no fresh main SQL backup or restore proof established |
| Dedicated South Africa ZA | Repository variable `ZA_OFFLINE=true` | No current regional backup/restore evidence inspected; no activation attempted |

The historical Boston missing-`R2_BACKUP_RECIPIENT` observation is no longer current for the inspected Docassemble sidecar: all four required names below have nonempty values. Values were never printed. This does not establish settings on the absent main backup worker or on ZA.

Current US object:

```json
{"bucket":"tervory-zenas","key":"us-east/00000000-0000-0000-0000-000000000001/backups/2026-10-30/030006-1dd95df1d65642b1a2ffb848c96d9242/docassemble.tar.age/manifest.json","ciphertext_size_bytes":56074,"part_count":1,"all_part_checks_pass":true,"archive_checksum_pass":true,"age_header_present":true}
```

The listing contained two objects: one completion manifest (319 bytes) and its ciphertext part. The 56,074-byte figure is the archive size from the manifest, independently checked against the downloaded ciphertext. SHA-256 checks and the age header establish ciphertext integrity/format, not decryptability or database consistency. No plaintext was downloaded, no private identity was accessed, and no local archive was retained.

## Commands and results

Executed on Boston; existing authenticated storage code handled its credentials internally without returning values. No environment dump, raw application logs, SQL, backup invocation, deployment or production mutation was performed.

```sh
git fetch origin main
ls AGENTS.md docs/build/MILESTONES-28OCT-1NOV.md docs/build/TONIGHT-2026-10-27.md
git rev-parse HEAD
```

All succeeded; HEAD is the full SHA above. The initial repo-root `TONIGHT-2026-10-27.md` lookup failed; coordinator corrected the path before this audit resumed.

```sh
date -u '+UTC %Y-%m-%d %H:%M:%S'
TZ=America/Los_Angeles date '+PDT %Y-%m-%d %H:%M:%S'
docker ps -a --filter name=backup --format '{{.Names}} status={{.Status}}'
```

Output at 09:36:32 PDT / 16:36:32 UTC: only `docassemble-backup-iumzytsbbvjn2ah2wmlvuiyk-20261028T194340 status=Up 38 hours`. This bounded inventory does not exclude backups scheduled outside Docker or deleted containers.

```sh
docker exec docassemble-backup-iumzytsbbvjn2ah2wmlvuiyk-20261028T194340 python -c 'import os,json; names=["R2_ACCOUNT_ID","R2_ACCESS_KEY_ID_ZENAS","R2_SECRET_ACCESS_KEY_ZENAS","R2_BACKUP_RECIPIENT"]; print(json.dumps({n:bool(os.environ.get(n)) for n in names}))'
```

Exit 0: all four booleans `true`.

Exact encrypted-object verification command (exit 0, JSON shown above):

```sh
docker exec docassemble-backup-iumzytsbbvjn2ah2wmlvuiyk-20261028T194340 python -c 'import sys,asyncio,json,hashlib; sys.path.insert(0,"jobs/train"); from r2_archive import Storage,PLATFORM_TENANT
async def main():
 s=Storage("zenas")
 try:
  rows=await s.objects(PLATFORM_TENANT,"backups",public=False)
  key=sorted(r["key"] for r in rows if r["key"].endswith("/docassemble.tar.age/manifest.json"))[-1]
  name=key.split("/backups/",1)[1]; m=json.loads(await s.get(PLATFORM_TENANT,"backups",name,public=False)); h=hashlib.sha256(); total=0; valid=True; age=False
  for i,p in enumerate(m["parts"]):
   b=await s.get(PLATFORM_TENANT,"backups",p["name"],public=False); total+=len(b); h.update(b); valid=valid and len(b)==p["size_bytes"] and hashlib.sha256(b).hexdigest()==p["sha256"]
   if i==0: age=b.startswith(b"age-encryption.org/v1\n")
  print(json.dumps({"bucket":s.bucket,"key":key,"ciphertext_size_bytes":m["size_bytes"],"part_count":len(m["parts"]),"all_part_checks_pass":valid,"archive_checksum_pass":h.hexdigest()==m["sha256"] and total==m["size_bytes"],"age_header_present":age}))
 finally: await s.close()
try: asyncio.run(main())
except Exception as e: print(json.dumps({"error_type":type(e).__name__})); sys.exit(1)'
```

```sh
gh api repos/Tervory-AI/tervory-tank/actions/variables/ZA_OFFLINE --jq '{name: .name, value: .value}'
```

Exit 0: `{"name":"ZA_OFFLINE","value":"true"}`. Installed `gh variable get` was unsupported; the API read above succeeded. This is an operations variable, not a secret.

```sh
gh pr view 217 -R Tervory-AI/tervory-tank --json body --jq .body
gh pr view 357 -R Tervory-AI/tervory-tank --json body --jq .body
gh pr view 370 -R Tervory-AI/tervory-tank --json number,state,mergedAt,body
```

All succeeded. #217 explicitly separates private-identity decryption from the worker/CI; #357 supplies an encrypted ZA reassembly procedure, followed by founder-side decryption and TOC listing, without SQL count/time proof. #370 supplies historical Qdrant restore proof, not SQL restore proof; its statement that Postgres was proved earlier is not the underlying evidence.

## Source boundaries and exact blocker

- `agents/zenas/docassemble/backup.py:81–94` archives `docassemble.tar.age`; `:99–113` schedules it at 03:00 UTC. This is separate from main SQL backups.
- `jobs/train/backup.py:203–210` archives `database.dump.age` for main SQL.
- `docker-compose.yml:309–312` makes Boston `r2-backup` opt-in.
- `docs/cursor/ZA-R2-BACKUP-PROVE-RESTORE.md:61–113` keeps decryption founder-side; encrypted reassembly and `pg_restore --list` are not a throwaway SQL restore/count comparison.
- `docs/build/TONIGHT-2026-10-27.md:59–64` requires a dated backup, throwaway Postgres restore, matching `tank.ledger`, `tank.tasks`, `base.records` counts, and restore duration.

Missing: a currently established, approved SQL restore interface/proof that performs decryption without exposing private identity, restores into isolated throwaway Postgres, and supplies independently recorded comparison counts and elapsed time. Production SQL remains prohibited by the current assignment. No counts, duration, successful SQL restore, founder screenshots or M0 completion are claimed. Founder acceptance remains last. No health compose file was changed; watchdog owner was informed separately.
