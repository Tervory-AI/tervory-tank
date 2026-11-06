# Product hosts — routing contract

The JSON table below is the single machine-readable ingress authority. `paths` is a restricted Traefik predicate (Path, PathPrefix, parentheses, !, &&, ||). Each row describes one HTTPS router/host; the matching HTTP router redirects to HTTPS. Explicit exclusions are part of the contract, including the Rig API/app split. A new host, path, port, network or protection class requires an explicit reviewed table change.

```json
[
  {
    "host": "rig.tervory.com",
    "paths": "(Path(`/v1/rig`) || PathPrefix(`/v1/rig/`) || Path(`/widget`) || PathPrefix(`/widget/`) || Path(`/3d`) || PathPrefix(`/3d/`) || Path(`/page`) || PathPrefix(`/page/`) || Path(`/product`) || PathPrefix(`/product/`) || Path(`/v5`) || PathPrefix(`/v5/`) || Path(`/cn-classic`) || Path(`/house`) || Path(`/health`) || Path(`/storage`) || PathPrefix(`/storage/`))",
    "service": "agent-rig",
    "port": 8000,
    "network": "59f8cnpelzwsyte1atyjc4fv",
    "access": "public",
    "compose": "agents/rig/docker-compose.yml",
    "router": "rig-https",
    "priority": 1000
  },
  {
    "host": "app.tervory.com",
    "paths": "PathPrefix(`/`) && !PathPrefix(`/admin`) && !PathPrefix(`/internal`)",
    "service": "workspace",
    "port": 3000,
    "network": "xnmc0jkz8j9i5jh1jwanbsfv",
    "access": "public",
    "compose": "docker-compose.yml",
    "router": "product-workspace-https",
    "priority": 100
  },
  {
    "host": "base.tervory.com",
    "paths": "PathPrefix(`/`) && !PathPrefix(`/admin`) && !PathPrefix(`/internal`)",
    "service": "workspace",
    "port": 3000,
    "network": "xnmc0jkz8j9i5jh1jwanbsfv",
    "access": "public",
    "compose": "docker-compose.yml",
    "router": "product-workspace-https",
    "priority": 100
  },
  {
    "host": "tiger.tervory.com",
    "paths": "PathPrefix(`/`) && !PathPrefix(`/admin`) && !PathPrefix(`/internal`)",
    "service": "workspace",
    "port": 3000,
    "network": "xnmc0jkz8j9i5jh1jwanbsfv",
    "access": "public",
    "compose": "docker-compose.yml",
    "router": "product-workspace-https",
    "priority": 100
  },
  {
    "host": "market-lab.tervory.com",
    "paths": "PathPrefix(`/`) && !PathPrefix(`/admin`) && !PathPrefix(`/internal`)",
    "service": "workspace",
    "port": 3000,
    "network": "xnmc0jkz8j9i5jh1jwanbsfv",
    "access": "public",
    "compose": "docker-compose.yml",
    "router": "product-workspace-https",
    "priority": 100
  },
  {
    "host": "tisan.tervory.com",
    "paths": "PathPrefix(`/`) && !PathPrefix(`/admin`) && !PathPrefix(`/internal`)",
    "service": "workspace",
    "port": 3000,
    "network": "xnmc0jkz8j9i5jh1jwanbsfv",
    "access": "public",
    "compose": "docker-compose.yml",
    "router": "product-workspace-https",
    "priority": 100
  },
  {
    "host": "radix.tervory.com",
    "paths": "PathPrefix(`/`) && !PathPrefix(`/admin`) && !PathPrefix(`/internal`)",
    "service": "workspace",
    "port": 3000,
    "network": "xnmc0jkz8j9i5jh1jwanbsfv",
    "access": "public",
    "compose": "docker-compose.yml",
    "router": "product-workspace-https",
    "priority": 100
  },
  {
    "host": "skala.tervory.com",
    "paths": "PathPrefix(`/`) && !PathPrefix(`/admin`) && !PathPrefix(`/internal`)",
    "service": "workspace",
    "port": 3000,
    "network": "xnmc0jkz8j9i5jh1jwanbsfv",
    "access": "public",
    "compose": "docker-compose.yml",
    "router": "product-workspace-https",
    "priority": 100
  },
  {
    "host": "tank.tervory.com",
    "paths": "PathPrefix(`/`) && !PathPrefix(`/admin`) && !PathPrefix(`/internal`)",
    "service": "workspace",
    "port": 3000,
    "network": "xnmc0jkz8j9i5jh1jwanbsfv",
    "access": "public",
    "compose": "docker-compose.yml",
    "router": "product-workspace-https",
    "priority": 100
  },
  {
    "host": "zenas.tervory.com",
    "paths": "PathPrefix(`/`) && !PathPrefix(`/admin`) && !PathPrefix(`/internal`)",
    "service": "workspace",
    "port": 3000,
    "network": "xnmc0jkz8j9i5jh1jwanbsfv",
    "access": "public",
    "compose": "docker-compose.yml",
    "router": "product-workspace-https",
    "priority": 100
  },
  {
    "host": "autumbra.tervory.com",
    "paths": "PathPrefix(`/`) && !PathPrefix(`/admin`) && !PathPrefix(`/internal`)",
    "service": "workspace",
    "port": 3000,
    "network": "xnmc0jkz8j9i5jh1jwanbsfv",
    "access": "public",
    "compose": "docker-compose.yml",
    "router": "product-workspace-https",
    "priority": 100
  },
  {
    "host": "protect.tervory.com",
    "paths": "PathPrefix(`/`) && !PathPrefix(`/admin`) && !PathPrefix(`/internal`)",
    "service": "workspace",
    "port": 3000,
    "network": "xnmc0jkz8j9i5jh1jwanbsfv",
    "access": "public",
    "compose": "docker-compose.yml",
    "router": "product-workspace-https",
    "priority": 100
  },
  {
    "host": "opli.tervory.com",
    "paths": "PathPrefix(`/`) && !PathPrefix(`/admin`) && !PathPrefix(`/internal`)",
    "service": "workspace",
    "port": 3000,
    "network": "xnmc0jkz8j9i5jh1jwanbsfv",
    "access": "public",
    "compose": "docker-compose.yml",
    "router": "product-workspace-https",
    "priority": 100
  },
  {
    "host": "window.tervory.com",
    "paths": "PathPrefix(`/`) && !PathPrefix(`/admin`) && !PathPrefix(`/internal`)",
    "service": "workspace",
    "port": 3000,
    "network": "xnmc0jkz8j9i5jh1jwanbsfv",
    "access": "public",
    "compose": "docker-compose.yml",
    "router": "product-workspace-https",
    "priority": 100
  },
  {
    "host": "mobile.tervory.com",
    "paths": "PathPrefix(`/`) && !PathPrefix(`/admin`) && !PathPrefix(`/internal`)",
    "service": "workspace",
    "port": 3000,
    "network": "xnmc0jkz8j9i5jh1jwanbsfv",
    "access": "public",
    "compose": "docker-compose.yml",
    "router": "product-workspace-https",
    "priority": 100
  },
  {
    "host": "rig.tervory.com",
    "paths": "PathPrefix(`/`) && !(Path(`/v1/rig`) || PathPrefix(`/v1/rig/`) || Path(`/widget`) || PathPrefix(`/widget/`) || Path(`/3d`) || PathPrefix(`/3d/`) || Path(`/page`) || PathPrefix(`/page/`) || Path(`/product`) || PathPrefix(`/product/`) || Path(`/v5`) || PathPrefix(`/v5/`) || Path(`/cn-classic`) || Path(`/house`) || Path(`/health`) || Path(`/storage`) || PathPrefix(`/storage/`)) && !PathPrefix(`/admin`) && !PathPrefix(`/internal`)",
    "service": "workspace",
    "port": 3000,
    "network": "xnmc0jkz8j9i5jh1jwanbsfv",
    "access": "public",
    "compose": "docker-compose.yml",
    "router": "product-rig-app-https",
    "priority": 100
  },
  {
    "host": "tervory.com",
    "paths": "PathPrefix(`/`) && !PathPrefix(`/admin`) && !PathPrefix(`/internal`)",
    "service": "site",
    "port": 3000,
    "network": "xnmc0jkz8j9i5jh1jwanbsfv",
    "access": "public",
    "compose": "docker-compose.yml",
    "router": "product-site-https",
    "priority": 100
  },
  {
    "host": "www.tervory.com",
    "paths": "PathPrefix(`/`) && !PathPrefix(`/admin`) && !PathPrefix(`/internal`)",
    "service": "site",
    "port": 3000,
    "network": "xnmc0jkz8j9i5jh1jwanbsfv",
    "access": "public",
    "compose": "docker-compose.yml",
    "router": "product-site-https",
    "priority": 100
  },
  {
    "host": "mcp.tervory.com",
    "paths": "PathPrefix(`/`) && !PathPrefix(`/admin`) && !PathPrefix(`/internal`)",
    "service": "mcp",
    "port": 8000,
    "network": "xnmc0jkz8j9i5jh1jwanbsfv",
    "access": "public",
    "compose": "docker-compose.yml",
    "router": "product-mcp-https",
    "priority": 100
  },
  {
    "host": "za.tervory.com",
    "paths": "PathPrefix(`/`) && !PathPrefix(`/admin`) && !PathPrefix(`/internal`)",
    "service": "tank",
    "port": 8000,
    "network": "9iwqimptdhspitnsgmv0imdl",
    "access": "public",
    "compose": "docker-compose.za.yml",
    "router": "product-za-tank-https",
    "priority": 100
  },
  {
    "host": "crm.tervory.com",
    "paths": "(PathPrefix(`/healthz`) || PathPrefix(`/api`) || PathPrefix(`/admin`) || PathPrefix(`/static`))",
    "service": "backend",
    "port": 8000,
    "network": "aty7tukal0rlksfpet1mzplb",
    "access": "Access-protected",
    "compose": "ops/trigger-crm/docker-compose.yml",
    "router": "product-crm-api-https",
    "priority": 1000
  },
  {
    "host": "crm.tervory.com",
    "paths": "PathPrefix(`/`) && !(PathPrefix(`/healthz`) || PathPrefix(`/api`) || PathPrefix(`/admin`) || PathPrefix(`/static`))",
    "service": "frontend",
    "port": 3000,
    "network": "aty7tukal0rlksfpet1mzplb",
    "access": "Access-protected",
    "compose": "ops/trigger-crm/docker-compose.yml",
    "router": "product-crm-app-https",
    "priority": 100
  },
  {
    "host": "auth.tervory.com",
    "paths": "PathPrefix(`/`)",
    "service": "trigger-signin-api",
    "port": 8080,
    "network": "${TRIGGER_SIGNIN_PROXY_NETWORK:?existing Coolify proxy network name}",
    "access": "public",
    "compose": "ops/trigger-signin/docker-compose.yml",
    "router": "trigger-signin-api",
    "priority": 100
  },
  {
    "host": "auth.tervory.com",
    "paths": "PathPrefix(`/ui/v2/login`)",
    "service": "trigger-signin-login",
    "port": 3000,
    "network": "${TRIGGER_SIGNIN_PROXY_NETWORK:?existing Coolify proxy network name}",
    "access": "public",
    "compose": "ops/trigger-signin/docker-compose.yml",
    "router": "trigger-signin-login",
    "priority": 200
  },
  {
    "host": "auth.tervory.com",
    "paths": "Path(`/`)",
    "service": "trigger-signin-login",
    "port": 3000,
    "network": "${TRIGGER_SIGNIN_PROXY_NETWORK:?existing Coolify proxy network name}",
    "access": "public",
    "compose": "ops/trigger-signin/docker-compose.yml",
    "router": "trigger-signin-root",
    "priority": 300
  }
]
```

