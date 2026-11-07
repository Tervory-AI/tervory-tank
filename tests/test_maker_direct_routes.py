"""Offline checks for maker-direct LiteLLM routes (PR soft spots).

No live model calls, no network inference. Sarvam extra_headers env
interpolation is verified against pinned LiteLLM v1.106.4 proxy behavior when
that package is importable; otherwise the config-shape assertions still run.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
FILES = ["config.yaml", "config.za.yaml"]

# Exact tank model_name → upstream openai/ id (no substitutes).
EXPECTED = {
    "minimax-m3.1-flash-direct": "openai/MiniMax-M3.1-Flash",
    "minimax-m3-direct": "openai/MiniMax-M3",
    "glm-5.3-direct": "openai/glm-5.3",
    "glm-5.2-direct": "openai/glm-5.2",
    "glm-5.1-direct": "openai/glm-5.1",
    "glm-5-direct": "openai/glm-5",
    "glm-4.7-direct": "openai/glm-4.7",
    "glm-4.6-direct": "openai/glm-4.6",
    "qwen3.5-27b-direct": "openai/qwen3.5-27b",
    "qwen3.5-122b-a10b-direct": "openai/qwen3.5-122b-a10b",
    "qwen3.5-397b-a17b-direct": "openai/qwen3.5-397b-a17b",
    "step-3.5-flash-direct": "openai/step-3.5-flash",
    "step-3.7-flash-direct": "openai/step-3.7-flash",
    "trinity-large-thinking-direct": "openai/trinity-large-thinking",
    "sarvam-105b-direct": "openai/sarvam-105b",
}

PINNED_LITELLM = "1.106.4"


def _rows(filename: str) -> dict:
    data = yaml.safe_load((ROOT / "litellm" / filename).read_text(encoding="utf-8"))
    return {row["model_name"]: row for row in data["model_list"]}


@pytest.mark.parametrize("filename", FILES)
def test_maker_direct_exact_upstream_ids(filename: str) -> None:
    book = _rows(filename)
    for name, upstream in EXPECTED.items():
        assert name in book, name
        assert book[name]["litellm_params"]["model"] == upstream, name


@pytest.mark.parametrize("filename", FILES)
def test_sarvam_extra_headers_env_ref_present(filename: str) -> None:
    row = _rows(filename)["sarvam-105b-direct"]
    headers = row["litellm_params"]["extra_headers"]
    assert headers["api-subscription-key"] == "os.environ/SARVAM_API_KEY"
    assert row["litellm_params"]["api_key"] == "os.environ/SARVAM_API_KEY"


@pytest.mark.parametrize("filename", FILES)
def test_sarvam_and_arcee_usd_ledger_not_invented(filename: str) -> None:
    book = _rows(filename)
    sarvam = book["sarvam-105b-direct"]
    assert sarvam["litellm_params"]["input_cost_per_token"] == 0
    assert sarvam["litellm_params"]["output_cost_per_token"] == 0
    assert sarvam["model_info"]["input_cost_per_token"] == 0
    assert sarvam["model_info"]["output_cost_per_token"] == 0
    assert "159345" not in (ROOT / "litellm" / filename).read_text(encoding="utf-8")
    assert "0.010623" not in (ROOT / "litellm" / filename).read_text(encoding="utf-8")

    arcee = book["trinity-large-thinking-direct"]
    assert arcee["litellm_params"]["input_cost_per_token"] == 0
    assert arcee["litellm_params"]["output_cost_per_token"] == 0
    assert arcee["model_info"].get("price_unverified") == "blog-only-2026-11-07"


def test_docs_mark_unverified_and_omit_invented_fx() -> None:
    text = (ROOT / "docs/ops/MAKER-DIRECT-KEYS-2026-11-07.md").read_text(encoding="utf-8")
    assert "0.010623" not in text
    assert "~$0.159" not in text
    assert "UNVERIFIED for Tank USD ledger" in text
    assert "₹15→₹60" in text or "₹15 / ₹60" in text
    assert "sarvam-105b" in text
    assert "trinity-large-thinking" in text


def test_dockerfile_pins_litellm_v1_106_4() -> None:
    text = (ROOT / "litellm" / "Dockerfile").read_text(encoding="utf-8")
    assert "ghcr.io/berriai/litellm:v1.106.4" in text


def test_sarvam_extra_headers_interpolated_by_pinned_proxy_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """ProxyConfig recursive os.environ walk (LiteLLM v1.106.4) expands nested headers."""
    litellm = pytest.importorskip("litellm")
    import importlib.metadata as metadata

    ver = metadata.version("litellm")
    if ver != PINNED_LITELLM:
        pytest.skip(f"need litellm=={PINNED_LITELLM} for pin-faithful check, have {ver}")

    from litellm.proxy.proxy_server import ProxyConfig

    monkeypatch.setenv("SARVAM_API_KEY", "offline-test-key-not-real")
    cfg = {
        "model_list": [
            {
                "model_name": "sarvam-105b-direct",
                "litellm_params": {
                    "model": "openai/sarvam-105b",
                    "api_base": "https://api.sarvam.ai/v1",
                    "api_key": "os.environ/SARVAM_API_KEY",
                    "extra_headers": {
                        "api-subscription-key": "os.environ/SARVAM_API_KEY",
                    },
                },
            }
        ]
    }
    out = ProxyConfig()._check_for_os_environ_vars(cfg)
    params = out["model_list"][0]["litellm_params"]
    assert params["api_key"] == "offline-test-key-not-real"
    assert params["extra_headers"]["api-subscription-key"] == "offline-test-key-not-real"
