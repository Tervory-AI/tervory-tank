"""Offline tests of CI policy around scanner output, not replacement scanners."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("security_scan", ROOT / ".github/scripts/security_scan.py")
scan = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scan)


def osv_payload(version="1.0", score="8.1"):
    # Tool-output fixtures stay in offline tests and are never shown on a live page.
    return {"results": [{"source": {"path": "/snapshot/requirements.txt"}, "packages": [{
        "package": {"ecosystem": "PyPI", "name": "test-package", "version": version},
        "vulnerabilities": [{"id": "TEST-ADVISORY"}],
        "groups": [{"ids": ["TEST-ADVISORY"], "max_severity": score}],
    }]}]}


class SecurityPolicyTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.output = self.root / "results"
        self.output.mkdir()

    def read(self, name):
        return json.loads((self.output / name).read_text())

    def osv(self, new, old=None):
        reports = [(new, ["requirements.txt"], Path("/snapshot"))]
        if old is not None:
            reports.append((old, ["requirements.txt"], Path("/snapshot")))
        with patch.object(scan, "git", return_value="head"), \
                patch.object(scan, "osv_report", side_effect=reports):
            return scan.osv("base" if old is not None else None, self.root, self.output)

    def test_existing_vulnerability_is_not_new(self):
        self.assertFalse(self.osv(osv_payload(), osv_payload()))
        self.assertEqual(self.read("osv.json")["findings"], [])

    def test_different_vulnerable_version_blocks_same_advisory(self):
        self.assertTrue(self.osv(osv_payload("1.1"), osv_payload("1.0")))

    def test_new_low_vulnerability_blocks_pull_request(self):
        self.assertTrue(self.osv(osv_payload(score="2.0"), {"results": []}))

    def test_weekly_blocks_high_but_not_low(self):
        self.assertTrue(self.osv(osv_payload(score="7.0")))
        self.assertFalse(self.osv(osv_payload(score="6.9")))

    def test_weekly_unknown_severity_requires_review(self):
        self.assertTrue(self.osv(osv_payload(score="")))

    def test_fixed_version_passes(self):
        self.assertFalse(self.osv({"results": []}, osv_payload()))

    def test_lock_discovery_includes_nested_and_nonstandard_requirements(self):
        paths = b"tank/requirements-dev.txt\0site/package-lock.json\0a/gpu/requirements.lock\0a/meshroom-requirements.lock\0README.md\0package.json\0"
        with patch.object(scan.subprocess, "check_output", return_value=paths):
            self.assertEqual(len(scan.lockfiles("head")), 4)

    def test_osv_errors_do_not_become_empty_clean_reports(self):
        with patch.object(scan.subprocess, "run", return_value=subprocess.CompletedProcess([], 127)):
            with self.assertRaises(RuntimeError):
                scan.run(["osv-scanner"], (0, 1))

    def test_missing_locks_fail_closed(self):
        with patch.object(scan, "lockfiles", return_value=[]):
            with self.assertRaises(ValueError):
                scan.osv_report("head", self.root)

    def semgrep(self, severity="INFO", errors=None):
        def fake_cli(args):
            self.assertIn("--config", args)
            self.assertIn("auto", args)
            self.assertEqual(args[args.index("--baseline-commit") + 1], "base")
            self.assertIn("--disable-nosem", args)
            report = {"results": [{"check_id": "test-rule", "path": "file.py", "start": {"line": 1},
                                  "extra": {"severity": severity, "lines": "private source", "message": "private message"}}],
                      "errors": errors or []}
            Path(args[args.index("--output") + 1]).write_text(json.dumps(report))
            return 0
        with patch.object(scan, "run", side_effect=fake_cli):
            return scan.semgrep("base", self.root, self.output)

    def test_semgrep_only_high_findings_block(self):
        for severity in ("ERROR", "HIGH", "CRITICAL"):
            with self.subTest(severity=severity):
                self.assertTrue(self.semgrep(severity))
        for severity in ("INFO", "WARNING", "LOW", "MEDIUM"):
            with self.subTest(severity=severity):
                self.assertFalse(self.semgrep(severity))

    def test_semgrep_errors_block(self):
        self.assertTrue(self.semgrep(errors=[{"message": "private source"}]))

    def test_semgrep_artifact_has_no_source_or_messages(self):
        self.semgrep()
        self.assertNotIn("private", (self.output / "semgrep.json").read_text())

    def test_gitleaks_uses_commits_and_keeps_no_secret_material(self):
        def fake_cli(args, allowed):
            self.assertEqual(allowed, (0, 1))
            self.assertEqual(args[args.index("--log-opts") + 1], "base..HEAD")
            self.assertIn("--redact=100", args)
            self.assertIn("--ignore-gitleaks-allow", args)
            Path(args[args.index("--report-path") + 1]).write_text(json.dumps([{
                "RuleID": "test-rule", "File": "probe.txt", "StartLine": 1, "Commit": "head",
                "Secret": "private value", "Match": "private match", "Message": "private message",
            }]))
            return 1
        with patch.object(scan, "run", side_effect=fake_cli):
            self.assertTrue(scan.leaks("base", self.root, self.output))
        self.assertNotIn("private", (self.output / "gitleaks.json").read_text())

    def test_missing_report_fails(self):
        with patch.object(scan, "run", return_value=0):
            with self.assertRaises(FileNotFoundError):
                scan.leaks(None, self.root, self.output)

    def test_weekly_gitleaks_covers_history(self):
        def fake_cli(args, allowed):
            self.assertEqual(args[args.index("--log-opts") + 1], "HEAD")
            Path(args[args.index("--report-path") + 1]).write_text("[]")
            return 0
        with patch.object(scan, "run", side_effect=fake_cli):
            self.assertFalse(scan.leaks(None, self.root, self.output))


if __name__ == "__main__":
    unittest.main()