## Protection and scope

Public catch-all routes reject /admin and /internal prefixes, including their children. Control ports (8003 and other non-web ports) are never implicitly exposed. CRM is founder-only behind the existing Cloudflare Access policy on the whole host; this PR neither creates nor verifies that external policy. Verify it at release before clearing UI domains. Access-protected is a deployment requirement, not proof supplied by a label. Sign-in routes are frozen, inventoried and checked for drift, but excluded from this migration and the new reserved-path exclusion requirement: do not edit or redeploy sign-in. Its existing public identity API policy is unchanged.

`opli`, `window` and `mobile` intentionally route to Workspace until a dedicated service is reviewed. The legacy IP-based sslip route is retired, never recreated by labels. Unrelated Chatwoot/Coolify infrastructure remains outside this product contract. Test-only compose stacks without routers still undergo Compose configuration validation.

## Coolify cutover — founder operation after merge

Do not clear live domains before the reviewed labels are available. This PR changes only repository files; no Coolify settings or live deployments were changed. On the deployment using these labels, clear these UI domains (also any corresponding preview domain overrides); retain every environment variable, volume and service:

- Application 15 `tervory-tank-za`, service `tank`: `https://za.tervory.com`.
- Application 1 `tervory-tank:main-xnmc0jkz8j9i5jh1jwanbsfv`, service `workspace`: `http://rf7e2jfdkabsno5nuaxwdpkk.2.25.250.28.sslip.io,https://app.tervory.com,https://protect.tervory.com,https://autumbra.tervory.com,https://zenas.tervory.com,https://base.tervory.com,https://tiger.tervory.com,https://market-lab.tervory.com,https://tisan.tervory.com,https://radix.tervory.com,https://skala.tervory.com,https://tank.tervory.com,https://rig.tervory.com`.
- Application 1 `tervory-tank:main-xnmc0jkz8j9i5jh1jwanbsfv`, service `site`: `https://tervory.com`.
- Application 1 `tervory-tank:main-xnmc0jkz8j9i5jh1jwanbsfv`, service `mcp`: `https://mcp.tervory.com,https://www.mcp.tervory.com`.
- Application 12 `agent-rig`, service `agent-rig`: `https://rig.tervory.com`.
- Application 20 `trigger-crm`, service `frontend`: `https://crm.tervory.com`.
- Application 20 `trigger-crm`, service `backend`: `https://crm.tervory.com/healthz,https://crm.tervory.com/api,https://crm.tervory.com/admin,https://crm.tervory.com/static`.

