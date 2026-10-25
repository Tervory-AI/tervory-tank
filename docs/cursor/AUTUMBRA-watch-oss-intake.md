# Autumbra Watch — OSS intake adapters (Vector / Fluent Bit / Steampipe / OpenCTI)

**Status:** Draft adapters + presets in `tervory-tank` (not live in product).  
**Product naming:** Autumbra **Watch** / **Enforce** only. Never ship Ghost/Wraith in user-facing copy.  
**Code path:** `agents/ghost/watch_oss/` (short-term room name unchanged).  
**Flag:** `WATCH_OSS_ENABLED` / `GHOST_WATCH_OSS_ENABLED` (default **OFF**).

This is the **Watch customise** PR called for in [`AUTUMBRA-OSS.md`](./AUTUMBRA-OSS.md) (#289 shopping list). Docs-only staging stays on #289; this PR adds thin Tank adapters.

## Vault (primary vs cache)

| Location | Role |
|----------|------|
| Boston `ammosync@2.25.250.28:/home/ammosync/code-vault/autumbra-oss/` | **Primary** vault (~1.3G, synced 2026-10-24) |
| Bot box `/workspace/autumbra-oss-vault/` | Working **cache** — customise from here; do not re-clone |
| ZA `41.222.36.225` / `dev.ammosync.co.za` | **Abandoned** for this vault |

Do not vendor multi-GB upstream trees into Tank. Prefer primary vault + adapters.

## Vault pins (Watch lane)

| Adapter | Upstream | Vault SHA | Stronger-than-stock |
|---------|----------|-----------|---------------------|
| Vector | vectordotdev/vector | `bdd8842daf787497ae65f7e11e4eda6f72df8196` | Anomaly-only forward; telemetry off; onsite bus sink |
| Fluent Bit | fluent/fluent-bit | `05048e35d7106890006b7b593531bd51a16dfc93` | Anomaly-only; `HTTP_Server Off`; onsite-first |
| Steampipe | turbot/steampipe | `103201b1aad459788fb7d798637295600ed82179` | Read-only SQL; write plugins blocked; `update_check=false` |
| OpenCTI | OpenCTI-Platform/opencti | `879d3f198971256acf1b6e79152f9ffeb39842ab` | CE only; feed allowlist; no Filigran/EE phone-home |

**Out of this PR (do not touch):** `wazuh/` (parent brief later), `vllm/` (Tank-only / no GPU), `nemo-guardrails/` + `llm-guard/` (Air Gap), `ansible/` + `terraform/` (Enforce).

## Non-negotiables

1. **Zero-ingestion / onsite-first** — raw client payloads stay onsite; adapters forward bounded `AnomalyEvent` facts only.
2. **Anomaly-only** — default threshold `0.8`; below-threshold events are dropped.
3. **ThreatPayload burn** — `handoff_threat` → `accept_threat_payload` before any Watch→Enforce path. Burns never echo input.
4. **Telemetry off** — packaged presets fail closed if phone-home / cloud analytics sinks appear.
5. **Not live until merge + prove-it** — do not claim Dual-LLM, NeMo, or Wazuh triage are live from this slice.

## Files

- `agents/ghost/watch_oss/` — Python adapters
- `agents/ghost/configs/watch/` — Vector YAML, Fluent Bit conf, Steampipe `.spc`
- `POST /ghost/watch/intake` — flag-gated; accepts anomaly JSON → ThreatPayload open_match
- `GET /ghost/watch/oss` — status (Autumbra Watch copy)
- `tests/test_ghost_watch_oss_intake.py`

## Related drafts

- #289 `AUTUMBRA-OSS.md` + clone helper (shopping list / vault truth)
- #281 ThreatPayload + SLO (base of this branch)
- #284 air-gap + Enforce stub (parallel; does not own these adapters)
- Air Gap / Enforce customise PRs come from other lanes

## Merge gate

CI green. Merge **only after Zenas via AMMOSYNC**. Leave `WATCH_OSS_ENABLED` OFF in prod until founder arming.


## Wire (connections) — #284 stack

Path: **anomaly → synthetic match → ThreatPayload → Shields.propose → founder panel**.

- Flag `WATCH_OSS_ENABLED` / `GHOST_WATCH_OSS_ENABLED` default **OFF**.
- Signals that map to a shield kind (`waf`, `multipart`, `rate`, `bots`, …) open a
  deduped synthetic match and call `Shields.propose` (practice mode when no CF token).
- Other anomalies acknowledge as `open_match` only.
- Uses `#281`/`#284` `match_to_threat_payload` / burn unchanged — does **not** rewrite
  `threat_payload.py` schema.
- Aligns with Air Gap `#286`: optional Dual-LLM guard stays flag-OFF; no live HF.
- Founder must tap **Shield** on the Autumbra Watch panel to raise. Enforce OFF.
- Fixtures: `tests/fixtures/watch_oss/` + `tests/test_ghost_watch_oss_wire.py`.

**Stack base for this draft tip:** PR `#292` tip `a374a48` (`grok/autumbra-connected-dogfood`) —
`#281` → `#284` → `#286` Dual-LLM (flag OFF) → `#288` `/admin/autumbra` panel. Leave Wazuh / vLLM alone.

