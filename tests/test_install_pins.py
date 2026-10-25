"""Regression coverage for mutable installs reaching CI or image builds."""

import base64
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / ".github/scripts/check_install_pins.py"
SPEC = importlib.util.spec_from_file_location("check_install_pins", SCRIPT)
assert SPEC and SPEC.loader
pins = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pins)


@pytest.mark.parametrize("command", [
    "pip install --upgrade pip",
    "python -m pip install -r tank/requirements.txt",
    "pip3 --no-cache-dir install fastapi==0.133.1",
    "pip install --require-hashes -r requirements.txt",
    "pip install --require-hashes -r $LOCK",
    "npm install --include=dev --no-audit",
    'npm --prefix "$RUNNER_TEMP/browser" install esbuild@0.28.2',
    "npm ci || npm install --no-package-lock",
    "RUN apt-get update && apt-get install -y curl",
    "RUN apk add --no-cache curl=8.14.1-r2 git",
    "curl -fsSL https://example.org/install.sh | bash",
])
def test_mutable_install_is_rejected(command):
    assert pins.install_errors(command)


@pytest.mark.parametrize("command", [
    "python -m pip install --require-hashes -r tank/requirements.lock -r tank/requirements-dev.lock",
    "pip install --require-hashes --requirement=requirements.lock",
    "pip install --require-hashes -rrequirements.lock",
    "RUN pip install \\\n        --require-hashes -r requirements.lock",
    "npm --prefix workspace ci --no-audit --no-fund",
    "RUN apk add --no-cache curl=8.14.1-r2 git=2.49.0-r0",
    "# npm install is not an executable command",
])
def test_locked_install_is_accepted(command):
    assert not pins.install_errors(command)


def test_external_bases_need_digest_but_internal_stages_do_not():
    digest = "a" * 64
    assert not pins.docker_errors(
        f"FROM --platform=linux/amd64 python:3.12-slim@sha256:{digest} AS runtime\n"
        "FROM runtime AS test\nFROM scratch AS export\n"
    )
    assert pins.docker_errors("FROM python:3.12-slim AS runtime\nFROM runtime AS test\n") == [
        (1, "External Docker base image must be pinned by @sha256")
    ]
    assert pins.docker_errors("FROM python@sha256:short\n")


def test_lock_rejects_unpinned_transitive_dependency_and_missing_hash():
    hashed = "fastapi==0.133.1 \\\n    --hash=sha256:" + "a" * 64 + "\n"
    assert not pins.lock_errors(hashed + "    # via requirements.txt\n")
    assert pins.lock_errors(hashed + "starlette>=1.3.1\n")
    assert pins.lock_errors("fastapi==0.133.1\n")
    assert pins.lock_errors("fastapi==0.* --hash=sha256:" + "a" * 64)
    assert pins.lock_errors("fastapi==0.133.1 --hash=sha256:short")


def node_manifests():
    package = {"dependencies": {"postcss": "8.5.23"}}
    lock = {
        "lockfileVersion": 3,
        "packages": {
            "": package,
            "node_modules/postcss": {
                "version": "8.5.23",
                "integrity": "sha512-" + base64.b64encode(bytes(64)).decode(),
            },
        },
    }
    return package, lock


def test_node_requires_transitive_integrity_and_manifest_agreement():
    package, lock = node_manifests()
    assert not pins.node_lock_errors(package, lock)
    assert pins.node_lock_errors({"dependencies": {"postcss": "8.4.31"}}, lock)
    del lock["packages"]["node_modules/postcss"]["integrity"]
    assert pins.node_lock_errors(package, lock)


def test_repository_scan_catches_missing_locks_and_install_in_workflow(tmp_path):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("fastapi==0.133.1\n")
    package_path = tmp_path / "package.json"
    package, lock = node_manifests()
    package_path.write_text(json.dumps(package))
    workflow = tmp_path / ".github/workflows/ci.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("steps:\n  - run: npm ci || npm install\n")
    paths = [requirements, package_path, workflow]
    errors = pins.check(tmp_path, paths)
    assert any("requirements.txt: missing" in error for error in errors)
    assert any("package.json: missing" in error for error in errors)
    assert any("ci.yml:2:" in error for error in errors)
    requirements.with_suffix(".lock").write_text("fastapi==0.133.1 --hash=sha256:" + "a" * 64)
    package_path.with_name("package-lock.json").write_text(json.dumps(lock))
    workflow.write_text("steps:\n  - run: npm ci\n")
    assert not pins.check(tmp_path, paths)
