"""Autumbra Dual-LLM air-gap E2E — fixtures only, no live HF / no network."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from agents.ghost.dogfood_airgap import AirgapDogfoodError, dogfood_airgap_e2e
from agents.ghost.dogfood_hf import load_synthetic_fixtures

FIXTURE = (
    Path(__file__).resolve().parent / "fixtures" / "autumbra_dogfood" / "synthetic_siem.jsonl"
)


def test_fixture_e2e_loads_synthetic_only():
    rows = load_synthetic_fixtures(FIXTURE)
    assert len(rows) >= 2
    blob = " ".join(str(r) for r in rows).lower()
    assert "synthetic" in blob
    assert "client" not in blob or "never client" in blob


def test_dogfood_airgap_e2e_fixtures_only(monkeypatch):
    """Full path: fixtures → guard OFF/ON → Watch accept/burn → Enforce dry."""
    monkeypatch.delenv("AUTUMBRA_HF_LIVE", raising=False)
    monkeypatch.delenv("GHOST_GUARDRAILS_ENABLED", raising=False)
    monkeypatch.delenv("AUTUMBRA_GUARDRAILS_ENABLED", raising=False)
    monkeypatch.delenv("GHOST_WRAITH_ENABLED", raising=False)
    monkeypatch.delenv("WRAITH_ENABLED", raising=False)
    monkeypatch.setenv("TANK_KEY", "ghost-test")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN_GHOST", "")

    receipt = dogfood_airgap_e2e(live=False, fixtures_path=FIXTURE)

    assert receipt["product"] == "Autumbra"
    assert receipt["roles"] == ["Watch", "Enforce"]
    assert receipt["zero_ingestion"] is True
    assert receipt["live_hf"] is False
    assert receipt["guardrails_default_off"] is True
    assert receipt["enforce_default_off"] is True
    assert receipt["guard_flag_off_decodes"] is True
    assert receipt["guard_flag_on_burns_injection"] is True
    assert receipt["threat_payload_accept"]["accepted"] is True
    assert receipt["threat_payload_burn_dirty"]["burned"] is True
    assert receipt["rails_before_enforce"]["clean_ok"] is True
    assert receipt["rails_before_enforce"]["dirty_burned"] is True

    asgi = receipt["asgi"]
    assert asgi["watch_accept"]["accepted"] is True
    assert asgi["watch_burn_dirty"]["burned"] is True
    assert asgi["watch_burn_dirty"]["echoed_injection"] is False
    assert asgi["enforce_off_default"]["disabled"] is True
    assert asgi["enforce_would"]["dry_only"] is True
    assert asgi["enforce_would"]["enforced"] is False
    assert asgi["enforce_would"]["would_enforce"] is True
    assert asgi["enforce_burn_dirty"]["burned"] is True
    assert asgi["enforce_burn_dirty"]["echoed_injection"] is False

    assert receipt["ok"] is True

    # Flags restored after dogfood (Enforce / guardrails still OFF).
    from agents.ghost import guardrails as gr
    from agents.ghost import wraith as wr

    assert gr.enabled() is False
    assert wr.enabled() is False

    # No token leakage / no HF URL in receipt.
    blob = str(receipt)
    assert "router.huggingface.co" not in blob
    for name in ("HF_INFERENCE_TOKEN", "HF_TOKEN"):
        val = os.environ.get(name, "")
        if val:
            assert val not in blob


def test_dogfood_airgap_e2e_refuses_live():
    with pytest.raises(AirgapDogfoodError, match="Fixtures-only"):
        dogfood_airgap_e2e(live=True, fixtures_path=FIXTURE)


def test_autumbra6_doc_has_fixture_e2e_section():
    doc = (
        Path(__file__).resolve().parents[1] / "docs/cursor/AUTUMBRA-6-dual-llm-airgap.md"
    ).read_text()
    assert "How to run fixture E2E" in doc
    assert "dogfood_airgap_e2e" in doc
    assert "NO live HF" in doc or "no live HF" in doc.lower() or "Fixtures-only" in doc
    assert "Autumbra" in doc and "Watch" in doc and "Enforce" in doc
