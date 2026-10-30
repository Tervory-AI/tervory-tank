# Trigger by Tervory

Trigger drafts copy, articles and documents through Tank, then checks the output with free, self-hosted code. `trigger.check` never uses a model. The existing `/chats` action result shows the draft/text and checker summary; no new page is included.

## Operations handoff

Grok creates the Coolify resource **agent-trigger**, using `agents/trigger/docker-compose.yml` in Raw Compose mode. The main stack creates `tervory-gw-trigger`; only Tank and Postgres join it. The room joins that corridor and a separate internal checker network. LanguageTool joins only the checker network and exposes no public port. Deploy the main stack/agent role provisioning before the room. No deployment was performed by this build.

Settings by name only: `AGENT_DB_PASSWORD_TRIGGER`, `TANK_KEY_TRIGGER`, `POSTGRES_DB`, `TANK_REGION`. The shared role provisioner creates the `agent_trigger` role/schema. The room applies its idempotent table schema on startup. The key is passed as `TANK_KEY` inside this room; no provider keys are present. Health endpoints: room `/health`, checker `/v2/languages`. Both are internal.

Memory limits: **512 MiB** room plus **2 GiB** LanguageTool, with Java heap capped at **1536 MiB**. Reserve at least **3 GiB of additional available box memory**, beyond the existing stack, for these services and overhead. The small isolated grammar test used about 316 MiB initially; this is not a concurrency/load sizing measurement. Each service is capped at one CPU. No optional n-gram/neural model data or auto-download entrypoint is enabled. LanguageTool is English (en-US) in this build.

## Tenant voice and actions

No voice is seeded. In the existing chat, a founder or the active tenant's Clerk `org:admin` can use these code-only commands:

- `trigger.voice.set:` followed by pasted plain-text notes. Optional headings: `Brand:`, `Rules:`, `Preferred words:`, `Banned words:`, `Required words:`, `Tone:`, `On-voice:`, `Off-voice:`. Lists can be separate lines; word lists can use CSV quoting. Unlabelled text is retained as rules. No brand is guessed when absent.
- The existing card's **Brief** shows the parsed spec. **Confirm** saves it; Cancel saves nothing. A changed voice invalidates an older preview. Source text, the exact parsed spec and every revision are retained. Direct gateway mutations without an executing confirmed card are refused.
- `trigger.voice.show` returns the current file and version history. `trigger.voice.show: version 2` also reads that version. History is paginated in groups of 20; `trigger.voice.show: 20` reads the next page.
- `trigger.voice.rollback: 2` previews version 2's content as the next revision. Confirm restores it without deleting intervening versions.

The text supplied is the only content source. There is no model parser, inferred counterpart example, invented rule or dataset coffee example. Status/version are storage metadata. The parser does not serialize default checker settings as user-authored rules. New notes replace the current file in a new version; they do not silently merge old rules. Existing pre-second-build voices are copied into history when the additive schema applies; overwritten pre-history cannot be reconstructed.

The full canonical voice and revision participate in the tenant cache key. A tenant without a file uses [house style](HOUSE_STYLE.md); no house rule is added to a tenant's saved file. Raw spec updates through `trigger.write.voice` and the former room PUT route are retired so new chat saves use the preview/Confirm/version flow. Plain-text source is capped at 12,000 UTF-8 bytes, and the existing Command 32,000-byte action envelope still applies.

The founder can ask for a description in their saved voice through the existing planner and confirm `trigger.write`. Drafting uses task `trigger.write` through the chassis Tank client and `/v1/route`; the new policy enables tenant cache and the existing ladder. It reuses the existing `luna` route and adds no paid provider. The checkers run on every returned draft, including a cached draft.

For a completely model-free check from the window, use **`Trigger, check: <pasted paragraph>`** or **`Trigger, check this paragraph: <pasted paragraph>`**. Command recognizes these prefixes in code, proposes the existing confirmation card, and dispatches `trigger.check`. Other conversational phrasing still uses the existing planner. The actual check action always uses code only. Its real ledger record has zero tokens/cost; Tank's existing receipt pricing trigger owns the comparison.

Writing/checking retain the first build's founder-only access; no new squad grant was created. Voice tools and feedback additionally allow the tenant's verified admin, only within their active tenant. The Workspace derives that role from the existing Clerk session and checks the user, organization and mapped tenant together; no browser-supplied role or squad grants access.

## Learning records

Every successful `trigger.write` tool result is saved through Tank's existing `training.save_pair`, with the brief, draft and checker report. New pairs are private, tenant-scoped, client-matter records and inactive/unapproved while feedback is pending. Nothing is exported to a shared dataset.

Use `trigger, accept`, `trigger, reject: <reason>` or `trigger, changes: <requested changes>` in the same thread. Code selects that thread's latest completed Trigger draft. The existing card previews the status and exact change text; Confirm records it. `trigger.feedback` also accepts an explicit write ID as an argument. Only accepted pairs become active; rejected/change-requested records stay inactive. All feedback events are retained, including the user and exact requested changes. Recording feedback does not itself generate a new draft. Normal free-form follow-ups may use the existing conversation planner; these explicit prefixes and the voice/check tools do not call a model.

Legal-document requests return a handoff to the existing same-box Zenas drafting endpoint. The existing Zenas template, jurisdiction, tenant/home checks and civil/criminal scope gates remain authoritative. Provide `template` and `jurisdiction`; missing values fail visibly. The original Zenas result and its existing notice are returned. Trigger does not write legal text or run a second legal engine.

## Checker coverage and bounds

See [ATTRIBUTION.md](ATTRIBUTION.md) and [source pins](sources/pins.json). Proselint and deterministic upstream agent-style detectors run locally. Readability includes sentence length and advisory passive-voice candidates. Selected stylebooks supply drafting guidance and mechanical phrase/link candidates where applicable; their semantic advice is not scored. Practical Prose contributes only an E1/E3/F3 code checklist. Its scorer is absent.

LanguageTool failure/incomplete results are explicit (`complete: false`, `checker_errors`); there is no paid or remote fallback. Inputs/drafts are capped at 20,000 characters. Reports retain the total issue count and return the first 200 findings, explicitly marked when truncated. Long text can be checked in smaller sections. No semantic accuracy/voice-fit grade is invented. The full skipped-rule list and proof are in [the PR handoff](../../tests/trigger_first_build/PR.md).
