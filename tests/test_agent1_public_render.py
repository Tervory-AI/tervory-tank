"""Real public-web regression in GitHub cloud CI; no model or production keys.

A normal non-internal gateway corridor fronts an internal-only Chromium service.
Local opt-in: AGENT1_PUBLIC_RENDER=1 pytest tests/test_agent1_public_render.py
"""
import os
import subprocess
from pathlib import Path

import pytest

from test_agent1_container_runtime import run_browser_boundary


@pytest.mark.skipif(not (os.environ.get("GITHUB_ACTIONS") == "true" or os.environ.get("AGENT1_PUBLIC_RENDER")),
    reason="Public website/container test runs in GitHub cloud CI or explicit cloud opt-in")
def test_example_com_through_render_with_internal_browser(capsys):
    root = Path(__file__).resolve().parents[1]
    # Build the actual production Dockerfiles. Only Chromium and the gateway are
    # needed; no Hermes model, sandbox image, deployment or external key is used.
    for name in ("browser", "gateway"):
        result = subprocess.run(["docker", "build", "-f", "agents/base/Dockerfile." + name,
            "-t", "tervory-agent1-" + name + ":cloud", "."], cwd=root, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=240)
        assert result.returncode == 0, result.stdout[-5000:]
    run_browser_boundary(render_public=True)
    with capsys.disabled():
        print("PASS: public /render respects robots.txt or returns page facts/text; browser internal-only, gateway outbound corridor")
