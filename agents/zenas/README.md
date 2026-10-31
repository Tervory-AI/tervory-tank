# Zenas gold candidates

`GET /gold/candidates` is room-key only. It labels public worked matters and statute sections already stored on this box. It does not call a model, and it does not read another tenant's rows.

Every auto row has `label_family`:

- Worked matters: `converted:{source_id}:YYYY-MM`. The month is the matter's `as_at`, then the day it was saved, then when the court text was first seen, then the court's own date.
- Statute sections: `statute_section:{source_id}:YYYY-MM`. The month is when the section was first seen, then when it was captured, then its effective date, then the document date.

A row with no usable date is not emitted. Two months are two families. Held-out rows stay `holdout: true` and are not trained on. A row marked synthetic uses a family whose name contains `synthetic`.

`label_source` stays per row, as before.

## Docassemble raw compose

`docker-compose.docassemble.yml` (Boston, `zenas-docassemble`) and
`docker-compose.docassemble.za.yml` (ZA, `zenas-docassemble-za`) start with
`# coolify: raw compose`. In Coolify's normal mode the `docassemble` service would also
join Coolify's internet-facing app network, which breaks the seal on the internal
`tervory-zenas-assembly` network (SEAL-1). Merging the files changes nothing live:
deploy-on-merge skips these resources. Live steps, done once per resource and in this order:

1. Boston: `docker volume ls --format '{{.Name}}' | grep iumzytsbbvjn2ah2wmlvuiyk`.
   It must list `iumzytsbbvjn2ah2wmlvuiyk_docassemble-us-backup`. If the name differs,
   fix `volumes.docassemble_us_backup.name` first.
2. ZA: find the normal-mode volume (`docker volume ls | grep _docassemble-za-backup`).
   With the resource stopped, copy it once into the fixed name:
   `docker volume create tervory-zenas-docassemble-za-backup && docker run --rm -v <old>:/from:ro -v tervory-zenas-docassemble-za-backup:/to alpine cp -a /from/. /to/`
3. In Coolify: open the resource, go to **Advanced**, turn on **Raw Compose
   Deployment**, then redeploy. Coolify's API does not offer this setting.
4. Check that `docassemble` is on `tervory-zenas-assembly` only
   (`docker inspect -f '{{json .NetworkSettings.Networks}}' <container>`), and that
   `http://127.0.0.1/health_check?ready=1` answers inside it.
