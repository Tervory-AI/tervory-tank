# ZA1 — The South Africa box (second region, same code)

> Written 14 Oct 2026, 17:50 PT. Part of the Zenas plan (`docs/cursor/Z-zenas-plan.md`, "Two regions"). Read that section first.

**Goal:** a second, complete Tervory region on the founder's South African server, so South African clients and South African law live only in South Africa. Same code as Boston; the region is configuration (`TANK_REGION=za`), never a fork. Nothing replicates between regions.

**Files you may change:** `docker-compose.za.yml` (new), `litellm/config.za.yaml` (new), `tank/main.py` (region checks only), `agents/zenas/pool/catalogue.py` (add `za` sources only), `.env.example` (names only), `docs/cursor/ROOMS.md` (a short "Regions" section), new tests under `tests/`.

## 1. The ZA stack (`docker-compose.za.yml`)
- Only what Zenas needs: `postgres`, `redis`, `qdrant`, `hermes`, `litellm`, `tank`, `agent-roles`, `agent-zenas`. No Base, Tiger, Market Lab, RIG or Workspace in this region yet.
- Same images and build contexts as the main compose; every service gets `TANK_REGION=za`. Own volumes; own corridor `tervory-gw-zenas` (compose-managed). Same room rules as ROOMS.md.
- Public endpoint: Tank only, at `za-api.tervory.com` (Claude sets the domain in Coolify). Everything else internal.

## 2. Models from South Africa (`litellm/config.za.yaml`, Tank region checks)
- Tank in `za` keeps a per-tenant provider allow-list. A prompt that still contains a detected personal identifier (`zenas.pii`) is **refused** for any provider not running in South Africa. Today no SA-hosted model is configured, so in `za` every prompt to a model must be placeholder-masked first; pure-code steps are unaffected.
- `config.za.yaml` starts with the same funded roster (no China-hosted providers) and a commented slot for an SA-hosted model (`za-local`), to be filled after the research in `docs/cursor/prompts/RESEARCH-ZENAS.md`.
- A `za` Tank refuses tenants whose home region is `us-east`, and the US Tank already refuses `za` tenants (Z1). Test both.

## 3. South African law sources (`catalogue.py`, region `za`)
Add catalogue entries (terms checked and recorded, as the US ones are) for the Z3 first wave, with fixtures only in this task; live loading is Z3b:
- Legislation: Companies Act 71 of 2008, Consumer Protection Act 68 of 2008, POPIA (Act 4 of 2013), Customs and Excise Act 91 of 1964, International Trade Administration Act 71 of 2002, ECTA (Act 25 of 2002), LRA and BCEA, Trade Marks Act 194 of 1993; Conventional Arms Control Act and Firearms Control Act as regulatory compliance only.
- Case law: SAFLII (SCA, Constitutional Court, High Court commercial).
- Court rules: Uniform Rules of Court, Magistrates' Courts Rules.
- Record for each: licence and terms URL, as information only. Data use is the founder's decision; do not block a source on your own reading of its terms. Keyed sources (e.g. Laws.Africa) read their key from the environment by name and are skipped cleanly until it is set.

## Done when
CI green; `docker compose -f docker-compose.za.yml config` is valid; a `za` Tank refuses a prompt with an SA ID number for a non-SA provider (tested); a `us-east` tenant is refused by the `za` Tank (tested); `za` catalogue entries load from fixtures and appear in pool status.

## Founder steps (after merge; Claude can guide)
1. Tell Claude the SA server's IP and its size (RAM, disk).
2. Coolify → **Servers** → **Add** the SA server (Claude gives the one command that lets Coolify reach it).
3. Same firewall as Boston on the SA server: only 22, 80, 443.
4. Cloudflare DNS: `za-api` → the SA server IP.
5. Claude creates the ZA app in Coolify from `docker-compose.za.yml` and runs room setup for `zenas` there.
