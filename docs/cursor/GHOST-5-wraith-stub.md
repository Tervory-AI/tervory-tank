# GHOST-5: Autumbra Enforce stub (flag OFF)

> Written 24 Oct 2026. Dogfood slice. **Not Dual-LLM / NeMo / vLLM. Not live enforcement.**
>
> Product: **Autumbra Enforce** (dry stub). Internal module remains `agents/ghost/wraith.py` and flag `GHOST_WRAITH_ENABLED` until a dedicated rename PR.

## What this is
A minimal stub so the Autumbra Watch → Autumbra Enforce air-gap shape exists in code:

1. Autumbra Watch (or triage) emits a `ThreatPayload`.
2. Payload validates (`accept_threat_payload`) or **burns**.
3. If `GHOST_WRAITH_ENABLED=1` (or `WRAITH_ENABLED=1`), `POST /ghost/wraith/enforce` returns a **would_enforce** dry JSON.
4. Default is **OFF** → route answers 404. No Cloudflare calls. No auto-patch. No host edits.

## What this is not
- Not a second model room / GPU bunker (keep using Tank).
- Not auto-execute without founder tap.
- Not a rename of Shields Up. Live edge changes still go Autumbra Watch propose → founder **Shield** → apply/health/undo.

## Enable (dogfood only, founder says go)
```
GHOST_WRAITH_ENABLED=1
```
Leave unset / `0` in Coolify until Zenas asks for it.

## Code
- `agents/ghost/wraith.py` — `enabled()`, `would_enforce()`
- Route wired in `agents/ghost/app.py`
