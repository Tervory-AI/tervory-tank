"""Autumbra dogfood HF Inference path — skip when token unset (CI green)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from agents.ghost.dogfood_hf import (
    dogfood_watch_triage,
    hf_token,
    load_synthetic_fixtures,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "autumbra_dogfood" / "synthetic_siem.jsonl"


def test_synthetic_fixtures_load_only():
    rows = load_synthetic_fixtures(FIXTURE)
    assert len(rows) >= 2
    blob = " ".join(str(r) for r in rows).lower()
    assert "synthetic" in blob


def test_local_dogfood_threatpayload_without_hf():
    receipt = dogfood_watch_triage(live=False, fixtures_path=FIXTURE)
    assert receipt["product"] == "Autumbra" and receipt["role"] == "Watch"
    assert receipt["zero_ingestion"] is True
    assert receipt["live_hf"] is False
    assert receipt["threat_payload_local"]["accepted"] is True


@pytest.mark.integration
def test_live_hf_dogfood_when_token_set():
    if not hf_token():
        pytest.skip("HF_INFERENCE_TOKEN / HF_TOKEN unset")
    receipt = dogfood_watch_triage(live=True, fixtures_path=FIXTURE, soft_live=True)
    assert receipt["zero_ingestion"] is True
    assert receipt["threat_payload_local"]["accepted"] is True
    # Token present: either live text OR a recorded provider error (e.g. 402 credits).
    assert receipt["live_hf"] or receipt.get("hf_error")
    for name in ("HF_INFERENCE_TOKEN", "HF_TOKEN"):
        val = os.environ.get(name, "")
        if val:
            assert val not in (receipt.get("hf_text") or "")
            assert val not in (receipt.get("hf_error") or "")
