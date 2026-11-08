"""The typed feed snapshot preserves source records and offline evidence."""
import importlib.util
from dataclasses import asdict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "tank/skills/market.series_fetch"


def load_sources(version, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "agents/market_lab"))
    path = SKILL / version / "feeds/engines/ffl/sources.py"
    spec = importlib.util.spec_from_file_location("source_contract_" + version, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_typed_catalog_preserves_every_source_field(monkeypatch):
    old = load_sources("1.4.0", monkeypatch)
    new = load_sources("1.6.0", monkeypatch)
    expected = [asdict(row) for row in old.sources()]
    assert len(expected) == 38
    assert [asdict(row) for row in new.sources()] == expected


def test_source_defaults_are_independent_and_fixed_flags_cannot_be_overridden(monkeypatch):
    sources = load_sources("1.6.0", monkeypatch)
    args = dict(id="placeholder", name="placeholder", kind="series",
                url="https://placeholder.example", licence="placeholder",
                terms_checked_at="2026-11-08", cadence="daily", adapter="csv")
    first, second = sources._copy(**args), sources._copy(**args)
    assert first.enabled is True and first.allow_bulk is True
    assert first.key_name == "" and first.key_required is False
    first.config["placeholder"] = True
    assert second.config == {}
    with pytest.raises(TypeError):
        sources._copy(**args, enabled=False)
    with pytest.raises(TypeError):
        sources._copy(**args, allow_bulk=False)
    configured = sources._copy(**args, config={"page": 2}, key_name="PLACEHOLDER_KEY", key_required=True)
    assert configured.config == {"page": 2}
    assert configured.key_name == "PLACEHOLDER_KEY" and configured.key_required is True


def test_minor_retains_all_existing_eval_cases():
    assert (SKILL / "1.6.0/evals/cases.jsonl").read_bytes() == (
        SKILL / "1.4.0/evals/cases.jsonl").read_bytes()
