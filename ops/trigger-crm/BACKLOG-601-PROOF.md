# PR 601 verification — 4 November 2026

Checked current main `fa34a9f0d9e8323358ebb47c82ba5e9f2eed9fab` and PR head
`5ba3296a0faa00e060051d50a60e136409c03ace` through GitHub. Main still has
file-based connector configs and no Dockerfile.backend. The existing repair
remains necessary; GitHub reported it mergeable. No main merge was needed.

## Decisions I made

Keep the existing narrow repair: build the pinned upstream image for the worker,
then use its service build context as `crm-pinned` and COPY only the two connector
files into the backend image. Keep upstream SHA, startup command, network alias,
entrypoint and command inheritance. No runtime application or database is started
for verification. No production change was made.

Add `.github/workflows/trigger-crm-image.yml` to make the isolated proof repeatable
on the PR's merged head: validate Compose without interpolating settings, build
only the backend and its pinned dependency with disposable image tags, compare
inherited image configuration, and inspect the baked files in a read-only,
network-disabled container with the application entrypoint overridden. The
workflow uses no secrets, registry push, application startup, migration or deploy.

## Results and remaining evidence

- Local Docker Compose v5.6.0 config validation passed.
- Parsed build graph confirms the pinned commit for worker/beat/frontend,
  backend service context, no configs or backend volumes, existing gunicorn
  command and `trigger-crm-backend` alias.
- Workflow YAML and both bash blocks parse successfully.
- `tests/test_trigger_crm_wsgi.py`: 4 passed, sockets disabled.
- Required CI Ruff E9/F check: All checks passed.
- Image build is NOT claimed: this session cannot access `/var/run/docker.sock`.
- Publish and final-head hosted image/CI results are pending. Git push fails
  `Could not resolve host: github.com`; the GitHub write connector returns
  `MCP tool call requires approval, but approval policy is never`.

Once this session can publish, push this existing PR branch and require the
`bake-connector` job and normal hosted CI to pass on the final head. Do not deploy
as part of this proof. Automatic main/ZA deployment prefixes do not include
`ops/trigger-crm/`; applying this CRM overlay remains a separate operational act.
