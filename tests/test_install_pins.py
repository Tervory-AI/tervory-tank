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
    "pip --timeout 30 install -r requirements.txt",
    "pip install --require-hashes -r requirements.txt",
    "pip install --require-hashes -r $LOCK",
    "npm install --include=dev --no-audit",
    'npm --prefix "$RUNNER_TEMP/browser" install esbuild@0.28.2',
    "npm ci || npm install --no-package-lock",
    "npm ci",
    "npm ci --ignore-scripts=false",
])
def test_mutable_install_is_rejected(command):
    assert pins.install_errors(command)


@pytest.mark.parametrize("command", [
    "python -m pip install --require-hashes -r tank/requirements.lock -r tank/requirements-dev.lock",
    "pip install --require-hashes --requirement=requirements.lock",
    "pip install --require-hashes -rrequirements.lock",
    "RUN pip install \\\n        --require-hashes -r requirements.lock",
    "npm --prefix workspace ci --ignore-scripts --no-audit --no-fund",
    "RUN apk add --no-cache curl=8.14.1-r2 git=2.49.0-r0",
    "apt-get install --simulate curl",
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


def test_source_archive_locks_require_hashes_and_reject_editable_directories():
    for location in ("file:///opt/locked-sources/cumesh.tar", "https://example.org/source.tar.gz"):
        requirement = "cumesh @ " + location
        assert pins.lock_errors(requirement)
        assert not pins.lock_errors(requirement + " --hash=sha256:" + "a" * 64)
    for location in ("file:///opt/cumesh", "git+https://example.org/source.git", "https://example.org/source.tar.gz?download=1"):
        assert pins.lock_errors("cumesh @ " + location + " --hash=sha256:" + "a" * 64)


def test_secrets_workflow_covers_docs_only_pull_requests():
    import yaml

    workflow = yaml.safe_load((SCRIPT.parents[2] / ".github/workflows/secrets.yml").read_text())
    triggers = workflow.get("on", workflow.get(True))
    assert "pull_request" in triggers
    assert not triggers["pull_request"]
    job = workflow["jobs"]["gitleaks"]
    assert "if" not in job and not job.get("continue-on-error")
    scan = next(step for step in job["steps"] if step.get("name") == "Gitleaks")
    assert "if" not in scan and not scan.get("continue-on-error")
    assert "sha256sum --check --status" in scan["run"]
    assert "check_secret_baseline.py" in scan["run"] and "--gitleaks" in scan["run"]


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
    workflow.write_text("steps:\n  - run: npm ci --ignore-scripts\n")
    assert not pins.check(tmp_path, paths)


def test_diff_gate_rejects_new_violation_and_duplicate_but_not_line_shift(tmp_path):
    import subprocess

    def git(*args):
        return subprocess.check_output(["git", *args], cwd=tmp_path)

    git("init", "-q")
    git("config", "user.name", "Policy test")
    git("config", "user.email", "policy-test@localhost")
    path = tmp_path / "Dockerfile"
    path.write_text("FROM python:3.12\nRUN pip install fastapi==0.133.1\n")
    git("add", ".")
    git("commit", "-qm", "Existing migration debt")
    path.write_text("# a shifted comment\n" + path.read_text())
    assert pins.new_errors(tmp_path, [path], "HEAD") == ([], 2)
    path.write_text(path.read_text() + "RUN pip install fastapi==0.133.1\n")
    errors, inherited = pins.new_errors(tmp_path, [path], "HEAD")
    assert len(errors) == 1 and inherited == 2
    path.write_text("FROM python:3.13\nRUN pip install fastapi==0.133.1\n")
    errors, inherited = pins.new_errors(tmp_path, [path], "HEAD")
    assert len(errors) == 1 and "Docker base" in errors[0] and inherited == 1


def test_nested_template_workflow_is_enforced(tmp_path):
    path = tmp_path / "template/.github/workflows/ci.yml"
    path.parent.mkdir(parents=True)
    path.write_text("steps:\n  - run: pip install pytest\n")
    assert pins.policy_file(path.relative_to(tmp_path))
    assert any("Python install" in error for error in pins.check(tmp_path, [path]))


def test_nonexistent_lock_is_rejected_and_copy_rename_is_resolved(tmp_path):
    path = tmp_path / "Dockerfile"
    path.write_text("FROM scratch\nRUN pip install --require-hashes -r /tmp/runtime.lock\n")
    assert any("not committed" in error for error in pins.check(tmp_path, [path]))
    lock = tmp_path / "requirements.lock"
    lock.write_text("httpx==0.28.1 --hash=sha256:" + "a" * 64 + "\n")
    path.write_text("FROM scratch\nCOPY requirements.lock /tmp/runtime.lock\nRUN pip install --require-hashes -r /tmp/runtime.lock\n")
    assert not pins.check(tmp_path, [path, lock])