The existing per-resource proxy networks are declared external and joined only by the services that need ingress; the proxy must already be attached (as it is for the inventoried Boston applications). ZA uses its existing resource proxy network; verify its attachment during the regional cutover. No container or volume renames are introduced. Do not deploy fixed production-host labels as a preview: use a separate reviewed preview routing overlay, or leave previews undeployed.

## Why clearing the UI domains is necessary

Read-only inspection of the installed Coolify deployment job and parser distinguishes two modes. **Normal mode** (Boston main, ZA and CRM today): applicationParser retains custom compose labels, then merges `fqdnLabelsForTraefik` labels when UI domains are present. Distinct router names coexist, and generated catch-all rules can bypass path exclusions. **Raw mode** (agent-rig today): ApplicationDeploymentJob selects oldRawParser and the raw source compose instead of applicationParser; its stored UI domain does not create an additional router in the observed deployment. Clear the listed domain overrides anyway so a later mode change cannot resurrect a catch-all. Do not switch deployment modes as part of this cutover. Clear normal-mode UI domains in the same controlled deployment, not in a later unattended deploy. No settings were changed to test this.

Deploy-on-merge will redeploy Boston main and the ZA stack (root compose changes), and Trigger CRM (`ops/trigger-crm/`), following existing deployment selection. Rig source labels remain unchanged. New labels contain public hostnames, service names, paths and existing network identifiers only: no secret or IP address.

## Validation and application behavior

`python3 tests/test_routing.py` runs real `docker compose config` for every tracked Compose file, with synthetic required inputs and no inherited production environment. Coolify's existing boolean `exclude_from_hc` metadata is represented as an `x-coolify-exclude-from-hc` extension in the validation input, matching the installed parser's removal before Compose; all runtime fields and routing labels are validated unchanged. This never builds images or starts services. Unknown routing matchers, TCP/UDP routers, missing redirect pairs, undocumented rules and internal-only proxy networks fail closed. The CI `routing` job runs on every PR and merge group and gates `ci-ok`.

Workspace still performs its existing product-host rewrites: Autumbra/protect to `/autumbra`, Zenas to `/moot`, and the other product hosts to their product pages. Moot canonical redirects and existing signed-in tenant/role checks are unchanged. `/sign-in`, `/sign-up`, `/api/health`, deep links and Rig API/widget paths retain their existing application semantics. The ingress restriction deliberately removes public `/admin*` and `/internal*` routes, including legacy founder admin aliases; do not claim those aliases work until a separately reviewed Access-protected ingress is provided. Existing non-admin canonical product pages remain routed. No model, payment, skill approval, WAF or sign-in changes are included.
