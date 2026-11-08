"""Offline roster checks; the pinned gateway contract runs in nonroot CI."""

from __future__ import annotations

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

HELD = {"sarvam-105b-direct", "trinity-large-thinking-direct"}


def _rows(filename: str) -> dict:
    data = yaml.safe_load((ROOT / "litellm" / filename).read_text(encoding="utf-8"))
    return {row["model_name"]: row for row in data["model_list"]}


@pytest.mark.parametrize("filename", FILES)
def test_maker_direct_exact_upstream_ids(filename: str) -> None:
    book = _rows(filename)
    for name, upstream in EXPECTED.items():
        if name in HELD:
            continue
        assert name in book, name
        assert book[name]["litellm_params"]["model"] == upstream, name


@pytest.mark.parametrize("filename", FILES)
def test_sarvam_extra_headers_env_ref_present(filename: str) -> None:
    config = yaml.safe_load((ROOT / "litellm" / filename).read_text())
    row = next(row for row in config["x_unpriced_models"] if row["model_name"] == "sarvam-105b-direct")
    headers = row["litellm_params"]["extra_headers"]
    assert headers["api-subscription-key"] == "os.environ/SARVAM_API_KEY"
    assert row["litellm_params"]["api_key"] == "os.environ/SARVAM_API_KEY"


@pytest.mark.parametrize("filename", FILES)
def test_unpriced_models_are_unavailable_even_with_provider_keys(filename, monkeypatch):
    import importlib.util
    root = ROOT / "litellm"
    monkeypatch.syspath_prepend(str(root))
    spec = importlib.util.spec_from_file_location("maker_engine_config", root / "engine_config.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    config = yaml.safe_load((root / filename).read_text())
    monkeypatch.setenv("SARVAM_API_KEY", "placeholder-sarvam")
    monkeypatch.setenv("ARCEE_API_KEY", "placeholder-arcee")
    assert HELD.isdisjoint(_rows(filename))
    held = {row["model_name"]: row for row in config["x_unpriced_models"]}
    assert held.keys() == HELD
    for name, row in held.items():
        assert row["litellm_params"]["model"] == EXPECTED[name]
        for section in ("litellm_params", "model_info"):
            assert "input_cost_per_token" not in row[section]
            assert "output_cost_per_token" not in row[section]
    generated = module.configure(config)
    assert "x_unpriced_models" not in generated
    assert HELD.isdisjoint(row["model_name"] for row in generated["model_list"])
    for section in ("litellm_settings", "router_settings"):
        for chain in generated.get(section, {}).get("fallbacks", []):
            assert HELD.isdisjoint(chain)
            assert all(HELD.isdisjoint(targets) for targets in chain.values())


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
