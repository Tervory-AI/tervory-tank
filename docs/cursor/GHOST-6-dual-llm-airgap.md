# GHOST-6: Dual-LLM air gap (NeMo-front tank-only)

> Written 24 Oct 2026. Dogfood slice. **Not full NVIDIA NeMo. Not GPU/vLLM bunker. Not live enforce. Not auto-merge.**

## Architecture (brief → code)

```
untrusted logs / triage JSON
        │
        ▼
  NeMo-shaped front door     ← agents/ghost/guardrails.py (this PR; Tank-only)
  (injection markers burn)
        │
        ▼
  Ghost (Watch)              ← propose-only; no Cloudflare apply / no weapons
        │
        ▼
  Pydantic ThreatPayload     ← agents/ghost/threat_payload.py (GHOST-3 / #281)
  (schema burn; fixed detail)
        │
        ▼
  Wraith (Enforce)           ← stub behind GHOST_WRAITH_ENABLED (default OFF; #284)
  never reads raw logs
```

Ghost may touch dirty text. Wraith must not. Nothing crosses the air gap except a
validated `ThreatPayload`. Founder Shield tap remains the only path that can
change the edge.

## What this PR adds

1. `agents/ghost/guardrails.py` — `guard_inbound(text) -> str` or `GuardBurned`
   with fixed `GUARD_BURN_DETAIL`. Markers imported from `INJECTION_MARKERS` in
   `threat_payload.py` (one list; no silent diverge).
2. Wire on `POST /ghost/triage/accept` — raw body runs through the guard **before**
   `accept_threat_payload`.
3. Docs + tests proving injection burns (422, fixed detail, body not echoed),
   clean propose still proposes only, Wraith still OFF by default.

## Tank-only until GPU

No `nemoguardrails`, no vLLM, no second model room. Inference stays on Tank.
Optional hook comment in `guardrails.py` for a future GPU bunker swap.

## No weapons on Watch

Ghost remains propose-only. This PR does **not** give Ghost Cloudflare apply or
auto-enforce. Wraith stays flag-off + founder tap. Enforce is not enabled by
default.

## Out of scope

- Full NVIDIA NeMo Guardrails install / `rails.co` config
- vLLM / Dual-LLM GPU bunker
- Live Wraith enforce / edge apply without founder tap
- Auto-merge (AMMOSYNC / Zenas)
- Collectors / Wazuh / Vector ingest paths
