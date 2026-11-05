# Boston routing inventory

Read-only Docker/Coolify snapshot, 5 November 2026. 66 running containers inspected. Sign-in is inventoried only and is frozen. Chatwoot is unrelated infrastructure and is not migrated.

| Host/path rule | Container service | Port | Entrypoints | Middlewares | Docker network | Source before this PR |
| --- | --- | --- | --- | --- | --- | --- |
| Host(`auth.tervory.com`) && PathPrefix(`/ui/v2/login`) | trigger-signin-login | 3000 | https | none | coolify | in code |
| Host(`auth.tervory.com`) && Path(`/`) | trigger-signin-login | 3000 | https | trigger-signin-root | coolify | in code |
| Host(`auth.tervory.com`) | trigger-signin-api | 8080 | https | none | coolify | in code |
| Host(`mcp.tervory.com`) && PathPrefix(`/`) | mcp | 8000 | default | redirect-to-https | xnmc0jkz8j9i5jh1jwanbsfv | UI only |
| Host(`www.mcp.tervory.com`) && PathPrefix(`/`) | mcp | 8000 | default | redirect-to-https | xnmc0jkz8j9i5jh1jwanbsfv | UI only |
| Host(`mcp.tervory.com`) && PathPrefix(`/`) | mcp | 8000 | default | gzip-sse | xnmc0jkz8j9i5jh1jwanbsfv | UI only |
| Host(`www.mcp.tervory.com`) && PathPrefix(`/`) | mcp | 8000 | default | gzip-sse | xnmc0jkz8j9i5jh1jwanbsfv | UI only |
| Host(`rf7e2jfdkabsno5nuaxwdpkk.2.25.250.28.sslip.io`) && PathPrefix(`/`) | workspace | 3000 | default | gzip-sse | xnmc0jkz8j9i5jh1jwanbsfv | UI only |
| Host(`app.tervory.com`) && PathPrefix(`/`) | workspace | 3000 | default | redirect-to-https | xnmc0jkz8j9i5jh1jwanbsfv | UI only |
| Host(`skala.tervory.com`) && PathPrefix(`/`) | workspace | 3000 | default | redirect-to-https | xnmc0jkz8j9i5jh1jwanbsfv | UI only |
| Host(`tank.tervory.com`) && PathPrefix(`/`) | workspace | 3000 | default | redirect-to-https | xnmc0jkz8j9i5jh1jwanbsfv | UI only |
| Host(`rig.tervory.com`) && PathPrefix(`/`) | workspace | 3000 | default | redirect-to-https | xnmc0jkz8j9i5jh1jwanbsfv | UI only |
| Host(`protect.tervory.com`) && PathPrefix(`/`) | workspace | 3000 | default | redirect-to-https | xnmc0jkz8j9i5jh1jwanbsfv | UI only |
| Host(`autumbra.tervory.com`) && PathPrefix(`/`) | workspace | 3000 | default | redirect-to-https | xnmc0jkz8j9i5jh1jwanbsfv | UI only |
| Host(`zenas.tervory.com`) && PathPrefix(`/`) | workspace | 3000 | default | redirect-to-https | xnmc0jkz8j9i5jh1jwanbsfv | UI only |
| Host(`base.tervory.com`) && PathPrefix(`/`) | workspace | 3000 | default | redirect-to-https | xnmc0jkz8j9i5jh1jwanbsfv | UI only |
| Host(`tiger.tervory.com`) && PathPrefix(`/`) | workspace | 3000 | default | redirect-to-https | xnmc0jkz8j9i5jh1jwanbsfv | UI only |
| Host(`market-lab.tervory.com`) && PathPrefix(`/`) | workspace | 3000 | default | redirect-to-https | xnmc0jkz8j9i5jh1jwanbsfv | UI only |
| Host(`tisan.tervory.com`) && PathPrefix(`/`) | workspace | 3000 | default | redirect-to-https | xnmc0jkz8j9i5jh1jwanbsfv | UI only |
| Host(`radix.tervory.com`) && PathPrefix(`/`) | workspace | 3000 | default | redirect-to-https | xnmc0jkz8j9i5jh1jwanbsfv | UI only |
| Host(`app.tervory.com`) && PathPrefix(`/`) | workspace | 3000 | default | gzip-sse | xnmc0jkz8j9i5jh1jwanbsfv | UI only |
| Host(`skala.tervory.com`) && PathPrefix(`/`) | workspace | 3000 | default | gzip-sse | xnmc0jkz8j9i5jh1jwanbsfv | UI only |
| Host(`tank.tervory.com`) && PathPrefix(`/`) | workspace | 3000 | default | gzip-sse | xnmc0jkz8j9i5jh1jwanbsfv | UI only |
| Host(`rig.tervory.com`) && PathPrefix(`/`) | workspace | 3000 | default | gzip-sse | xnmc0jkz8j9i5jh1jwanbsfv | UI only |
| Host(`protect.tervory.com`) && PathPrefix(`/`) | workspace | 3000 | default | gzip-sse | xnmc0jkz8j9i5jh1jwanbsfv | UI only |
| Host(`autumbra.tervory.com`) && PathPrefix(`/`) | workspace | 3000 | default | gzip-sse | xnmc0jkz8j9i5jh1jwanbsfv | UI only |
| Host(`zenas.tervory.com`) && PathPrefix(`/`) | workspace | 3000 | default | gzip-sse | xnmc0jkz8j9i5jh1jwanbsfv | UI only |
| Host(`base.tervory.com`) && PathPrefix(`/`) | workspace | 3000 | default | gzip-sse | xnmc0jkz8j9i5jh1jwanbsfv | UI only |
| Host(`tiger.tervory.com`) && PathPrefix(`/`) | workspace | 3000 | default | gzip-sse | xnmc0jkz8j9i5jh1jwanbsfv | UI only |
| Host(`market-lab.tervory.com`) && PathPrefix(`/`) | workspace | 3000 | default | gzip-sse | xnmc0jkz8j9i5jh1jwanbsfv | UI only |
| Host(`tisan.tervory.com`) && PathPrefix(`/`) | workspace | 3000 | default | gzip-sse | xnmc0jkz8j9i5jh1jwanbsfv | UI only |
| Host(`radix.tervory.com`) && PathPrefix(`/`) | workspace | 3000 | default | gzip-sse | xnmc0jkz8j9i5jh1jwanbsfv | UI only |
| Host(`tervory.com`) && PathPrefix(`/`) | site | 3000 | default | redirect-to-https | xnmc0jkz8j9i5jh1jwanbsfv | UI only |
| Host(`tervory.com`) && PathPrefix(`/`) | site | 3000 | default | gzip-sse | xnmc0jkz8j9i5jh1jwanbsfv | UI only |
| Host(`rig.tervory.com`) && (Path(`/v1/rig`) \|\| PathPrefix(`/v1/rig/`) \|\| Path(`/widget`) \|\| PathPrefix(`/widget/`) \|\| Path(`/3d`) \|\| PathPrefix(`/3d/`) \|\| Path(`/page`) \|\| PathPrefix(`/page/`) \|\| Path(`/product`) \|\| PathPrefix(`/product/`) \|\| Path(`/v5`) \|\| PathPrefix(`/v5/`) \|\| Path(`/cn-classic`) \|\| Path(`/house`) \|\| Path(`/health`) \|\| Path(`/storage`) \|\| PathPrefix(`/storage/`)) | agent-rig | 8000 | http | redirect-to-https | 59f8cnpelzwsyte1atyjc4fv | in code |
| Host(`rig.tervory.com`) && (Path(`/v1/rig`) \|\| PathPrefix(`/v1/rig/`) \|\| Path(`/widget`) \|\| PathPrefix(`/widget/`) \|\| Path(`/3d`) \|\| PathPrefix(`/3d/`) \|\| Path(`/page`) \|\| PathPrefix(`/page/`) \|\| Path(`/product`) \|\| PathPrefix(`/product/`) \|\| Path(`/v5`) \|\| PathPrefix(`/v5/`) \|\| Path(`/cn-classic`) \|\| Path(`/house`) \|\| Path(`/health`) \|\| Path(`/storage`) \|\| PathPrefix(`/storage/`)) | agent-rig | 8000 | https | rig-gzip | 59f8cnpelzwsyte1atyjc4fv | in code |
| Host(`crm.tervory.com`) && PathPrefix(`/`) | frontend | 3000 | default | redirect-to-https | aty7tukal0rlksfpet1mzplb | UI only |
| Host(`crm.tervory.com`) && PathPrefix(`/`) | frontend | 3000 | default | gzip-sse | aty7tukal0rlksfpet1mzplb | UI only |
| Host(`crm.tervory.com`) && PathPrefix(`/healthz`) | backend | 8000 | default | redirect-to-https | aty7tukal0rlksfpet1mzplb | UI only |
| Host(`crm.tervory.com`) && PathPrefix(`/api`) | backend | 8000 | default | redirect-to-https | aty7tukal0rlksfpet1mzplb | UI only |
| Host(`crm.tervory.com`) && PathPrefix(`/admin`) | backend | 8000 | default | redirect-to-https | aty7tukal0rlksfpet1mzplb | UI only |
| Host(`crm.tervory.com`) && PathPrefix(`/static`) | backend | 8000 | default | redirect-to-https | aty7tukal0rlksfpet1mzplb | UI only |
| Host(`crm.tervory.com`) && PathPrefix(`/healthz`) | backend | 8000 | default | gzip-sse | aty7tukal0rlksfpet1mzplb | UI only |
| Host(`crm.tervory.com`) && PathPrefix(`/api`) | backend | 8000 | default | gzip-sse | aty7tukal0rlksfpet1mzplb | UI only |
| Host(`crm.tervory.com`) && PathPrefix(`/admin`) | backend | 8000 | default | gzip-sse | aty7tukal0rlksfpet1mzplb | UI only |
| Host(`crm.tervory.com`) && PathPrefix(`/static`) | backend | 8000 | default | gzip-sse | aty7tukal0rlksfpet1mzplb | UI only |
| Host(`chat.ammosync.com`) && PathPrefix(`/`) | chatwoot | 3000 | default | redirect-to-https | wefornkolxs7kw194xbdyf1b | UI only |
| Host(`chat.ammosync.com`) && PathPrefix(`/`) | chatwoot | 3000 | default | gzip | wefornkolxs7kw194xbdyf1b | UI only |

