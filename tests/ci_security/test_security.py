"""Offline tests of CI policy around scanner output, not replacement scanners."""
import ast
import copy
import importlib.util
import io
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from contextlib import redirect_stdout
from pathlib import Path
import shlex
import subprocess
import tempfile
import threading
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
        "vulnerabilities": [{"id": "TEST-ADVISORY", "details": "private advisory text",
                             "affected": [{"package": {"name": "test-package", "ecosystem": "PyPI"},
                                           "ranges": [{"type": "ECOSYSTEM", "events": [
                                               {"introduced": "0"}, {"fixed": "1.2"}]}]}]}],
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

    def capture_annotations(self, stdout):
        self.full_annotations = stdout.getvalue()
        lines = self.full_annotations.splitlines(keepends=True)
        self.summaries = [line for line in lines if line.startswith("::error::")]
        self.annotations = "".join(line for line in lines if not line.startswith("::error::"))
        self.assertLessEqual(len(self.summaries), 1)
        if self.summaries:
            self.assertEqual(lines[0], self.summaries[0])

    def osv(self, new, old=None):
        reports = []
        for index, payload in enumerate([new] if old is None else [new, old]):
            report = copy.deepcopy(payload)
            root = self.root / f"snapshot-{index}"
            root.mkdir(exist_ok=True)
            for source in report["results"] or []:
                path = root / "requirements.txt"
                path.write_text("# dependency snapshot\n" + "\n".join(
                    f"{item['package']['name']}=={item['package']['version']}"
                    for item in source["packages"]) + "\n")
                source["source"]["path"] = str(path)
            reports.append((report, ["requirements.txt"], root))
        # Synthetic test findings must not become annotations in the CI job.
        with patch.object(scan, "git", return_value="head"), \
                patch.object(scan, "osv_report", side_effect=reports), \
                redirect_stdout(io.StringIO()) as stdout:
            try:
                return scan.osv("base" if old is not None else None, self.root, self.output)
            finally:
                self.capture_annotations(stdout)

    def test_existing_vulnerability_is_not_new(self):
        self.assertFalse(self.osv(osv_payload(), osv_payload()))
        self.assertEqual(self.read("osv.json")["findings"], [])
        self.assertEqual(self.annotations, "")
        self.assertEqual(self.summaries, [])

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

    def test_osv_annotation_has_only_pin_and_advisory_metadata(self):
        self.assertTrue(self.osv(osv_payload(), {"results": []}))
        self.assertEqual(self.annotations,
                         "::error file=requirements.txt,line=2::test-package 1.0 TEST-ADVISORY fixed-in 1.2\n")
        self.assertEqual(self.summaries, ["::error::OSV%0Atest-package 1.0 (requirements.txt) -> 1.2, 1 advisories\n"])
        report = self.read("osv.json")
        self.assertEqual(report["findings"][0]["line"], 2)
        self.assertEqual(report["findings"][0]["fixed_versions"], ["1.2"])
        self.assertNotIn("private", json.dumps(report) + self.full_annotations)

    def test_osv_fixes_are_scoped_to_package_and_ecosystem(self):
        report = osv_payload()
        vuln = report["results"][0]["packages"][0]["vulnerabilities"][0]
        vuln["affected"].extend([
            {"package": {"name": "Test_Package", "ecosystem": "PyPI"}, "ranges": [
                {"type": "ECOSYSTEM", "events": [{"fixed": "2.1"}, {"fixed": "1.2"}]}]},
            {"package": {"name": "unrelated", "ecosystem": "PyPI"}, "ranges": [
                {"type": "ECOSYSTEM", "events": [{"fixed": "99"}]}]},
            {"package": {"name": "test-package", "ecosystem": "npm"}, "ranges": [
                {"type": "SEMVER", "events": [{"fixed": "88"}]}]},
            {"package": {"name": "test-package", "ecosystem": "PyPI"}, "ranges": [
                {"type": "GIT", "events": [{"fixed": "commit-not-version"}]}]},
        ])
        self.assertTrue(self.osv(report))
        self.assertEqual(self.read("osv.json")["findings"][0]["fixed_versions"], ["1.2", "2.1"])
        self.assertTrue(self.annotations.endswith("fixed-in 1.2,2.1\n"))

    def test_osv_unfixed_advisory_still_fails(self):
        report = osv_payload()
        report["results"][0]["packages"][0]["vulnerabilities"][0]["affected"] = []
        self.assertTrue(self.osv(report))
        self.assertTrue(self.annotations.endswith("fixed-in unavailable\n"))

    def test_python_pin_location_handles_extras_hashes_and_canonical_names(self):
        path = self.root / "requirements.lock"
        path.write_text("# lock\nOther==1.0\nTest_Package[extra] == 1.1 ; python_version >= '3.12'\n"
                        "    --hash=sha256:unused\n")
        self.assertEqual(scan.dependency_line(path, {
            "name": "test-package", "version": "1.1", "ecosystem": "PyPI"}), 3)

    def test_npm_pin_location_matches_version_nested_scope_and_alias(self):
        path = self.root / "package-lock.json"
        for lock in [
            {"packages": {"node_modules/@scope/name": {"version": "1.0"},
                          "node_modules/parent/node_modules/@scope/name": {"version": "2.0"}}},
            {"dependencies": {"parent": {"version": "1.0", "dependencies": {
                "@scope/name": {"version": "2.0"}}}}},
            {"packages": {"node_modules/alias": {"name": "@scope/name", "version": "2.0"}}},
        ]:
            with self.subTest(lock=lock):
                path.write_text(json.dumps(lock, indent=2))
                expected = next(number for number, line in enumerate(path.read_text().splitlines(), 1)
                                if ('"@scope/name": {' in line or
                                    '"node_modules/parent/node_modules/@scope/name": {' in line or
                                    '"node_modules/alias": {' in line))
                self.assertEqual(scan.dependency_line(path, {
                    "name": "@scope/name", "version": "2.0", "ecosystem": "npm"}), expected)

    def test_osv_advisory_metadata_cannot_inject_workflow_commands(self):
        report = osv_payload()
        vuln = report["results"][0]["packages"][0]["vulnerabilities"][0]
        vuln["id"] = "TEST%\r\n::notice::injected"
        self.assertTrue(self.osv(report))
        self.assertEqual(self.annotations.count("\n"), 1)
        self.assertIn("TEST%25%0D%0A::notice::injected", self.annotations)

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
                self.capture_annotations(stdout)

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
        self.assertNotIn("private", json.dumps(report) + self.full_annotations)

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
        self.assertNotIn("private", self.full_annotations)

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
        with patch.object(scan, "run", side_effect=fake_cli), redirect_stdout(io.StringIO()) as stdout:
            self.assertTrue(scan.leaks("base", self.root, self.output))
        self.capture_annotations(stdout)
        self.assertEqual(self.summaries, ["::error::Gitleaks%0Atest-rule: probe.txt:1\n"])
        self.assertEqual(self.annotations, "::error file=probe.txt,line=1::test-rule\n")
        self.assertNotIn("private", self.full_annotations)
        self.assertNotIn("private", (self.output / "gitleaks.json").read_text())

    def test_semgrep_summary_keeps_all_locations_beyond_ten_and_deduplicates(self):
        findings = [{"check_id": "one-rule", "path": f"file-{i:02}.py", "start": {"line": i + 1},
                     "extra": {"severity": "HIGH", "lines": "private source"}} for i in range(20)]
        self.assertTrue(self.semgrep(findings=findings + findings))
        expected = ", ".join(f"file-{i:02}.py:{i + 1}" for i in range(20))
        self.assertEqual(self.summaries, [f"::error::Semgrep%0Aone-rule: {expected}\n"])
        self.assertEqual(len(self.annotations.splitlines()), 40)
        self.assertNotIn("private", self.full_annotations)

    def test_osv_summary_counts_distinct_advisories_and_keeps_each_lock(self):
        rows = [{"package": "package", "version": "1.0", "ecosystem": "PyPI", "path": path,
                 "id": f"ADVISORY-{i}", "fixed_versions": ["2.0"]} for i in range(20)
                for path in ("first.lock", "second.lock")]
        with redirect_stdout(io.StringIO()) as stdout:
            scan.finding_summary("OSV", rows + rows)
        self.assertEqual(stdout.getvalue(), "::error::OSV%0A"
                         "package 1.0 (first.lock) -> 2.0, 20 advisories%0A"
                         "package 1.0 (second.lock) -> 2.0, 20 advisories\n")

    def test_gitleaks_summary_deduplicates_history_without_values(self):
        rows = [{"RuleID": "rule", "File": f"file-{i:02}.txt", "StartLine": i + 1,
                 "Commit": commit, "Secret": "private source", "Match": "private match"}
                for i in range(20) for commit in ("old", "new")]
        with redirect_stdout(io.StringIO()) as stdout:
            scan.finding_summary("Gitleaks", rows)
        expected = "%0A".join(f"rule: file-{i:02}.txt:{i + 1}" for i in range(20))
        self.assertEqual(stdout.getvalue(), f"::error::Gitleaks%0A{expected}\n")
        self.assertNotIn("private", stdout.getvalue())

    def test_empty_summaries_do_not_emit_errors(self):
        with redirect_stdout(io.StringIO()) as stdout:
            for tool in ("Gitleaks", "Semgrep", "OSV"):
                scan.finding_summary(tool, [])
        self.assertEqual(stdout.getvalue(), "")

    def test_summary_metadata_is_escaped_as_one_annotation(self):
        with redirect_stdout(io.StringIO()) as stdout:
            scan.finding_summary("Semgrep", [{"rule": "rule%\r\n::error::injected",
                                              "path": "path\n.py", "line": 2}])
        self.assertEqual(stdout.getvalue(),
                         "::error::Semgrep%0Arule%25%0D%0A::error::injected: path%0A.py:2\n")

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


