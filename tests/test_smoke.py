"""Smoke test: the app imports and its routes exist. Run with: pytest tests/"""
import os

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://x:y@localhost/z")
os.environ.setdefault("LITELLM_MASTER_KEY", "test")
os.environ.setdefault("TANK_API_KEY", "test")

import importlib.util
import pathlib
import sys

spec = importlib.util.spec_from_file_location("tank_main", pathlib.Path(__file__).parent.parent / "tank" / "main.py")
mod = importlib.util.module_from_spec(spec)
# Registration needs this fresh instance, but collection must not replace the
# Tank fixture already held by other test modules.
_missing = object()
_previous = sys.modules.get(spec.name, _missing)
sys.modules[spec.name] = mod
try:
    spec.loader.exec_module(mod)
finally:
    if _previous is _missing:
        sys.modules.pop(spec.name, None)
    else:
        sys.modules[spec.name] = _previous


@pytest.fixture(autouse=True)
def bind_smoke_runtime(monkeypatch):
    monkeypatch.setitem(sys.modules, spec.name, mod)


def test_routes_exist():
    from http_routes import http_paths

    paths = http_paths(mod.app.routes)
    assert {"/health", "/v1/route", "/v1/ledger/summary", "/v1/policy"} <= paths
