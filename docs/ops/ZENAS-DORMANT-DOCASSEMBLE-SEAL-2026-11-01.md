# Dormant Docassemble definitions: seal and backup preservation

This change hardens retained definitions. It does not approve restarting Docassemble,
retiring its clients, changing Zenas architecture, or deleting data or backups.

## Current topology and limits

Checked against main `c5d6b10ed52e4b25afe8537d2da856cf8f27abcf`:

- Zenas still instantiates `DocassembleClient` in `agents/zenas/core/service.py`;
  the regional room definitions still use `http://docassemble`. Historical removal
  comments in quarantine are not evidence that the replacement shipped.
- Each retained Docassemble definition uses a separate regional image argument,
  its own backup volume and region, and the host-local external
  `tervory-zenas-assembly` network. The backup worker has its own outbound network
  and only a read-only mount of that region's backup volume.
- Read-only Boston inspection at 2026-11-01 08:47–08:49 UTC found a healthy
  `agent-zenas` on `tervory-zenas-assembly`, whose `internal` flag was `true`.
  No Docassemble container, stopped container, or Docassemble-named Docker volume
  was found. This does not prove that retained archives or differently named
  volumes are absent.
- The separately owned ZA readiness inspection reported a host-local assembly
  network with `internal=true`, no Docassemble application/container, and an absent
  `DOCASSEMBLE_API_KEY`. Its source was the ZA readiness report for PR #538,
  `/home/ammosync/.codex/za-readiness-20261101/readiness-report.txt`.
  Boston inspection is not evidence of ZA runtime state.
- Backup code, regional restore contracts and historical encrypted archives remain
  dependencies. Retirement and the replacement drafting architecture are unresolved;
  this change preserves them. A healthy room is not proof that drafting works.

## Configuration safeguards

Both retained files now start with `# coolify: raw compose`, so the private service
is not implicitly attached to Coolify's app network. No public port or routing
label is added. The repaired assembly networks and active room files are untouched.

Raw compose must preserve storage identity. Each backup volume is therefore
`external: true` and requires its own existing-volume selector:
`DOCASSEMBLE_US_BACKUP_VOLUME` or `DOCASSEMBLE_ZA_BACKUP_VOLUME`.
There is no default, guessed name, automatic creation or data migration.
An empty selector fails Compose validation; a nonexistent selected volume fails
startup instead of creating an empty replacement. Compose does not remove an
external volume when taking the stack down.

Before any separately approved future deployment, the owner must resolve the
retirement decision, identify the actual retained regional volume and restore
requirements, and verify the matching host-local assembly network is internal.
Do not create a new volume to satisfy this setting or copy Boston data to ZA.
This PR neither supplies setting values nor starts either dormant resource.

## Validation, deploy scope and rollback

The room-seal suite checks both actual raw-mode isolation and the normal-mode
counterexample, external network identity, required regional selectors and shared
read-only backup mounts. Only the two now-fixed strict XFAILs and their allow-list
entries are removed. Both definitions also pass `docker compose config` with
isolated placeholder credentials and reject an omitted volume selector. No build,
container start, fixture database, production SQL or provider call is involved.

`deploy_changed.py` maps paths under `agents/zenas/` to `agent-zenas` and its ZA copy;
these changes do not select the historical separate Docassemble resources. No
runtime action is performed by this task. Integration must follow normal review
and deploy coordination. Rollback is a git revert, with no volume or network
removal. Reverting reintroduces the seal defect and is not a reason to restart
Docassemble in normal mode.