class FixedHTTPSBaseTests(unittest.TestCase):
    def api(self, filename, base):
        path = ROOT / ".github/scripts" / filename
        tree = ast.parse(path.read_text())
        # room_setup executes mutations at module scope. Load only imports and
        # the API function, never room creation, secret generation or deployment.
        tree.body = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))
                     or isinstance(node, ast.FunctionDef) and node.name == "api"]
        namespace = {"URL": base, "TOKEN": ""}
        exec(compile(tree, str(path), "exec"), namespace)
        return namespace["api"], namespace["urllib"].request

    def watchdog(self):
        name = "security_test_watchdog"
        spec = importlib.util.spec_from_file_location(name, ROOT / ".github/scripts/watchdog.py")
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {name: module}):
            spec.loader.exec_module(module)
        return module

    def test_coolify_rejects_nonfixed_origins_before_network(self):
        invalid = ("http://coolify.tervory.com", "https://coolify.tervory.com.bad.invalid",
                   "https://coolify.tervory.com@bad.invalid", "file:///tmp/config",
                   "https://coolify.tervory.com/other", "https://coolify.tervory.com?other",
                   "https://coolify.tervory.com#other", "https://coolify.tervory.com:444")
        watchdog = self.watchdog()
        for base in invalid:
            for filename in ("deploy_changed.py", "room_setup.py"):
                with self.subTest(file=filename, base=base):
                    api, request = self.api(filename, base + ("/api/v1" if filename == "room_setup.py" else ""))
                    with patch.object(request, "urlopen") as opener:
                        with self.assertRaises(ValueError):
                            api("GET", "/applications")
                        opener.assert_not_called()
            with patch.dict(os.environ, {"COOLIFY_URL": base, "COOLIFY_TOKEN": "COOLIFY_TOKEN"}), \
                    patch.object(watchdog.urllib.request, "urlopen") as opener:
                self.assertEqual(watchdog.coolify_results()[0].state, "down")
                opener.assert_not_called()

    def test_allowed_coolify_requests_use_literal_https_base(self):
        class Response:
            status = 200
            def read(self):
                return b'[{"name":"app","status":"running:healthy","uuid":"app"}]'
            def __enter__(self):
                return self
            def __exit__(self, *_args):
                pass

        def open_local(request, **_kwargs):
            self.assertEqual(request.full_url, "https://coolify.tervory.com/api/v1/applications")
            return Response()

        for filename in ("deploy_changed.py", "room_setup.py"):
            api, request = self.api(filename, "https://coolify.tervory.com" +
                                    ("/api/v1" if filename == "room_setup.py" else ""))
            with patch.object(request, "urlopen", side_effect=open_local):
                self.assertEqual(api("GET", "/applications")[0], 200)
        watchdog = self.watchdog()
        with patch.dict(os.environ, {"COOLIFY_URL": "https://coolify.tervory.com/", "COOLIFY_TOKEN": "COOLIFY_TOKEN"}), \
                patch.object(watchdog.urllib.request, "urlopen", side_effect=open_local):
            self.assertTrue(all(row.state == "ok" for row in watchdog.coolify_results()))


