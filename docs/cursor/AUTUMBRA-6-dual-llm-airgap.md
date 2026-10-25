# Autumbra-6: Dual-LLM air gap (NeMo-front tank-only)

> Written 24 Oct 2026. Dogfood slice. **Not full NVIDIA NeMo. Not GPU/vLLM bunker. Not live enforce. Not auto-merge.**

Product: **Autumbra**. Roles: **Watch** / **Enforce**. Code may still live under `agents/ghost` and env flags `GHOST_*` short-term.

## Architecture (brief → code)

```
untrusted logs / triage JSON
        │
        ▼
  Optional NeMo / LLM Guard-shaped door  ← agents/ghost/guardrails.py
  (flag OFF by default; Tank-only stubs)
  GHOST_GUARDRAILS_ENABLED / AUTUMBRA_GUARDRAILS_ENABLED=1 to arm
        │
        ▼
  Watch (code: agents/ghost)             ← propose-only; no Cloudflare apply / no weapons
        │
        ▼
  Pydantic ThreatPayload                 ← agents/ghost/threat_payload.py (#281)
  (schema burn; fixed detail; always on)
        │
        ▼
  Enforce (stub flag OFF)                ← agents/ghost/wraith.py + rails/
  GHOST_WRAITH_ENABLED default OFF (#284)
  never reads raw logs — ThreatPayload only
```

Watch may touch dirty text. Enforce must not. Nothing crosses the air gap except a
validated `ThreatPayload`. Founder Shield tap remains the only path that can
change the edge.

## What this PR adds

1. `agents/ghost/guardrails.py` — `enabled()` (default **OFF**),
   `guard_inbound` / `guard_inbound_if_enabled`, fixed `GUARD_BURN_DETAIL`.
   Markers imported from `INJECTION_MARKERS` in `threat_payload.py`.
2. Wire on `POST /ghost/triage/accept` and Enforce raw — **if_enabled** path.
   When flag OFF, ThreatPayload burn alone still protects.
3. `agents/ghost/rails/` — NeMo-shaped Colang/config stubs (ThreatPayload-only
   before Enforce). Inspired by vault `nemo-guardrails` (see TERVORY.md).
4. `agents/ghost/scanners/` — llm-guard-shaped PII + injection stubs (regex;
   no HF). Inspired by vault `llm-guard` (see TERVORY.md; upstream ARCHIVED).
5. Docs + tests: injection burns (422, fixed detail, body not echoed), clean
   propose still proposes only, Enforce still OFF by default, guard flag OFF
   by default.

## Vault OSS (box cache — do not re-clone)

| Tree | Path |
|------|------|
| NeMo Guardrails | `/workspace/autumbra-oss-vault/nemo-guardrails` |
| LLM Guard | `/workspace/autumbra-oss-vault/llm-guard` |

Optional: `AUTUMBRA_OSS_GUARD=nemo|llm-guard` documents the future call site.
Packages are **not** required; marker/stub adapters run when unavailable.
Tank models until GPU — no invented GPU blocker.

## Stronger-than-stock (this slice)

- Rails that burn anything not ThreatPayload before Enforce
  (`rails.ensure_threat_payload_before_enforce`)
- PII + injection scanners before Watch LLM (flag-armed path)
- Zero-ingestion: no client payload to Tervory cloud from these paths
- Telemetry off in rails `config.yml`

## Tank-only until GPU

No required `nemoguardrails` / `llm_guard` install, no vLLM, no second model
room. Inference stays on Tank.

## No weapons on Watch

Watch remains propose-only. This PR does **not** give Watch Cloudflare apply or
auto-enforce. Enforce stays flag-off + founder tap. Enforce is not enabled by
default.

## Out of scope

- Full NVIDIA NeMo Guardrails install / live `rails.co` session
- vLLM / Dual-LLM GPU bunker
- Live Enforce / edge apply without founder tap
- Auto-merge (AMMOSYNC / Zenas)
- Collectors / Wazuh / Vector ingest paths

