"""The default pytest collector must accept legacy and platform product names."""
import os
from pathlib import Path
import shutil
import subprocess
import sys


def test_legacy_and_gate_product_names_collect_together(tmp_path):
    source = Path(__file__).parent
    suite = tmp_path / "gates78"
    products = suite / "products"
    products.mkdir(parents=True)
    for relative in ("__init__.py", "products/__init__.py", "conftest.py", "gate78_contract.py"):
        shutil.copyfile(source / relative, suite / relative)
    (tmp_path / "test_market_lab.py").write_text("def test_legacy_placeholder():\n    assert True\n")
    (products / "placeholder_market_fixture.py").write_text("VALUE = 'placeholder-value'\n")
    (products / "test_market_lab.py").write_text(
        "from placeholder_market_fixture import VALUE\n"
        "def test_platform_placeholder():\n    assert VALUE == 'placeholder-value'\n"
    )
    root = source.parents[1]
    env = dict(os.environ, PYTEST_ADDOPTS="", PYTEST_PLUGINS="")
    env["PYTHONPATH"] = os.pathsep.join(str(root / part) for part in ("", "tank", "tests", "agents", "agents/_chassis"))
    result = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q",
                             "--import-mode=prepend", str(tmp_path)],
                            cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "test_legacy_placeholder" in result.stdout
    assert "test_platform_placeholder" in result.stdout
    assert "2 tests collected" in result.stdout
