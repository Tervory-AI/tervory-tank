# Autumbra connect · M17

Status: **Proposed — not approved** for every frame and all new wording. Design only; these screens do not establish implemented token storage, permission validation, alert delivery or disconnect behavior.

Figma file: [Workspace](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS), page `513:34988`. Branch `codex/figma-autumbra-connect`, from `origin/main` at `8857cd3e`.

Uses the existing white shared menu (main `180:8387`, mobile variant via source `231:12014`), CRM Action `93:4`, CRM field `93:6`, and MCP card pattern `231:11997`. Shared components are unchanged; local instance product heading is Autumbra and typography is Inter. Existing menu items are preserved: no Autumbra-specific menu items are invented.

Light canvas/white panels; navy primary controls and white/navy secondary controls. Existing surface/text/spacing/radius/input-border variables remain bound. Only the approved logo image is raster; all content is editable text, instances and auto-layout frames.

## Cloudflare

Permissions appear before Save and connect: one specific zone, Zone Read and WAF Edit, excluding DNS/account-wide/other-zone/global-key access. Names come from `docs/ops/AUTUMBRA-CLOUDFLARE-LIVE.md:22`; the end-user flow and vault guarantees are **Proposed**, per this brief. No token is present; dots represent a masked field, not a real value.

| State | Width | Frame ID | Status | Screenshot |
| --- | --- | --- | --- | --- |
| Connect | 1440 | [513:34989](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=513-34989) | Proposed | [PNG](screenshots/cloudflare-connect-1440.png) |
| Connect | 375 | [513:35164](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=513-35164) | Proposed | [PNG](screenshots/cloudflare-connect-375.png) |
| Empty | 1440 | [513:35340](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=513-35340) | Proposed | [PNG](screenshots/cloudflare-empty-1440.png) |
| Empty | 375 | [513:35481](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=513-35481) | Proposed | [PNG](screenshots/cloudflare-empty-375.png) |
| Loading | 1440 | [513:35623](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=513-35623) | Proposed | [PNG](screenshots/cloudflare-loading-1440.png) |
| Loading | 375 | [513:35764](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=513-35764) | Proposed | [PNG](screenshots/cloudflare-loading-375.png) |
| Error | 1440 | [513:35906](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=513-35906) | Proposed | [PNG](screenshots/cloudflare-error-1440.png) |
| Error | 375 | [513:36049](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=513-36049) | Proposed | [PNG](screenshots/cloudflare-error-375.png) |
| Connected | 1440 | [513:36193](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=513-36193) | Proposed | [PNG](screenshots/cloudflare-connected-1440.png) |
| Connected | 375 | [513:36336](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=513-36336) | Proposed | [PNG](screenshots/cloudflare-connected-375.png) |
| Disconnect | 1440 | [513:36480](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=513-36480) | Proposed | [PNG](screenshots/cloudflare-disconnect-1440.png) |
| Disconnect | 375 | [513:36623](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=513-36623) | Proposed | [PNG](screenshots/cloudflare-disconnect-375.png) |
| Disconnected | 1440 | [513:36767](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=513-36767) | Proposed | [PNG](screenshots/cloudflare-disconnected-1440.png) |
| Disconnected | 375 | [513:36908](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=513-36908) | Proposed | [PNG](screenshots/cloudflare-disconnected-375.png) |

## Wording register

Every content string and text-node ID is recorded in [cloudflare.json](cloudflare.json). All connection/vault/error/disconnect sentences in that inventory are **Proposed**. The card explicitly says “Proposed wording”; each frame says “Proposed · Not approved”. Node names also identify proposed wording. Provider names are existing product terms. Shared menu wording, “Connected”, “Disconnect”, “Cancel”, “Add connection”, “Try again” and “Sign in with the provider” reuse existing MCP/UI wording. “Optional. You choose what to connect.” comes from `agents/ghost/client_settings.py:195`. New labels including “Connections”, “Website”, “Scoped API token”, “Permissions before saving”, “Save and connect”, “No connections yet.” and their surrounding sentences are Proposed.

## Validation and approval gaps

Every screen has 1440/375 versions and empty, loading, error, connected, disconnect confirmation and disconnected states. Font/bounds checks passed for Cloudflare. Screenshot review corrected the primary action paint and input height. New vault/save/removal claims require implementation verification and founder wording approval; no credential or client session was used. Google Workspace frames follow in the next screen push.
