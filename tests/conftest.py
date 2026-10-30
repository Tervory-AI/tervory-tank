"""Test harness: Tank's package directory is not installed, so put it on sys.path.

pytest loads this file before any test module. That lets test_smoke import
tank.main (which imports skala) and lets the offline skill tests import skala.
"""
import sys
import os
import shutil
from pathlib import Path

import pytest
import pytest_asyncio

_CHASSIS = Path(__file__).resolve().parents[1] / "agents" / "_chassis"
if str(_CHASSIS) not in sys.path:
    sys.path.insert(0, str(_CHASSIS))

_TANK = Path(__file__).resolve().parents[1] / "tank"
if str(_TANK) not in sys.path:
    sys.path.insert(0, str(_TANK))


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:
    # pytest-asyncio warns, and will later error, when this is unset. There is no
    # project config file in this lane, so set the ini cache before the plugin reads it.
    if not config.getini("asyncio_default_fixture_loop_scope"):
        config._inicache["asyncio_default_fixture_loop_scope"] = "function"


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    """Expose failed test identities when archived Actions logs are unavailable."""
    if not report.failed or os.environ.get("GITHUB_ACTIONS") != "true":
        return
    path, line, name = report.location
    # Parameter values and exception contents can contain private input. Only
    # publish the source location and unparameterized test name.
    def escape(value: str) -> str:
        return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A").replace(",", "%2C")
    print(f"\n::error file={escape(path)},line={line + 1},title=Pytest failure::{escape(name.split('[', 1)[0])} ({report.when})", flush=True)


@pytest_asyncio.fixture
async def real_chromium():
    """Required browser tests fail, rather than skip, if CI setup is missing."""
    from playwright.async_api import async_playwright
    executable = os.environ.get('READ1_CHROMIUM_EXECUTABLE') or next(
        (path for name in ('chromium', 'chromium-browser', 'google-chrome', 'google-chrome-stable')
         if (path := shutil.which(name))), None)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(executable_path=executable, args=['--no-sandbox'])
        try:
            yield browser
        finally:
            await browser.close()
