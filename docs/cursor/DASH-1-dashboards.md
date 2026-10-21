# DASH-1: the founder control panel and the clean client dashboard

> Written 21 Oct 2026. **Build exactly to the approved Figma:** page "0 · Dashboards" in https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS
>
> Founder: one screen for himself with everything to press; a completely clean dashboard for clients, with no text dumps and no internal words.

**Files you may change:**
- `workspace/app/page.tsx` (client home);
- new `workspace/app/control/` (founder);
- `workspace/lib/tank.ts` (dashboard reads only);
- `tank/` (read-only dashboard routes; route registration in main.py);
- tests.

## Founder control panel (`/control`, founders only)
- **Top:** a health pill (from Ghost) and **Pause all paid work**. The pause flips a Tank switch that refuses paid calls and paid tools until it is turned back on.
- **Key numbers with sparklines:** sign-ups (Clerk), paying clients (Stripe), work done today and the share done by code (ledger), spent this month against the budget, saved this month (ledger baseline).
- **Case study, AmmoSync on Base:** verified records by state (bar), cost per verified record over time against Apollo (line), headline numbers, and the "Run next state" and "Export case study" buttons.
- **Needs you:** every pending action, each with its buttons: skill approvals ("Approve all ready" from SKALA-2), paid steps, proven cheaper models (Switch), the gold check (Start), Ghost issues (Look / Let it fix).
- **Squad:** each agent's status, what it is doing now, and Pause/Start, per region.
- **Latest sign-ups:** name, company, country and plan, with a link to all.
- **Controls:** shadow checks, overnight batches, paid tools without asking, squad builds Tervory, daily budget, server load, storage used.

## Client dashboard (the home page for clients)
- Greeting, one ask box ("What do you need today?") with "Add a file", three numbers (jobs done this month, you saved, credits left), "Waiting on you" with plain yes/no buttons, recent work with plain statuses, and "Your team" (agent logos with a two-word job).
- **Banned words on client screens:** Skala, Tank, ledger, receipt IDs, model names, eval, gold, shadow, retire, rung, tenant, region box. Details open in a drawer only when the client asks.

## Done when
CI green. Tests:
- a non-founder cannot load `/control`;
- the pause blocks a paid call;
- every number comes from its source with a test fixture;
- a client page contains none of the banned words.

Screenshots matching Figma at 1440px and 375px.
