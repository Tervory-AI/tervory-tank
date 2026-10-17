"""Test harness: Tank's package directory is not installed, so put it on sys.path.

pytest loads this file before any test module. That lets test_smoke import
tank.main (which imports skala) and lets the offline skill tests import skala.
"""
import sys
from pathlib import Path

import pytest

_TANK = Path(__file__).resolve().parents[1] / "tank"
if str(_TANK) not in sys.path:
    sys.path.insert(0, str(_TANK))


@pytest.fixture(autouse=True)
def _lab_vault_gate_starts_off():
    """A test that turns lab.vault on for the feed gate must not leak into the next test."""
    yield
    import sys

    keys = sys.modules.get("feeds.keys")
    if keys is None:
        return
    keys.configure_vault(enabled=False)
    keys._held.clear()


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:
    # pytest-asyncio warns, and will later error, when this is unset. There is no
    # project config file in this lane, so set the ini cache before the plugin reads it.
    if not config.getini("asyncio_default_fixture_loop_scope"):
        config._inicache["asyncio_default_fixture_loop_scope"] = "function"
