# ZA2: the whole squad on the ZA server, in rand

> Written 20 Oct 2026, 13:00 PT. Founder: "I want the ZA Squad on its own in the server... It is all about confusion: Tiger scraping Rand pricing, getting confused at some point and it fucks the entire system." Today the ZA box runs only Tank, LiteLLM and Zenas (ZA1). Every other room and the Workspace live on Boston, so rand and dollar work share one squad.

**Goal:** two complete squads from the same code. Boston serves the US in USD. The ZA box serves South Africa in ZAR. The region is configuration (`TANK_REGION`), never a fork. No client data, price, catalogue or record is copied between boxes.

**Files you may change:**
- `docker-compose.za.yml`: add the workspace and a corridor network and database role for each room.
- new `agents/<room>/docker-compose.za.yml` for base, tiger, market_lab, rig, tisan and radix (zenas already has one).
- `db/` (ZA room roles, additive).
- `workspace/`: region config, sign-in routing, onboarding, squad links, review, admin homes.
- each room's region config and source lists. This is config only; the room logic does not change.
- `.github/scripts/deploy_changed.py`: deploy the ZA workspace too.
- `.env.example` (names only), `docs/cursor/ROOMS.md`, tests.

## 1. Rooms on the ZA box
- **Every room** gets `docker-compose.za.yml` in the same shape as `agents/zenas/docker-compose.za.yml`:
  - `TANK_REGION: za`, `TANK_URL: http://tank:8000` (tank-za);
  - its own corridor network;
  - its own login to the ZA database;
  - its own `TANK_KEY` on tank-za;
  - no model keys.
- **The ZA Tank** knows every ZA room key (`TANK_KEY_<ROOM>` on tank-za) and routes model calls through ZA LiteLLM, using the same providers as Boston.
- **Resource limits** match Boston. Add up every limit on the ZA box (rooms, workspace, Tank, LiteLLM, Postgres, Qdrant, Redis). The PR reports the total against the server's RAM and CPU, so the founder can upgrade the VPS first if needed.
- **No build workers** on the ZA box (unchanged rule).

## 2. Workspace at za.tervory.com
- With `TANK_REGION=za`, the workspace talks only to tank-za.
- **No calls between boxes in either direction.** Test this at the fetch layer.
- **Same Clerk login on both.** On sign-in, an account whose home is the other box goes to that box's address (`APP_URL_US`, `APP_URL_ZA`).
- **Home region is set automatically at onboarding** from the account's country: South Africa = za, everything else = us-east. The founder can still change it in Admin > Homes. No account is left without one.
- **Founders** (`TERVORY_ADMIN_USER_IDS`) have full access on both boxes:
  - every page;
  - every tenant on that box;
  - every review queue;
  - sign-off in any jurisdiction.
- **On each box, /review for a founder lists all of that box's tenants,** with the tenant name on each row.

## 3. One currency per box: the confusion fix
- **Region defaults** come from the region, not the code:
  - ZA: currency ZAR, locale en-ZA, time zone Africa/Johannesburg, country ZA.
  - Boston: USD, en-US, America/New_York, US.
- **Every money value carries its currency code.** A room refuses to compare, add or average values in different currencies. It returns an error rather than converting, and this is tested in Tiger, Rig and Market Lab.
- **No currency conversion anywhere in the rooms.** A price is stored as the page or catalogue shows it.
- **Source lists by region:**
  - **Tiger:** SA retailers on ZA, US retailers on Boston.
  - **Rig:** ZAR catalogues (Custom Nation) on ZA.
  - **Base:** ATF FFL on Boston only. On ZA, SA official lists only; leave the list empty with a "no SA official source yet" note if none is wired.
  - **Market Lab:** US feeds on Boston; SA public feeds (Stats SA, SARB) on ZA, or empty until wired.
  - **Tisan and Radix:** the same on both boxes.
- **Ledger:** model costs are billed by providers in USD, so they stay USD on both ledgers. The ZA billing page may also show ZAR at a stored daily rate, labelled as an estimate.

## 4. Skills, gold and training
- The skill code is the same on both boxes, and each box's Tank keeps its own skill states.
- A founder-only button on ZA Skala, "Copy approvals from Boston", copies skill ids, versions and states one way. It copies no data and no examples.
- ZA nightly gold intake reads only ZA rooms. Training exports keep going to `snapshots/za/`, public rows only (as #190).

## 5. Deploy
- `deploy_changed.py` already deploys `agent-<room>-za` copies by name. Add the ZA workspace.
- Claude creates the Coolify apps in the ZA project (`agent-base-za`, `agent-tiger-za`, `agent-market_lab-za`, `agent-rig-za`, `agent-tisan-za`, `agent-radix-za`, `workspace-za`).
- The founder sets every secret.

## 6. Existing SA data on Boston
Not part of this PR. The PR lists what on Boston is South African (for example the Custom Nation catalogue and SA Tiger watchlists), with counts. Moving it is a separate step the founder approves.

## Done when
CI green, and tested:
- each room starts with `TANK_REGION=za` against tank-za;
- the ZA workspace never calls a Boston URL, and Boston never calls ZA;
- an SA account gets home za at onboarding, and sign-in sends it to `APP_URL_ZA`;
- a founder sees all tenants on each box, and a reviewer only their own;
- mixed-currency comparisons are refused in Tiger, Rig and Market Lab;
- ZA defaults are ZAR, en-ZA and Africa/Johannesburg.

The PR reports the ZA resource total and the list of SA data on Boston. After merge, the founder adds DNS and secrets, and Claude creates and deploys the ZA apps and checks each one.
