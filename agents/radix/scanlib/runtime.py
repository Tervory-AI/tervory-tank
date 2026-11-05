"""Coverage checks for room scans, without changing released skill engines."""
from __future__ import annotations

import json
import sqlite3
import subprocess
from pathlib import Path

from scanlib import dependencies, secrets, static
from scanlib.osv_contract import FLOORS


def secret_scan(root: Path) -> tuple[list[dict], list[str], bool]:
    # Always retain native redaction and known findings if the full tool fails.
    fallback, hidden = secrets.scan_files(secrets.iter_text_files(root))
    binary, config = secrets.gitleaks_bin(), secrets._config_path()
    if not binary or not config:
        return fallback, hidden, False
    report = root.parent / "gitleaks-report.json"
    try:
        report.unlink(missing_ok=True)
        completed = subprocess.run([
            binary, "detect", "--no-git", "--no-banner", "--redact",
            "--log-level", "error", "--source", str(root), "--config", str(config),
            "--report-format", "json", "--report-path", str(report),
        ], capture_output=True, timeout=60, env=secrets._tool_env(), check=False)
        if completed.returncode not in (0, 1):
            return fallback, hidden, False
        parsed = json.loads(report.read_text(encoding="utf-8"))
        if not isinstance(parsed, list) or any(
            not isinstance(item, dict) or not item.get("RuleID") or not item.get("File")
            or type(item.get("StartLine")) is not int or item["StartLine"] < 1
            for item in parsed
        ):
            return fallback, hidden, False
        findings, reported = secrets._from_gitleaks(parsed, root)
        # Exit 1 means leaks found; an empty report cannot substantiate that run.
        return findings, hidden + reported, completed.returncode == 0 or bool(parsed)
    except (OSError, ValueError, TypeError, subprocess.TimeoutExpired):
        return fallback, hidden, False
    finally:
        report.unlink(missing_ok=True)


def static_scan(root: Path) -> tuple[list[dict], bool]:
    fallback = static.scan_files(static.iter_source_files(root))
    binary, rules = static.semgrep_bin(), static._rules_path()
    if not binary or not rules:
        return fallback, False
    try:
        completed = subprocess.run([
            binary, "scan", "--config", str(rules), "--json", "--quiet",
            "--metrics=off", "--disable-version-check", "--no-git-ignore", str(root),
        ], capture_output=True, timeout=60, env=static._tool_env(), check=False)
        if completed.returncode not in (0, 1):
            return fallback, False
        report = json.loads(completed.stdout)
        if not isinstance(report, dict) or not isinstance(report.get("results"), list):
            return fallback, False
        if any(not isinstance(item, dict) or not item.get("check_id") or not item.get("path")
               or not isinstance(item.get("start"), dict)
               or type(item["start"].get("line")) is not int or item["start"]["line"] < 1
               or not isinstance(item.get("extra"), dict) for item in report["results"]):
            return fallback, False
        findings = static._from_semgrep(report, root)
        complete = report.get("errors") == []
        if not complete:
            findings += [item for item in fallback if item not in findings]
        return findings, complete
    except (OSError, ValueError, TypeError, subprocess.TimeoutExpired):
        return fallback, False


def dependency_scan(root: Path) -> tuple[list[dict], bool]:
    """Fixture advisories alone never certify coverage of real dependencies."""
    coverage = set()
    try:
        for path in dependencies.databases():
            conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
            try:
                for ecosystem, records, rows in conn.execute("SELECT ecosystem,records,rows FROM meta"):
                    ecosystem = str(ecosystem).casefold()
                    if ecosystem in FLOORS and records >= FLOORS[ecosystem] and rows > 0:
                        # Validate the queried schema too, including for empty handovers.
                        conn.execute("SELECT eco,ecosystem,package,advisory,aliases,severity,ranges,versions "
                                     "FROM advisories LIMIT 1")
                        actual = conn.execute("SELECT count(*) FROM advisories WHERE eco=?", (ecosystem,)).fetchone()[0]
                        if actual == rows:
                            coverage.add(ecosystem)
            finally:
                conn.close()
        return dependencies.scan_tree(root), coverage == set(FLOORS)
    except (OSError, sqlite3.Error, ValueError, TypeError):
        return [], False
