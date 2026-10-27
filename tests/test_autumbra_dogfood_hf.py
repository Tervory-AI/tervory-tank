"""Autumbra dogfood — fixtures-only by default; live hard-gated."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from agents.ghost.dogfood_hf import (
    dogfood_watch_triage,
    hf_token,
    live_armed,
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


def test_live_true_refused_without_autumbra_hf_live(monkeypatch):
    """Zenas STOP: live=True alone must not spend via Tank."""
    monkeypatch.delenv("AUTUMBRA_HF_LIVE", raising=False)
    receipt = dogfood_watch_triage(live=True, fixtures_path=FIXTURE, soft_live=True)
    assert receipt["live_hf"] is False
    assert receipt["threat_payload_local"]["accepted"] is True
    assert "STOPPED" in (receipt.get("note") or "") or "AUTUMBRA_HF_LIVE" in (
        receipt.get("hf_error") or ""
    )


@pytest.mark.integration
def test_live_hf_dogfood_when_armed():
    """Only when Zenas says go: AUTUMBRA_HF_LIVE=1 + Tank key."""
    if not live_armed():
        pytest.skip("AUTUMBRA_HF_LIVE!=1 — fixtures-only until Zenas tops up and says go")
    if not hf_token():
        pytest.skip("TANK_KEY unset")
    receipt = dogfood_watch_triage(live=True, fixtures_path=FIXTURE, soft_live=True)
    assert receipt["zero_ingestion"] is True
    assert receipt["threat_payload_local"]["accepted"] is True
    assert receipt["live_hf"] or receipt.get("hf_error")
    # Never echo Tank key or provider tokens in the receipt.
    for name in ("TANK_KEY", "HF_INFERENCE_TOKEN", "HF_TOKEN"):
        val = os.environ.get(name, "")
        if val:
            assert val not in (receipt.get("hf_text") or "")
            assert val not in (receipt.get("hf_error") or "")
