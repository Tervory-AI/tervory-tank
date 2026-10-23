"""Execute the Workspace authorization and upload boundary tests with Node."""

import subprocess
from pathlib import Path


def test_retailer_workspace_route_and_server_identity():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(["node", "tests/rig_feeds_admin_route.test.cjs"], cwd=root, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_rig_review_workflow_limits_minutes_to_rig_changes():
    import fnmatch
    import yaml
    root = Path(__file__).resolve().parents[1]
    workflow = yaml.safe_load((root / ".github/workflows/rig-admin-review.yml").read_text())
    events = workflow.get("on", workflow.get(True))
    assert set(events) == {"pull_request"}
    patterns = events["pull_request"]["paths"]
    matches = lambda path: any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)
    for path in ["workspace/app/rig/admin/retailer-admin.tsx", "workspace/lib/tank.ts", "tests/rig_feeds_admin_route.test.cjs", ".github/workflows/rig-admin-review.yml"]:
        assert matches(path)
    for path in ["workspace/app/tiger/page.tsx", "tank/main.py", "README.md", ".github/workflows/ci.yml"]:
        assert not matches(path)
    assert workflow["concurrency"]["cancel-in-progress"] is True
    assert "github.event.pull_request.number" in workflow["concurrency"]["group"]
    assert "github.workflow" in workflow["concurrency"]["group"]
    assert all(0 < job["timeout-minutes"] <= 10 for job in workflow["jobs"].values())