## Dogfood: Hugging Face Inference (optional)

Optional Watch triage over **synthetic fixtures only** — never client payloads
(zero-ingestion). Local ThreatPayload burn always runs on Tank; HF is additive.

| Item | Value |
|------|--------|
| Module | `agents/ghost/dogfood_hf.py` |
| Fixtures | `tests/fixtures/autumbra_dogfood/synthetic_siem.jsonl` |
| Token env | `HF_INFERENCE_TOKEN` (preferred) or `HF_TOKEN` |
| Model env | `AUTUMBRA_HF_MODEL` (default `meta-llama/Llama-3.1-8B-Instruct`) |
| API | `https://router.huggingface.co/v1/chat/completions` |

### Load token (never print values)

```bash
source /home/box/agent-data/agents/bd32fdb6-b222-4404-a278-ac58baaf52fd/.env.hf
# or: source /workspace/autumbra-oss-vault/_tervory/load-hf-env.sh
```

### Local-only (CI / default)

```bash
PYTHONPATH=. /workspace/tank-venv/bin/pytest tests/test_autumbra_dogfood_hf.py -q
```

### Live HF — STOPPED until Zenas says go (24 Oct 2026)

Credits burned. **Fixtures-only** dogfood until Zenas tops up Inference Providers
credits and explicitly says go. `live=True` alone is refused; live also requires
`AUTUMBRA_HF_LIVE=1`.

```bash
# Do NOT run until Zenas says go:
# export AUTUMBRA_HF_LIVE=1
# source .../.env.hf
# PYTHONPATH=. .../python -c 'from agents.ghost.dogfood_hf import dogfood_watch_triage; print(dogfood_watch_triage(live=True))'
```

Integration live test skips unless `AUTUMBRA_HF_LIVE=1`. Default pytest stays
fixtures-only and green. Not a permanent GPU bunker blocker — path stays wired,
spend is hard-gated.

## How to run fixture E2E (NO live HF)

End-to-end Autumbra Dual-LLM air gap on **synthetic fixtures only**. Proves:

1. Load `tests/fixtures/autumbra_dogfood/synthetic_siem.jsonl`
2. Optional guardrails adapter (flag **OFF** decodes; flag **ON** burns injection)
3. Watch triage accept → ThreatPayload burn / accept
4. Rails `ensure_threat_payload_before_enforce` → Enforce stub dry `would_enforce`
   (flag temporarily ON inside the dogfood only — never edge apply)

| Item | Value |
|------|--------|
| Module | `agents/ghost/dogfood_airgap.py` → `dogfood_airgap_e2e(live=False)` |
| Fixtures | `tests/fixtures/autumbra_dogfood/synthetic_siem.jsonl` |
| Live HF | **Forbidden** — `live=True` raises; do not set `AUTUMBRA_HF_LIVE=1` |

### Pytest (CI / default)

```bash
cd /workspace/ghost-build/tervory-tank
PYTHONPATH=. /workspace/tank-venv/bin/pytest tests/test_autumbra_dogfood_airgap.py -q
```

### Python receipt (fixtures only)

```bash
cd /workspace/ghost-build/tervory-tank
PYTHONPATH=. /workspace/tank-venv/bin/python -c \
  'from agents.ghost.dogfood_airgap import dogfood_airgap_e2e; import json; print(json.dumps(dogfood_airgap_e2e(live=False), indent=2))'
```

Receipt fields: `product=Autumbra`, `roles=[Watch, Enforce]`, `live_hf=False`,
`threat_payload_accept` / `threat_payload_burn_dirty`, ASGI `watch_accept`,
`enforce_would.dry_only`, `ok=true` when the whole path passes.

Do **not** call `dogfood_watch_triage(live=True)` or hit `router.huggingface.co`
from this path. Guard flags and `GHOST_WRAITH_ENABLED` remain OFF by default
after the dogfood restores env.
