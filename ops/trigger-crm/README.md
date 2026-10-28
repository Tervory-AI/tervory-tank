# ops/trigger-crm — BottleCRM (Trigger CRM)

| | |
|---|---|
| Upstream | https://github.com/Django-CRM/Django-CRM |
| Pin | **v1.39.0** @ `cd7c12a607df1719518fcdaf289864f6ba7d0bcd` |
| Coolify resource | `trigger-crm` |
| FQDN | `https://crm.tervory.com` (Cloudflare Access: founder only) |
| Health | `/healthz/` (backend) |
| Admin UI | `/` frontend; Django `/admin/` on backend |
| DB | Shared Boston Postgres: database `trigger_crm`, role `trigger_crm` (never tank). No compose `db`. |
| Corridor | `tervory-gw-trigger-crm` (create once; attach postgres + this resource) |

## Coolify

- `base_directory`: `ops/trigger-crm`
- `docker_compose_location`: `/docker-compose.yml`
- Build contexts pull Django-CRM @ v1.39.0 from GitHub (see compose).
- Env **names** only; founder fills values. Do not set `ENV_TYPE=prod`. Do not run `seed_data`.

## Env names

`SECRET_KEY`, `DBPASSWORD`, `DBHOST`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `EMAIL_USE_SSL`, `EMAIL_TIMEOUT`, `DEFAULT_FROM_EMAIL`, optional `EMAIL_BACKEND`, `ALLOWED_HOSTS`, `DOMAIN_NAME`, `DBNAME`, `DBUSER`, `DBPORT`, `PUBLIC_DJANGO_API_URL`, `TRUST_PROXY_SSL_HEADER`.

## API user (after live sign-in)

See **`TERVORY-CONNECTOR.md`**: create member `tervory-connector` in the founder org; founder mints the PAT under Settings → API Tokens with scopes `leads|contacts|invoices` read+write only. Never put the token in chat or git.

## Rule 11

See **`PROOF.md`** (scaffold). Screenshots and command results after Tervory deploys.
