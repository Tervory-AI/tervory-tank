# Uptime Kuma (Boston)

Self-hosted [Uptime Kuma](https://github.com/louislam/uptime-kuma) on the Boston Coolify host. Free. One-click Coolify service `louislam/uptime-kuma:2`.

## Coolify

| Field | Value |
| --- | --- |
| Tank / server | Boston (`xnmc0jkz8j9i5jh1jwanbsfv` context; Coolify server `h5fcg6mlspwtfaw3wf3expbm`) |
| Service uuid | `m24wvavrazt3s6lovfwu2ffp` |
| Application uuid | `tnzohaq0qahwzhsieotjdmqh` |
| Project | Tervory AI (`dguxczrbmbqvezo3qib0twge`) / production (`0zjmt7swwqqevcjq21121oq8`) |
| Image | `louislam/uptime-kuma:2` |
| Data | Docker volume `m24wvavrazt3s6lovfwu2ffp_uptime-kuma-data` → `/app/data` |
| Compose dir | `/data/coolify/services/m24wvavrazt3s6lovfwu2ffp/` |

**Internal only.** Traefik is disabled (`traefik.enable=false`). There is no public FQDN. Coolify `SERVICE_URL_*` / `SERVICE_FQDN_*` placeholders were removed so a redeploy does not recreate an sslip.io host.

### Reach the UI (founder)

Until `KUMA_PUBLIC_FQDN` is set behind sign-in (Cloudflare Access, Coolify auth, or similar), open an SSH tunnel to Boston and browse localhost:

```bash
ssh -i <boston-key> -L 13001:127.0.0.1:13001 root@2.25.250.28 \
  'docker run --rm -p 127.0.0.1:13001:3001 --network m24wvavrazt3s6lovfwu2ffp \
   alpine/socat TCP-LISTEN:3001,fork TCP:uptime-kuma-m24wvavrazt3s6lovfwu2ffp:3001'
```

Then open `http://127.0.0.1:13001`, complete first-run admin setup using the values you put in Coolify for `KUMA_ADMIN_USERNAME` / `KUMA_ADMIN_PASSWORD` (names only in Coolify until you fill them). Do not leave the setup wizard on a public URL.

When you want a durable URL, set Coolify domain from `KUMA_PUBLIC_FQDN` (name only until filled) and put it behind sign-in. Do not publish an unauthenticated sslip.io host.

## Monitors (HTTP, every 60s)

Add these in the Kuma UI after admin setup. Accepted status `200–299`. Interval **60** seconds.

| Name | URL | Live at deploy |
| --- | --- | --- |
| app | `https://app.tervory.com/api/health` | yes |
| base | `https://base.tervory.com/api/health` | yes |
| tiger | `https://tiger.tervory.com/api/health` | yes |
| market-lab | `https://market-lab.tervory.com/api/health` | yes |
| rig | `https://rig.tervory.com/health` | yes |
| zenas | `https://zenas.tervory.com/api/health` | yes |
| protect | `https://protect.tervory.com/api/health` | yes |
| chat.ammosync.com | `https://chat.ammosync.com/` | yes |
| za | `https://za.tervory.com/api/health` | **no** — add only once live (was HTTP 404) |

## Email alerts (SMTP)

Kuma notification type **Email (SMTP)**. Create / fill these Coolify setting **names** on service `m24wvavrazt3s6lovfwu2ffp` (values are founder-only; never commit them):

| Coolify name | Use in Kuma |
| --- | --- |
| `SMTP_HOST` or `KUMA_SMTP_HOST` | SMTP host (same mail path Rig already uses) |
| `SMTP_PORT` or `KUMA_SMTP_PORT` | Port |
| `SMTP_USER` or `KUMA_SMTP_USER` | Username |
| `SMTP_PASSWORD` or `KUMA_SMTP_PASSWORD` | Password |
| `SMTP_FROM` or `KUMA_SMTP_FROM` | From address |
| `KUMA_SMTP_TO` | Founder inbox (To) |

Also: `KUMA_ADMIN_USERNAME`, `KUMA_ADMIN_PASSWORD`, `KUMA_PUBLIC_FQDN`.

Wire the SMTP notification as default for every monitor. Resend on down; recover on up.

## GitHub watchdog stays

Keep `.github/workflows/watchdog.yml`, `.github/scripts/watchdog.py`, and `docs/ops/watchdog.md` until Uptime Kuma has run clean for **one week**. Do not remove the GitHub Action when this note lands. After a clean week, the founder may retire the Action in a separate change.

## Proof

Deploy proof for this cut: `/workspace/boston-uptime-kuma-proof/` on the agent box (not in git).