Containers without Traefik routers (57): `identity-backup-zhcgyuamty89bbv6wpn0tgey`, `identity-postgres-zhcgyuamty89bbv6wpn0tgey`, `tank-xnmc0jkz8j9i5jh1jwanbsfv-20261105T195918`, `hermes-xnmc0jkz8j9i5jh1jwanbsfv-20261105T195917`, `r2-backup-xnmc0jkz8j9i5jh1jwanbsfv-20261105T195918`, `searxng-xnmc0jkz8j9i5jh1jwanbsfv-20261105T195917`, `postgres-xnmc0jkz8j9i5jh1jwanbsfv-20261105T195917`, `litellm-xnmc0jkz8j9i5jh1jwanbsfv-20261105T195917`, `qdrant-xnmc0jkz8j9i5jh1jwanbsfv-20261105T195917`, `redis-xnmc0jkz8j9i5jh1jwanbsfv-20261105T195917`, `tiger-xnmc0jkz8j9i5jh1jwanbsfv-20261105T195918`, `market-research-xnmc0jkz8j9i5jh1jwanbsfv-20261105T195918`, `Ferry-xnmc0jkz8j9i5jh1jwanbsfv-20261105T195917`, `figma-egress-proxy-lblbn0wjaz30hhdur9l3pylg-20261105T184951`, `agent-tisan-lblbn0wjaz30hhdur9l3pylg-20261105T184951`, `agent-zenas-r7qzm460bc4scnskurlowbvn-20261105T121331`, `yzq4jrwa6fipvwb7lzcx4nmo-agent-trigger-1`, `yzq4jrwa6fipvwb7lzcx4nmo-trigger-languagetool-1`, `fro6z8xlh579owlp1wwrjr8n-agent-tiger-1`, `fro6z8xlh579owlp1wwrjr8n-tiger-browser-gateway-1`, `fro6z8xlh579owlp1wwrjr8n-tiger-browser-1`, `59f8cnpelzwsyte1atyjc4fv-rig-brain-1`, `59f8cnpelzwsyte1atyjc4fv-rig-forge-1`, `59f8cnpelzwsyte1atyjc4fv-rig-forge-egress-1`, `59f8cnpelzwsyte1atyjc4fv-rig-browser-1`, `59f8cnpelzwsyte1atyjc4fv-rig-browser-gateway-1`, `59f8cnpelzwsyte1atyjc4fv-rig-sandbox-1`, `liv4x7vshraiwnnowjv0kgfd-agent-radix-1`, `liv4x7vshraiwnnowjv0kgfd-egress-proxy-1`, `liv4x7vshraiwnnowjv0kgfd-passive-egress-1`, `agent-market-lab-xt0vc7rnr45flw2wg3iyjpmn-20261105T114114`, `r8aprclj8nooe9keywrp9dmb-base-brain-1`, `r8aprclj8nooe9keywrp9dmb-agent-base-1`, `r8aprclj8nooe9keywrp9dmb-base-browser-1`, `r8aprclj8nooe9keywrp9dmb-base-sandbox-1`, `r8aprclj8nooe9keywrp9dmb-base-browser-gateway-1`, `coolify-sentinel`, `coolify`, `coolify-db`, `coolify-redis`, `gbcrtd9bij6hnhrbd6ljvo1g-health-egress-proxy-1`, `gbcrtd9bij6hnhrbd6ljvo1g-egress-proxy-1`, `gbcrtd9bij6hnhrbd6ljvo1g-enforce-1`, `gbcrtd9bij6hnhrbd6ljvo1g-health-observer-1`, `celery-beat-aty7tukal0rlksfpet1mzplb-20261103T111814`, `celery-worker-aty7tukal0rlksfpet1mzplb-20261103T111814`, `redis-aty7tukal0rlksfpet1mzplb-20261103T111814`, `kuma-socat-tunnel`, `uptime-kuma-m24wvavrazt3s6lovfwu2ffp`, `agent-ghost-nypsvvcxjpdebaa204smtqtd-20261027T121359`, `ghost-browser-nypsvvcxjpdebaa204smtqtd-20261027T121359`, `agent-template-jodjyt6vsyoyhfr6axtuc8ij-20261027T104918`, `sidekiq-wefornkolxs7kw194xbdyf1b`, `redis-wefornkolxs7kw194xbdyf1b`, `coolify-proxy`, `postgres-wefornkolxs7kw194xbdyf1b`, `coolify-proxy-error-pages`.

