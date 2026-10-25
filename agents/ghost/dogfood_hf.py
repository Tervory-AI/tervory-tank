"""Autumbra dogfood: optional Hugging Face Inference for Watch triage.

Zero-ingestion: synthetic/fixture logs ONLY — never send client payloads to HF.
Burn / ThreatPayload validation always stays local on Tank.

Token from env `HF_INFERENCE_TOKEN` (preferred) or `HF_TOKEN`. If unset, callers
and tests skip — CI stays green.

Live HF is **hard-gated**: requires `AUTUMBRA_HF_LIVE=1` *and* `live=True`.
Default / Zenas STOP (2026-10-24): fixtures-only — no Inference / GPU spend until
he tops up credits and explicitly says go.

Load secrets (never print values):
  source /home/box/agent-data/agents/bd32fdb6-b222-4404-a278-ac58baaf52fd/.env.hf
  # or: source /workspace/autumbra-oss-vault/_tervory/load-hf-env.sh

API: Hugging Face Inference Providers via OpenAI-compatible router
(`https://router.huggingface.co/v1/chat/completions`). Legacy
`api-inference.huggingface.co` is SSL-broken from this box.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx

from .threat_payload import ThreatBurned, accept_threat_payload

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "autumbra_dogfood"
# Default chat model on Inference Providers; override with AUTUMBRA_HF_MODEL.
DEFAULT_MODEL = os.environ.get("AUTUMBRA_HF_MODEL", "meta-llama/Llama-3.1-8B-Instruct")
HF_CHAT_URL = "https://router.huggingface.co/v1/chat/completions"


class HfDogfoodError(RuntimeError):
    """Live HF call failed (credits, model, network). Not a Tank burn."""


def hf_token() -> str | None:
    for name in ("HF_INFERENCE_TOKEN", "HF_TOKEN"):
        val = os.environ.get(name, "").strip()
        if val:
            return val
    return None


def live_armed() -> bool:
    """True only when AUTUMBRA_HF_LIVE=1 (Zenas explicit go after credit top-up)."""
    return os.environ.get("AUTUMBRA_HF_LIVE", "").strip() == "1"


def load_synthetic_fixtures(path: Path | None = None) -> list[dict[str, Any]]:
    """Load synthetic SIEM-ish JSONL. Never client data."""
    target = path or (FIXTURES_DIR / "synthetic_siem.jsonl")
    rows: list[dict[str, Any]] = []
    for line in target.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def build_watch_prompt(events: list[dict[str, Any]]) -> str:
    """Prompt for Watch triage over synthetic fixtures only."""
    blob = "\n".join(json.dumps(e, sort_keys=True) for e in events)
    return (
        "You are Autumbra Watch (propose-only). Summarize these SYNTHETIC SIEM "
        "fixture lines for dogfood. Do not invent client data. Reply with a short "
        "JSON object: {\"summary\": str, \"suspect_site\": str|null}.\n\n"
        f"FIXTURES:\n{blob}\n"
    )


def call_hf_inference(prompt: str, *, model: str | None = None, timeout: float = 60.0) -> str:
    """Call HF Inference Providers chat completions. Raises if live disarmed or token missing."""
    if not live_armed():
        raise HfDogfoodError(
            "Live HF STOPPED — set AUTUMBRA_HF_LIVE=1 only after Zenas tops up and says go"
        )
    token = hf_token()
    if not token:
        raise HfDogfoodError("HF_INFERENCE_TOKEN / HF_TOKEN unset — skip live dogfood")
    model_id = model or DEFAULT_MODEL
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": "Autumbra Watch dogfood. Synthetic fixtures only."},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 200,
        "temperature": 0.2,
    }
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(HF_CHAT_URL, headers=headers, json=payload)
    if resp.status_code == 402:
        raise HfDogfoodError(
            "HF Inference Providers: no remaining credits (402). "
            "Token is valid; top up credits to run live dogfood."
        )
    if resp.status_code >= 400:
        # Never echo Authorization. Body may name the model — OK for ops.
        raise HfDogfoodError(f"HF chat HTTP {resp.status_code}: {resp.text[:240]}")
    data = resp.json()
    try:
        return str(data["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as exc:
        raise HfDogfoodError(f"Unexpected HF response shape: {str(data)[:240]}") from exc


def dogfood_watch_triage(
    *,
    live: bool = False,
    fixtures_path: Path | None = None,
    soft_live: bool = True,
) -> dict[str, Any]:
    """Run synthetic dogfood. Local burn path always; HF only when live+token.

    Returns a receipt dict suitable for tests/docs. Never uploads client payloads.
    When soft_live=True, credit/network errors are recorded in the receipt instead
    of raising (so CI / dogfood scripts stay usable until HF credits are topped up).
    """
    events = load_synthetic_fixtures(fixtures_path)
    receipt: dict[str, Any] = {
        "product": "Autumbra",
        "role": "Watch",
        "zero_ingestion": True,
        "fixture_count": len(events),
        "live_hf": False,
        "hf_text": None,
        "hf_error": None,
        "threat_payload_local": None,
        "note": "Synthetic fixtures only. ThreatPayload burn stays on Tank.",
    }
    # Local ThreatPayload path still exercised with a clean propose fixture shape.
    clean = {
        "schema_version": "ghost.threat.v1",
        "action": "propose_shield",
        "site": "coolify.tervory.com",
        "kind": "block_multipart_post",
        "path": None,
        "match_id": "dogfood-synthetic",
        "cve_ids": ["CVE-2026-109618"],
        "severity": "known_exploited",
        "reason": "synthetic dogfood SIEM fixture match",
        "confidence": 0.9,
    }
    try:
        payload = accept_threat_payload(json.dumps(clean))
        receipt["threat_payload_local"] = {
            "accepted": True,
            "action": payload.action.value,
            "site": payload.site,
        }
    except ThreatBurned:
        receipt["threat_payload_local"] = {"accepted": False}

    if not live:
        return receipt
    if not live_armed():
        receipt["note"] = (
            "Live HF STOPPED (fixtures-only). Set AUTUMBRA_HF_LIVE=1 only after "
            "Zenas tops up credits and says go."
        )
        receipt["hf_error"] = "AUTUMBRA_HF_LIVE not set — refusing live call"
        return receipt
    if not hf_token():
        receipt["note"] = "HF token unset — local-only dogfood"
        return receipt
    prompt = build_watch_prompt(events)
    try:
        text = call_hf_inference(prompt)
    except (HfDogfoodError, httpx.HTTPError) as exc:
        receipt["hf_error"] = str(exc)[:300]
        receipt["note"] = "Live HF attempted; see hf_error (token may be OK; credits/model)."
        if not soft_live:
            raise
        return receipt
    receipt["live_hf"] = True
    # Do not store raw prompt with secrets; only a short model reply excerpt.
    receipt["hf_text"] = text[:500]
    return receipt
