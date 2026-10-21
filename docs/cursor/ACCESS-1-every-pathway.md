# ACCESS-1: every pathway to the data, without disguise

> Written 21 Oct 2026. Founder: "Base is not to be blocked from any site, it is to be given the tools to be a human." "Every other site is fair game. We need solutions for all and every pathway." Runs after AGENT-1 (#216) merges, for Base and Tiger.

**Standing limits (founder, 21 Oct):**
- Any public website, with no allowlist.
- Private and internal network addresses stay blocked (the public-IP DNS check). That is not a site block.
- Never solve or bypass a captcha or bot check, never fake identity, never rotate proxies to dodge blocks.
- A simple age confirmation may be clicked through, like a person would. Nothing more: no forms, no accounts.

**Files you may change:**
- `agents/tiger/`, `agents/base/`, `agents/_brain/` (browser and access only);
- new `tank/access.py` and new `tank/vault.py`;
- `tank/main.py` (route registration only);
- `tank/schema.sql` (additive);
- new `workspace/app/access/` (founder and client pages for connections);
- `workspace/lib/tank.ts` (access calls only);
- `.env.example` (names only);
- tests.

## 1. Official feeds first
- Many distributors give dealers a price and inventory feed: an FTP file, EDI, or a dealer API. Build a feed adapter per distributor (start with the ones in the Build Pack: Zanders, Sports South, RSR, Jerry's).
- Tiger reads feeds through Tank: no browser, no login.
- Each feed records its source, the time it was fetched and a row count on a receipt.
- A feed always outranks scraping the same data.

## 2. Logins, where no feed exists
- **A dedicated read-only user per distributor per client**, created by the account owner. Never the owner's own login. Revoking means the owner disables that user; nothing else changes.
- **The vault (`tank/vault.py`):**
  - Credentials are entered on `workspace/app/access/` by the founder or the client, server-side only. They never pass through chat, the window, a model, a log or a URL.
  - They are encrypted at rest. The key name is `TANK_VAULT_KEY` in Coolify; the value is never in code.
  - They are scoped to one tenant, one room and one site.
  - They are released only to the owning room's own browser container, at login time, over its own corridor.
  - The model only ever sees "logged in" or "login failed".
- **Sessions:** the browser keeps the session cookie on its own volume. It logs in again only when the session ends.
- **Every login, logout and failure is on a receipt:** who, which site, when.
- **Revoke and rotate:**
  - a **Revoke now** button deletes the stored credential and the session at once;
  - a rotation reminder on the schedule the founder sets per site;
  - a credential older than its schedule is refused until it is updated.
- **Authenticator codes:** only when the account owner deliberately enrolls Tervory as a device. The secret is stored in the vault like a password.
- **Terms:** each site has a founder-set flag, "automated login allowed under this site's terms" (yes / no / unknown). Only "yes" logs in.
- **The data belongs to that client.** Prices fetched with a client's login stay in that client's account. The skill (how to read the portal) may be shared through Skala; the data never reaches another client or shared training.

## 3. "Needs a person" queue
- A captcha, a bot check, a login that needs a human, or a terms flag of "unknown" puts the page in a queue, shown in the window and on `/control`.
- A person on our side opens it in the room's own browser (a live view), does the check themselves, and hands back. The room carries on from there in the same session.
- A receipt records who handled it and how long it took.

## 4. Social pages
- **Meta (Facebook and Instagram):** an adapter for Meta's official API for public business pages, behind a `META_APP_ID` setting (name only). Until the app review is approved it stays off, and Base uses what search results show.
- No logged-in scraping of social sites.

## 5. Sites that are down or gone
- Retry with backoff.
- Then archived copies (the Wayback Machine, Common Crawl), marked as "archived, dated".
- Then the paid data rung through Tank, as the ladder already does.

## Done when
CI green. Tests:
- a feed outranks a scrape of the same data;
- credentials never appear in a log, URL, model message, receipt or test output;
- only the owning room's browser can fetch a credential, and only for its tenant and site;
- Revoke now removes the credential and the session;
- an overdue credential is refused;
- a site flagged "no" or "unknown" never logs in, and goes to the queue;
- a captcha goes to the queue and is never solved by code;
- an age confirmation is clicked and nothing else is;
- one client's portal prices never appear for another client.

Screenshots of the access pages at 375px and 1440px.
