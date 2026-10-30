"""Dry-run real Compose deployment inputs without keys or live mutations."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("directory", ["deployment-artifact", "saved-coolify-compose"])
def test_boston_backup_survives_default_deployment_composition(tmp_path, directory):
    if shutil.which("docker") is None:
        pytest.skip("Docker Compose CLI is unavailable")
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    # Coolify consumes this metadata before handing the file to Compose.
    for service in compose["services"].values():
        service.pop("exclude_from_hc", None)
    target = tmp_path / directory
    target.mkdir()
    source = target / "docker-compose.yaml"
    source.write_text(yaml.safe_dump(compose))
    # No inherited COMPOSE_PROFILES or env file can hide the default-off defect.
    env = {name: os.environ[name] for name in ("PATH", "HOME") if name in os.environ}
    # config --services includes disabled profiles too; only up exercises selection.
    # --no-deps avoids unrelated services' runtime dependency waits in dry-run.
    command = ["docker", "compose", "--project-name", "backup-regression", "--dry-run",
               "-f", str(source), "up", "-d", "--no-build", "--pull", "never", "--no-deps"]
    first = subprocess.run(command, env=env, capture_output=True, text=True, check=True)
    expected = "Container backup-regression-r2-backup-1"
    assert expected in first.stdout + first.stderr, "ordinary redeploy drops the profiled backup"
    # A fresh resolution at the same path must retain the worker without a repair/profile flag.
    again = subprocess.run(command, env=env, capture_output=True, text=True, check=True)
    assert expected in again.stdout + again.stderr
    worker = compose["services"]["r2-backup"]
    assert worker["restart"] == "unless-stopped"
    assert worker["volumes"] == ["r2_backup_spool:/tmp"]
    assert worker["read_only"] is True
    assert worker["build"]["dockerfile"] == "jobs/train/Dockerfile.backup"
    assert worker["environment"]["R2_BACKUP_RECIPIENT"] == "${R2_BACKUP_RECIPIENT:-}"
    assert not any("identity" in name.lower() for name in worker["environment"])
    za = yaml.safe_load((ROOT / "docker-compose.za.yml").read_text())
    assert za["services"]["r2-backup-za"]["profiles"] == ["r2-backup-za"]
