"""Offline tests of CI policy around scanner output, not replacement scanners."""
import importlib.util
import io
import json
from contextlib import redirect_stdout
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

    def semgrep(self, severity="INFO", errors=None, code=0, findings=None):
        def fake_cli(args, allowed):
            self.assertIn(code, allowed)
            self.assertIn("--config", args)
            self.assertIn("auto", args)
            # Semgrep aborts before creating its report for auto config + metrics off.
            self.assertEqual(args[args.index("--metrics") + 1], "auto")
            self.assertEqual(args[args.index("--baseline-commit") + 1], "base")
            self.assertIn("--disable-nosem", args)
            results = [{"check_id": "test-rule", "path": "file.py", "start": {"line": 1},
                        "extra": {"severity": severity, "lines": "private source", "message": "private message"}}]
            report = {"results": results if findings is None else findings,
                      "errors": errors or []}
            Path(args[args.index("--output") + 1]).write_text(json.dumps(report))
            return code
        # Do not publish synthetic test annotations in the CI job.
        with patch.object(scan, "run", side_effect=fake_cli), redirect_stdout(io.StringIO()) as stdout:
            try:
                return scan.semgrep("base", self.root, self.output)
            finally:
                self.annotations = stdout.getvalue()

    def test_semgrep_only_high_findings_block(self):
        for severity in ("ERROR", "HIGH", "CRITICAL"):
            with self.subTest(severity=severity):
                self.assertTrue(self.semgrep(severity))
                self.assertEqual(self.annotations, f"::error file=file.py,line=1::test-rule {severity}\n")
        for severity in ("INFO", "WARNING", "LOW", "MEDIUM"):
            with self.subTest(severity=severity):
                self.assertFalse(self.semgrep(severity))
                self.assertEqual(self.annotations, f"::error file=file.py,line=1::test-rule {severity}\n")

    def test_semgrep_nonfatal_errors_are_counted_not_failed(self):
        errors = [
            {"type": ["PartialParsing", [{"tokens": "private source"}]], "level": "warn", "path": "fixture.html"},
            {"type": "Syntax error", "level": "error", "path": "other.html", "message": "private message"},
            {"type": "Timeout", "level": "warn", "path": "slow.py"},
        ]
        self.assertFalse(self.semgrep(errors=errors, code=3, findings=[]))
        report = self.read("semgrep.json")
        self.assertEqual(report["fatal_error_count"], 0)
        self.assertEqual(report["non_fatal_error_count"], 3)
        self.assertEqual(self.annotations, "::notice file=fixture.html::PartialParsing\n"
                         "::notice file=other.html::Syntax error\n::notice file=slow.py::Timeout\n")
        self.assertNotIn("private", json.dumps(report) + self.annotations)

    def test_semgrep_fatal_errors_still_block_and_annotate_findings(self):
        with self.assertRaises(RuntimeError):
            self.semgrep(severity="HIGH", errors=[{"type": "EngineError", "level": "fatal", "path": "file.py",
                                                   "message": "private source"}])
        self.assertEqual(self.read("semgrep.json")["fatal_error_count"], 1)
        self.assertEqual(self.annotations, "::error file=file.py,line=1::test-rule HIGH\n"
                         "::notice file=file.py::EngineError\n")

    def test_semgrep_native_fatal_error_type_blocks(self):
        with self.assertRaises(RuntimeError):
            self.semgrep(errors=[{"type": "Fatal error", "level": "error"}], code=2, findings=[])
        self.assertEqual(self.annotations, "::notice::Fatal error\n")

    def test_semgrep_rule_download_failure_blocks_without_printing_message(self):
        with self.assertRaises(RuntimeError):
            self.semgrep(errors=[{"type": "SemgrepError", "level": "error",
                                  "message": "Failed to download configuration from private location"}],
                         code=2, findings=[])
        self.assertEqual(self.annotations, "::notice::SemgrepError\n")
        self.assertNotIn("private", (self.output / "semgrep.json").read_text())
        self.assertEqual(self.read("semgrep.json")["fatal_error_count"], 1)

    def test_semgrep_unexplained_fatal_exit_cannot_pass(self):
        with self.assertRaises(RuntimeError):
            self.semgrep(code=2, findings=[])
        self.assertEqual(self.annotations, "::notice::SemgrepProcessError\n")

    def test_semgrep_nonfatal_notices_do_not_hide_high_findings(self):
        self.assertTrue(self.semgrep(severity="HIGH", errors=[{"type": "Timeout", "level": "warn", "path": "slow.py"}]))
        self.assertEqual(self.read("semgrep.json")["non_fatal_error_count"], 1)

    def test_semgrep_annotation_metadata_is_escaped(self):
        findings = [{"check_id": "rule%\r\n::notice::text", "path": "a,b:c%\r\n.py", "start": {"line": 2},
                     "extra": {"severity": "HIGH", "lines": "private source", "message": "private message"}}]
        self.assertTrue(self.semgrep(findings=findings))
        self.assertEqual(self.annotations, "::error file=a%2Cb%3Ac%25%0D%0A.py,line=2::rule%25%0D%0A::notice::text HIGH\n")

    def test_semgrep_missing_report_blocks_with_safe_notice(self):
        with patch.object(scan, "run", return_value=0), redirect_stdout(io.StringIO()) as stdout:
            with self.assertRaises(RuntimeError):
                scan.semgrep("base", self.root, self.output)
        self.assertEqual(stdout.getvalue(), f"::notice file={self.root}/semgrep.json::SemgrepReportMissingExit0\n")

    def test_semgrep_missing_launcher_identifies_executable(self):
        with patch.object(scan, "run", side_effect=FileNotFoundError(2, "not found", "semgrep")), \
                redirect_stdout(io.StringIO()) as stdout:
            with self.assertRaises(FileNotFoundError):
                scan.semgrep("base", self.root, self.output)
        self.assertEqual(stdout.getvalue(), "::notice file=semgrep::SemgrepExecutableMissing\n")

    def test_semgrep_artifact_has_no_source_or_messages(self):
        self.semgrep()
        self.assertNotIn("private", (self.output / "semgrep.json").read_text())
        self.assertNotIn("private", self.annotations)

    def test_gitleaks_uses_commits_and_keeps_no_secret_material(self):
        def fake_cli(args, allowed):
            self.assertEqual(allowed, (0, 1))
            self.assertEqual(args[args.index("--log-opts") + 1], "base..HEAD")
            self.assertIn("--redact=100", args)
            self.assertIn("--ignore-gitleaks-allow", args)
            self.assertEqual(Path(args[args.index("--config") + 1]), ROOT / ".gitleaks.toml")
            self.assertEqual(Path(args[args.index("--gitleaks-ignore-path") + 1]), ROOT / ".gitleaksignore")
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


