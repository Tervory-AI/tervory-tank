# Product hosts vs Figma (inventory)

Written 2026-10-25. Source of truth:

- Product window / dashboards: https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS
  - page `0 · Dashboards` — founder control `10:115`, client dashboard `12:2`
  - page `2 · Client screens` — **C5 · Agent page (Base)** `7:221` is the agent-host Main chrome
  - page `3 · Founder screens` — F1–F5 (Proof, Squad, Agent box, Skala, Gold)
- Marketing landing: https://www.figma.com/design/ksi7ctRwEnN8wbip1yfuhL
- Rig widget: Figma `uRpPy3Hns0WxWZYTPwZ2ni` (separate file; RIG-PHASE-1)

User-facing product name is **Autumbra** (Watch / Enforce). Code and public copy stay Autumbra even if an older Figma squad row still uses a retired label.

## Live hosts (US) vs Figma

| Host | Live before this PR | Figma target | Status after this PR | Still needs Figma build-out |
| --- | --- | --- | --- | --- |
| base.tervory.com `/base` | Invented typed-brief shell (fake shop brief) | C5 agent page Main | C5 chrome scaffold; Jobs empty until live | Full C5 pixels + wire Ask/Upload to Base; match screenshots |
| tiger.tervory.com `/tiger` | Invented watches/alerts rows | C5 agent page Main (Tiger labels) | C5 chrome scaffold; empty Jobs | Same + Tiger watch columns from private `view.tsx` data |
| tisan.tervory.com `/tisan` | Invented chat threads | C5 agent page Main (Tisan) | C5 chrome scaffold; empty Jobs | Same + briefs/chats live |
| market-lab.tervory.com `/market-lab` | Invented readings/% | C5 agent page Main (Market Lab) | C5 chrome scaffold; empty Jobs | Same + feed readings live |
| radix.tervory.com `/radix` | Invented findings | C5 agent page Main (Radix) | C5 chrome scaffold; empty Jobs | Same + scan jobs live |
| skala.tervory.com `/skala` | Invented skill scores | C5 agent page Main + founder F4 Skala | C5 chrome scaffold; empty Jobs | Founder F4 screen; client host stays clean |
| tank.tervory.com `/tank` | Invented roster/queue | C5 agent page Main (Tank) | C5 chrome scaffold; empty Jobs | Founder squad/queue screens; no invented calls |
| protect / autumbra `/autumbra` | Autumbra public Watch page (fixture receipts labeled Autumbra) | Not C5; Autumbra product page | **Unchanged** (already Autumbra naming) | Replace fixture receipts with live Watch when dogfood armed |
| rig.tervory.com `/` | Lab + seeded catalogue paths | Rig Figma `uRpPy3Hns0WxWZYTPwZ2ni` 01–05 | Seed search no longer paints invented parts before live hits; scrubbed banned word from copy | Full Rig frames 01–05 / 3D; live catalogue only |
| app.tervory.com `/` + `/control` | Workspace shell | Dashboards `12:2` client + `10:115` founder | Not in this PR | DASH-1 full build |
| zenas.tervory.com | Moot / panel | Client screens + Zenas briefs | Not in this PR | Zenas US e2e + Figma match |

## What this PR does

1. Shared Main chrome CSS `workspace/app/product-public.css` aligned to C5 (Ask row, Jobs table, learned strip, foot).
2. Public product pages for Base, Tiger, Tisan, Market Lab, Radix, Skala, Tank use that chrome with **empty Jobs** (honest) instead of invented SKUs/%/findings.
3. Rig: no pre-seeded catalogue parts/thread; live search only; copy scrub.

## What this PR does not do

- Pixel-perfect Figma C5 (tokens, exact type, screenshot parity).
- Wire Ask / Upload buttons to Tank (scaffold only).
- Enable Autumbra Enforce or new paid APIs.
- Build DASH-1 `/control` or marketing landing.
- Rename retired Figma squad labels to Autumbra.

## Prove-it (founder)

After merge + Coolify workspace redeploy:

```bash
for u in base tiger tisan market-lab radix skala tank; do
  echo "== $u"
  curl -sS "https://$u.tervory.com/$u" | rg -n "pp-title|pp-ask|pp-empty|Hornady|Kauai|Critical Defense|Weekly shelf|base\\.intake|extract-zip" || true
done
```

Expect: `pp-title` / `pp-ask` / `pp-empty` present; invented SKU/shop/finding strings absent.

Rig: open `/`, confirm search line asks for a brand/model and does not show a pre-filled Staccato parts list before a live answer.

Autumbra: page copy shows Autumbra / Watch / Enforce only (ThreatPayload schema ids are protocol names, not product UI).
