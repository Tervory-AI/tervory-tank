"""Smoke test: the app imports and its routes exist. Run with: pytest tests/"""
import os

os.environ.setdefault("DATABASE_URL", "postgresql://x:y@localhost/z")
os.environ.setdefault("LITELLM_MASTER_KEY", "test")
os.environ.setdefault("TANK_API_KEY", "test")

import importlib.util
import pathlib
import sys

spec = importlib.util.spec_from_file_location("tank_main", pathlib.Path(__file__).parent.parent / "tank" / "main.py")
mod = importlib.util.module_from_spec(spec)
# main.py looks itself up in sys.modules while including routers.
sys.modules.setdefault("tank_main", mod)
spec.loader.exec_module(mod)


def test_routes_exist():
    from http_routes import http_paths

    paths = http_paths(mod.app.routes)
    assert {"/health", "/v1/route", "/v1/ledger/summary", "/v1/policy"} <= paths