class GitleaksAllowlistTests(unittest.TestCase):
    """Exercise the pinned free CLI; never print the dummy value or scan matches."""

    def setUp(self):
        lines = (ROOT / ".github/workflows/ci.yml").read_text().splitlines()
        self.dummy = next(line.split(":", 1)[1].strip() for line in lines
                          if line.strip().startswith("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY:"))

    def check_value(self, value, expected_code, expected_count):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "copy.txt").write_text("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=" + value + "\n")
            report = root / "report.json"
            result = subprocess.run([
                "gitleaks", "dir", str(root), "--no-banner", "--redact=100",
                "--config", str(ROOT / ".gitleaks.toml"),
                "--gitleaks-ignore-path", str(ROOT / ".gitleaksignore"),
                "--ignore-gitleaks-allow", "--report-format", "json", "--report-path", str(report),
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30, check=False)
            self.assertEqual(result.returncode, expected_code)
            self.assertEqual(len(json.loads(report.read_text())), expected_count)

    def test_new_copy_of_exact_ci_dummy_is_allowed(self):
        self.check_value(self.dummy, 0, 0)

    def test_other_value_with_same_clerk_prefix_still_blocks(self):
        offset = len("pk_test_")
        replacement = "A" if self.dummy[offset] != "A" else "B"
        self.check_value(self.dummy[:offset] + replacement + self.dummy[offset + 1:], 1, 1)

    def test_changed_ending_with_same_clerk_prefix_still_blocks(self):
        offset = len(self.dummy.rstrip("=")) - 1
        replacement = "A" if self.dummy[offset] != "A" else "B"
        self.check_value(self.dummy[:offset] + replacement + self.dummy[offset + 1:], 1, 1)


if __name__ == "__main__":
    unittest.main()
