"""One offline command exercises the production jobs through fake boundaries."""
import argparse
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description="Autumbra Saturday dry run; no external connections or model calls.")
    parser.add_argument("--dry-run", action="store_true", required=True)
    parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    vendor = root if (root / "tank/main.py").is_file() else root / "vendor/tervory-tank"
    # Inherited production settings cannot select a real queue, SMTP account,
    # provider or model. Each proof supplies its own temporary paths and fakes.
    prefixes = ("AUTUMBRA_", "GHOST_", "COOLIFY_", "CLOUDFLARE_", "TANK_", "THREAT_", "ENFORCE_", "WRAITH_")
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(prefixes) and k not in {"DATA_DIR", "SITE_NAME", "TENANT_ID", "PYTEST_ADDOPTS"}}
    env["PYTHONPATH"] = os.pathsep.join(str(p) for p in (
        root, root / "tests", vendor, vendor / "tank", vendor / "tests", vendor / "agents/_chassis"))
    env.update(AUTUMBRA_HF_LIVE="0", GHOST_PATCH_PR_ENABLED="0")
    tests = ["tests/test_autumbra_gate4_operations.py", "tests/test_autumbra_gate4_settings.py",
             "tests/test_autumbra_finish_feeds.py", "tests/test_autumbra_finish_jobs.py",
             "tests/test_autumbra_finish_monitor.py", "tests/test_autumbra_finish_sources.py",
             "tests/test_autumbra_finish_exercises.py", "tests/test_autumbra_dogfood_airgap.py",
             "tests/test_autumbra_w3_blocks.py"]
    return subprocess.call([sys.executable, "-m", "pytest", "-v", "--timeout=120",
        "--disable-socket", "--allow-unix-socket", "-p", "no:cacheprovider", *tests], cwd=root, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
