# Tisan

Tisan is the developer and the designer. It builds and checks the work a tenant has asked for.

## Room

Own Coolify resource. Base directory `/agents/tisan`. Compose location `/docker-compose.yml`. No public domain. Predefined network: isolated network only.

Standard room, same pattern as the template. The only corridor is `tervory-gw-tisan`. Tisan can reach Tank, Postgres, and Hermes. Nothing else joins that corridor.

Login `agent_tisan`. Schema `agent_tisan`. Key `TANK_KEY_TISAN` on Tank and on Hermes.

The image installs Node and fills an npm cache while it builds. A scaffold run uses that cache with `npm ci --offline`, so the check does not need the internet.

The room has 1g of memory and 0.25 CPU. A scaffold job is allowed 10 minutes. Other jobs, and other agents, stay on the chassis default of 2 minutes.

## Project scaffold

Skill `tisan.scaffold` (job kind `scaffold`). Input:

```json
{
  "name": "Northwind",
  "slug": "northwind",
  "pages": ["home", "about", "contact", "privacy"],
  "locale": "en",
  "brand": {
    "colours": {"ink": "#001840", "paper": "#F4F6FB", "accent": "#E80008", "line": "#B8BFD0"},
    "fonts": {"heading": "Jost", "body": "Inter"},
    "logo_url": "https://cdn.example/logo.svg"
  }
}
```

The tenant is the job's `tenant_id`. Brand colours and fonts become CSS variables and Tailwind tokens. Pages use those tokens. The contact form posts to `/api/contact`, which accepts the message and does not store it. There is no analytics and no third-party script.

Before it returns, the room runs `npm ci`, `npm run lint`, `npm run build`, and `npm test`. The project is stored at `/data/builds/<tenant>/<slug>/<n>.tar.gz` with a manifest: `files`, `token_set`, and `checks`.

## Later skills

1. The Figma token reader (the style contract).
2. The Playwright test runner.

## What Tisan never does

- Deploy anything to production without a Radix scan result of "no critical findings".
- Hold model keys. Every model call goes through Tank.
- Push to a client's repo without that tenant's approval recorded.
