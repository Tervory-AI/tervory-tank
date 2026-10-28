# Trigger by Tervory

Trigger drafts copy, articles and documents through Tank, then checks the output with free, self-hosted code. `trigger.check` never uses a model. The existing `/chats` action result shows the draft/text and checker summary; no new page is included.

## Operations handoff

Grok creates the Coolify resource **agent-trigger**, using `agents/trigger/docker-compose.yml` in Raw Compose mode. The main stack creates `tervory-gw-trigger`; only Tank and Postgres join it. The room joins that corridor and a separate internal checker network. LanguageTool joins only the checker network and exposes no public port. Deploy the main stack/agent role provisioning before the room. No deployment was performed by this build.

Settings by name only: `AGENT_DB_PASSWORD_TRIGGER`, `TANK_KEY_TRIGGER`, `POSTGRES_DB`, `TANK_REGION`. The shared role provisioner creates the `agent_trigger` role/schema. The room applies its idempotent table schema on startup. The key is passed as `TANK_KEY` inside this room; no provider keys are present. Health endpoints: room `/health`, checker `/v2/languages`. Both are internal.

Memory limits: **512 MiB** room plus **2 GiB** LanguageTool, with Java heap capped at **1536 MiB**. Reserve at least **3 GiB of additional available box memory**, beyond the existing stack, for these services and overhead. The small isolated grammar test used about 316 MiB initially; this is not a concurrency/load sizing measurement. Each service is capped at one CPU. No optional n-gram/neural model data or auto-download entrypoint is enabled. LanguageTool is English (en-US) in this build.

## Tenant voice and actions

No voice is seeded. A founder may supply their own Brand Voice Spec JSON as `voice` in a confirmed `trigger.write` action. The object requires their `brand`, `status: live`, and a positive increasing `revision`. Subsequent writes omit `voice` and reuse the saved file. The complete canonical voice (including revision) is included in the Tank prompt and therefore in its tenant cache key. An internal authenticated `PUT /voice/{tenant_id}` also accepts the file. No browser calls the room directly.

Use the dataset's **format only**; do not copy its fictional coffee brand. `bannedTerms` and explicit `requiredTerms` are case-insensitive whole words/phrases; `preferredTerms` are writing guidance, not mandatory occurrences. `maxSentenceWords` defaults to 30 and can be 5–100. Optional `stylebook` selects one of the original 11 vendored books. Voice JSON is capped at 40,000 characters; the existing Command action envelope also has its stricter 32,000-byte limit. Stale voice revisions are rejected.

The founder can ask for a description in their saved voice through the existing planner and confirm `trigger.write`. Drafting uses task `trigger.write` through the chassis Tank client and `/v1/route`; the new policy enables tenant cache and the existing ladder. It reuses the existing `luna` route and adds no paid provider. The checkers run on every returned draft, including a cached draft.

For a completely model-free check from the window, use **`Trigger, check: <pasted paragraph>`** or **`Trigger, check this paragraph: <pasted paragraph>`**. Command recognizes these prefixes in code, proposes the existing confirmation card, and dispatches `trigger.check`. Other conversational phrasing still uses the existing planner. The actual check action always uses code only. Its real ledger record has zero tokens/cost; Tank's existing receipt pricing trigger owns the comparison.

This first build is founder-only. Trigger has no new client entitlement: the existing database squad whitelist is unchanged. No browser-supplied squad can grant access.

Legal-document requests return a handoff to the existing same-box Zenas drafting endpoint. The existing Zenas template, jurisdiction, tenant/home checks and civil/criminal scope gates remain authoritative. Provide `template` and `jurisdiction`; missing values fail visibly. The original Zenas result and its existing notice are returned. Trigger does not write legal text or run a second legal engine.

## Checker coverage and bounds

See [ATTRIBUTION.md](ATTRIBUTION.md) and [source pins](sources/pins.json). Proselint and deterministic upstream agent-style detectors run locally. Readability includes sentence length and advisory passive-voice candidates. Selected stylebooks supply drafting guidance and mechanical phrase/link candidates where applicable; their semantic advice is not scored. Practical Prose contributes only an E1/E3/F3 code checklist. Its scorer is absent.

LanguageTool failure/incomplete results are explicit (`complete: false`, `checker_errors`); there is no paid or remote fallback. Inputs/drafts are capped at 20,000 characters. Reports retain the total issue count and return the first 200 findings, explicitly marked when truncated. Long text can be checked in smaller sections. No semantic accuracy/voice-fit grade is invented. The full skipped-rule list and proof are in [the PR handoff](../../tests/trigger_first_build/PR.md).
