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

### Live synthetic smoke (when token set)

```bash
source /home/box/agent-data/agents/bd32fdb6-b222-4404-a278-ac58baaf52fd/.env.hf
PYTHONPATH=. /workspace/tank-venv/bin/python -c \
  'from agents.ghost.dogfood_hf import dogfood_watch_triage; \
   r=dogfood_watch_triage(live=True); print(r["live_hf"], r["threat_payload_local"], (r["hf_text"] or "")[:120])'
# or:
PYTHONPATH=. /workspace/tank-venv/bin/pytest tests/test_autumbra_dogfood_hf.py -q -m integration
```

If the token is unset, integration tests **skip** (CI stays green). This is not a
permanent GPU blocker — Tank markers/stubs remain the default path.

### Notes from box smoke (24 Oct 2026)

- Token loads (Pro `whoami` OK). Prefer `HF_INFERENCE_TOKEN`.
- Live call uses Inference Providers router. If HTTP **402**, top up Inference
  Providers credits — the dogfood path is wired; local ThreatPayload still passes.
- Soft receipt: `dogfood_watch_triage(live=True)` records `hf_error` instead of
  crashing CI when credits/model are unavailable.
