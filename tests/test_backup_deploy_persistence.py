"""Dry-run real Compose deployment inputs without keys or live mutations."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]


def _without_dependency_waits(compose: dict) -> None:
    """Drop depends_on from the temporary copy. These tests check which services an
    ordinary `up` selects, not start order. With depends_on, a dry-run `up` still
    waits on each dependency's simulated container, and on a loaded CI runner Compose
    sometimes looked before that container was listed and stopped with
    "agent-roles is missing dependency postgres" (31 Oct, #486). No service here
    depends on a profiled service, so dropping depends_on cannot change selection;
    the loop checks that no dependency is profiled."""
    for name, service in compose["services"].items():
        for dependency in service.pop("depends_on", None) or []:
            assert not compose["services"][dependency].get("profiles"), (name, dependency)


@pytest.mark.parametrize("directory", ["deployment-artifact", "saved-coolify-compose"])
def test_boston_backup_survives_default_deployment_composition(tmp_path, directory):
    if shutil.which("docker") is None:
        pytest.skip("Docker Compose CLI is unavailable")
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    # Coolify consumes this metadata before handing the file to Compose.
    for service in compose["services"].values():
        service.pop("exclude_from_hc", None)
    # Corridor networks are created once on the live host (docker network create), so a
    # fresh runner has none and Compose stops at "declared as external, but could not be
    # found". This test is about which services an ordinary up selects, not networks.
    for network in (compose.get("networks") or {}).values():
        if network:
            network.pop("external", None)
    _without_dependency_waits(compose)
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
    first = subprocess.run(command, env=env, capture_output=True, text=True)
    assert first.returncode == 0, first.stdout + first.stderr
    expected = "Container backup-regression-r2-backup-1"
    assert expected in first.stdout + first.stderr, "ordinary redeploy drops the profiled backup"
    # A fresh resolution at the same path must retain the worker without a repair/profile flag.
    again = subprocess.run(command, env=env, capture_output=True, text=True)
    assert again.returncode == 0, again.stdout + again.stderr
    assert expected in again.stdout + again.stderr
    worker = compose["services"]["r2-backup"]
    assert worker["restart"] == "unless-stopped"
    assert worker["volumes"] == ["r2_backup_spool:/tmp"]
    assert worker["read_only"] is True
    assert worker["build"]["dockerfile"] == "jobs/train/Dockerfile.backup"
    assert worker["environment"]["R2_BACKUP_RECIPIENT"] == "${R2_BACKUP_RECIPIENT:-}"
    assert not any("identity" in name.lower() for name in worker["environment"])


# Coolify rewrites every service's env_file to its own .env on each deploy, so a
# backup worker that read a side file (.env.r2-backup) lost its R2 settings.
# Both workers must take every value from compose interpolation of Coolify env.
@pytest.mark.parametrize("path,name", [("docker-compose.yml", "r2-backup"),
                                       ("docker-compose.za.yml", "r2-backup-za")])
def test_backup_worker_needs_only_coolify_env(path, name):
    worker = yaml.safe_load((ROOT / path).read_text())["services"][name]
    assert not worker.get("profiles"), "a profile drops the worker on ordinary redeploys"
    assert worker["restart"] == "unless-stopped"
    assert not worker.get("env_file")
    for key in ("R2_ACCOUNT_ID", "R2_BACKUP_RECIPIENT", "DATABASE_URL", "QDRANT_API_KEY"):
        assert "${" in str(worker["environment"][key]), key
    assert "--nightly" in (worker.get("command") or ["--nightly"])
    assert "qdrant_configuration()" in worker["healthcheck"]["test"][-1]


def test_za_backup_survives_default_deployment_composition(tmp_path):
    if shutil.which("docker") is None:
        pytest.skip("Docker Compose CLI is unavailable")
    compose = yaml.safe_load((ROOT / "docker-compose.za.yml").read_text())
    for service in compose["services"].values():
        service.pop("exclude_from_hc", None)
    # Corridor networks are created once on the live host (docker network create), so a
    # fresh runner has none and Compose stops at "declared as external, but could not be
    # found". This test is about which services an ordinary up selects, not networks.
    for network in (compose.get("networks") or {}).values():
        if network:
            network.pop("external", None)
    _without_dependency_waits(compose)
    for service in compose["services"].values():
        service["env_file"] = [".env"]  # what Coolify writes on every deploy
    (tmp_path / ".env").write_text("")
    source = tmp_path / "docker-compose.yaml"
    source.write_text(yaml.safe_dump(compose))
    env = {name: os.environ[name] for name in ("PATH", "HOME") if name in os.environ}
    command = ["docker", "compose", "--project-name", "za-backup-regression", "--dry-run",
               "-f", str(source), "up", "-d", "--no-build", "--pull", "never", "--no-deps"]
    out = subprocess.run(command, env=env, capture_output=True, text=True, check=True, cwd=tmp_path)
    assert "Container za-backup-regression-r2-backup-za-1" in out.stdout + out.stderr
