"""Existing commit fingerprints cannot be expanded to cover a new PR finding."""
import importlib.util
from pathlib import Path
import subprocess

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / ".github/scripts/check_secret_baseline.py"
spec = importlib.util.spec_from_file_location("secret_baseline", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_baseline_accepts_only_old_fingerprints_without_raw_values(tmp_path):
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=tmp_path).decode().strip()
    git("init", "-q")
    git("config", "user.name", "Policy test")
    git("config", "user.email", "policy-test@localhost")
    git("commit", "--allow-empty", "-qm", "Existing repository")
    base = git("rev-parse", "HEAD")
    git("commit", "--allow-empty", "-qm", "Pull request")
    head = git("rev-parse", "HEAD")
    module.validate(tmp_path, base, [{"Fingerprint": f"{base}:file.txt:generic-api-key:1"}])
    with pytest.raises(ValueError, match="introduced"):
        module.validate(tmp_path, base, [{"Fingerprint": f"{head}:file.txt:generic-api-key:1"}])
    with pytest.raises(ValueError, match="fingerprints only"):
        module.validate(tmp_path, base, [{"Fingerprint": f"{base}:file.txt:generic-api-key:1", "Secret": ""}])


def test_fingerprint_filter_only_suppresses_the_exact_old_commit():
    old = {"Fingerprint": "a" * 40 + ":file.txt:generic-api-key:1"}
    new = {"Fingerprint": "b" * 40 + ":file.txt:generic-api-key:1"}
    assert module.new_findings([old], [old, new]) == [new]
    with pytest.raises(ValueError, match="Invalid scanner"):
        module.new_findings([old], [{"RuleID": "generic-api-key"}])


def test_scanner_failure_cannot_pass_as_an_empty_report(tmp_path, monkeypatch):
    monkeypatch.setattr(module.subprocess, "check_output", lambda *a, **kw: ("a" * 40).encode())
    def failed(args, **kwargs):
        assert "--redact" in args and "--ignore-gitleaks-allow" in args
        assert "--config" in args and "--gitleaks-ignore-path" in args
        assert "--exit-code" in args
        Path(args[args.index("--report-path") + 1]).write_text("[]")
        return subprocess.CompletedProcess(args, 1)
    monkeypatch.setattr(module.subprocess, "run", failed)
    with pytest.raises(ValueError, match="failed without findings"):
        module.scan(tmp_path, "gitleaks", "HEAD", [])