class SecurityDownloadTests(unittest.TestCase):
    """Exercise the installer's real curl flags against a local failing server."""

    def downloads(self, recover):
        script = (ROOT / ".github/scripts/install-security-tools.sh").read_text()
        commands = [shlex.split(line) for line in script.replace("\\\n", "").splitlines()
                    if line.startswith("curl ")]
        self.assertEqual(len(commands), 2)
        attempts = []
        payload = b"local test download"

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                attempts.append(self.path)
                # 404 is not one of curl's default retryable responses.
                self.send_response(200 if recover and len(attempts) == 4 else 404)
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *_args):
                pass

        with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server, \
                tempfile.TemporaryDirectory() as directory:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                for index, command in enumerate(commands):
                    with self.subTest(download=index, recover=recover):
                        attempts.clear()
                        urls = [i for i, value in enumerate(command) if value.startswith("https://")]
                        self.assertEqual(len(urls), 1)
                        # No release traffic: retain actual options but use only our loopback server.
                        command[urls[0]] = f"http://127.0.0.1:{server.server_port}/artifact"
                        output = Path(directory) / f"download-{index}"
                        command[command.index("--output") + 1] = str(output)
                        result = subprocess.run(command, capture_output=True, timeout=15, check=False)
                        self.assertEqual(len(attempts), 4)  # initial attempt plus three retries
                        self.assertEqual(result.returncode, 0 if recover else 22)
                        if recover:
                            self.assertEqual(output.read_bytes(), payload)
            finally:
                server.shutdown()
                thread.join(timeout=5)

    def test_download_recovers_on_third_retry(self):
        self.downloads(recover=True)

    def test_download_stops_after_third_retry(self):
        self.downloads(recover=False)


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