## Coolify application UI domains (all applications)

| Application ID | Application | Service | Domains |
| --- | --- | --- | --- |
| 15 | tervory-tank-za | tank | https://za.tervory.com |
| 1 | tervory-tank:main-xnmc0jkz8j9i5jh1jwanbsfv | workspace | http://rf7e2jfdkabsno5nuaxwdpkk.2.25.250.28.sslip.io,https://app.tervory.com,https://protect.tervory.com,https://autumbra.tervory.com,https://zenas.tervory.com,https://base.tervory.com,https://tiger.tervory.com,https://market-lab.tervory.com,https://tisan.tervory.com,https://radix.tervory.com,https://skala.tervory.com,https://tank.tervory.com,https://rig.tervory.com |
| 1 | tervory-tank:main-xnmc0jkz8j9i5jh1jwanbsfv | site | https://tervory.com |
| 1 | tervory-tank:main-xnmc0jkz8j9i5jh1jwanbsfv | mcp | https://mcp.tervory.com,https://www.mcp.tervory.com |
| 14 | Autumbra | — | none |
| 4 | agent-tiger | — | none |
| 3 | agent-template | — | none |
| 18 | agent-zenas-za | — | none |
| 5 | agent-market-lab | — | none |
| 8 | agent-zenas | — | none |
| 6 | agent-radix | — | none |
| 7 | agent-tisan | — | none |
| 19 | agent-trigger | — | none |
| 9 | agent-base | — | none |
| 12 | agent-rig | agent-rig | https://rig.tervory.com |
| 20 | trigger-crm | frontend | https://crm.tervory.com |
| 20 | trigger-crm | backend | https://crm.tervory.com/healthz,https://crm.tervory.com/api,https://crm.tervory.com/admin,https://crm.tervory.com/static |
| 23 | Autumbra Enforce - tervory.com | — | none |
