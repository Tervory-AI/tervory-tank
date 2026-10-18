# TS-2 — Tisan reads a Figma page

**Goal:** Tisan reads one page from the Tervory Figma and produces named tokens, a Tailwind theme, and a component manifest. Conflicting values and missing states are listed. They are not guessed.

**Files you may change:** `agents/tisan/` (reader, fixture, app, Dockerfile, README, the room compose env name), `tank/skills/tisan.figma/1.0.0/`, `tests/test_tisan_figma.py`, `.env.example`, this brief. Not the main `docker-compose.yml`. Not `tank/main.py`.

- **File:** `ksi7ctRwEnN8wbip1yfuhL`, page `0:1` "Landing — Desktop & Mobile". Frames `2:11` (desktop) and `6:45` (mobile).
- **Fixture only.** A live read of `api.figma.com` needs a route to the public internet. This room does not get one: no egress, no allow-list, no proxy. The reader opens `agents/tisan/fixtures/tervory-landing.json`, captured from the Figma connection on 17 Oct 2026. Collection names were not in that response.
- **`FIGMA_TOKEN`** is a name in `.env.example` only. The room does not receive it. Never commit a value.
- **Output:** CSS custom properties, a Tailwind config that references them, and a manifest mapping each Figma component to `components/ui/<Name>.tsx`.
- **Do not invent:** a second value for one token, a missing state, a font family, a spacing scale, or a collection name.

**Done when:** tests cover the fixture, a conflicting value, a missing state, and a refused call when the token is absent for any other file. PR open. Not merged. Not deployed.
