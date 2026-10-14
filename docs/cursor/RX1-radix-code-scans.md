# RX-1 — Radix: code scans (no internet needed)

**Goal:** Radix's first three skills, all working on code handed to it, so its room stays internet-free. Build Pack: "Nothing ships without a scan."

**Files you may change:** `agents/radix/` (app, Dockerfile, README), `tank/skills/scan.secrets/1.0.0/`, `tank/skills/scan.dependencies/1.0.0/`, `tank/skills/scan.static/1.0.0/` (evals + CHANGELOG each), new tests. Not `docker-compose.yml`.

- **Input:** a tarball of a repo (or a git bundle) posted to Radix's job `scan` with `{tenant_id, source, ref}`. Radix never clones from the internet; the caller sends the files.
- **`scan.secrets`:** Gitleaks with a pinned version baked into the Radix image. Report `{type, file, line, rule}`. **Never store or return the secret value**: mask it in every output and log.
- **`scan.dependencies`:** offline vulnerability databases baked into the image at build time (OSV offline export; `npm audit` / `pip-audit` with an offline DB). Report package, version, advisory id, severity, fixed version.
- **`scan.static`:** Semgrep with pinned rule packs vendored into the image (no registry download at run time).
- **Result:** `findings` table in `agent_radix` (`tenant_id, scan_id, tool, severity, file, line, rule, fix`) plus a plain-English summary. Severity `critical` = the build must not deploy (Tisan reads this later).
- **Evals:** fixture repos with a planted fake key, a known-vulnerable dependency and an injection pattern; each must be found. A clean fixture must give zero criticals.
- **Tests prove:** no network call is made during a scan, and no secret value appears in output, logs or the database.

**Done when:** CI green; after deploy, a scan of the `tervory-rig` repo bundle produces a report with no secret values in it.
