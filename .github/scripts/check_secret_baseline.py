"""A baseline may suppress only fingerprints from commits already in the PR base."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def validate(root: Path, base: str, entries: list[dict]) -> None:
    base = subprocess.check_output(["git", "rev-parse", "--verify", base + "^{commit}"], cwd=root).decode().strip()
    for entry in entries:
        if set(entry) != {"Fingerprint"}:
            raise ValueError("The baseline must contain fingerprints only, never secret text.")
        fingerprint = entry["Fingerprint"]
        if not isinstance(fingerprint, str) or not re.fullmatch(r"[a-f0-9]{40}:.+:[\w-]+:\d+", fingerprint):
            raise ValueError("Invalid baseline fingerprint.")
        commit = fingerprint.split(":", 1)[0]
        if subprocess.run(["git", "merge-base", "--is-ancestor", commit, base], cwd=root,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
            raise ValueError("Baseline cannot suppress a finding introduced by this PR.")


def new_findings(entries: list[dict], findings: list[dict]) -> list[dict]:
    allowed = {entry["Fingerprint"] for entry in entries}
    if not isinstance(findings, list) or any(not isinstance(row, dict) or not row.get("Fingerprint") for row in findings):
        raise ValueError("Invalid scanner report.")
    return [row for row in findings if row["Fingerprint"] not in allowed]


def scan(root: Path, binary: str, head: str, entries: list[dict]) -> list[dict]:
    head = subprocess.check_output(["git", "rev-parse", "--verify", head + "^{commit}"], cwd=root).decode().strip()
    with tempfile.TemporaryDirectory() as directory:
        report = Path(directory) / "report.json"
        config = Path(directory) / "rules.toml"
        config.write_text("[extend]\nuseDefault = true\n")
        ignored = Path(directory) / "ignore"
        ignored.write_text("")
        process = subprocess.run([
            binary, "git", ".", "--redact", "--no-banner", "--exit-code", "1",
            "--ignore-gitleaks-allow", "--gitleaks-ignore-path", str(ignored),
            "--config", str(config), "--report-format", "json", "--report-path", str(report),
            "--log-opts=" + head,
        ], cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if process.returncode not in {0, 1} or not report.exists():
            raise ValueError("Gitleaks failed to produce a report.")
        findings = json.loads(report.read_text())
        if process.returncode == 1 and not findings:
            raise ValueError("Gitleaks failed without findings.")
        return new_findings(entries, findings)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base")
    parser.add_argument("--gitleaks")
    parser.add_argument("--head", default="HEAD")
    args = parser.parse_args()
    try:
        entries = json.loads((ROOT / ".github/gitleaks-baseline.json").read_text())
        validate(ROOT, args.base, entries)
        if args.gitleaks:
            findings = scan(ROOT, args.gitleaks, args.head, entries)
            print(f"Gitleaks: {len(findings)} new finding(s); {len(entries)} historical fingerprints in baseline.")
            return bool(findings)
    except (ValueError, TypeError, KeyError, IndexError, OSError, subprocess.CalledProcessError):
        print("Secret scan rejected: invalid baseline, scanner failure, or unreadable report.")
        return 1
    print(f"Validated {len(entries)} existing-history fingerprints; no secret values stored.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
