"""Run the free scanners; adapt their reports to CI policy, never detect issues here."""
from __future__ import annotations

import argparse
import fnmatch
import json
from pathlib import Path
import subprocess
import tempfile


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def run(args: list[str], allowed: tuple[int, ...] = (0,)) -> int:
    # Scanner diagnostics can contain source text. Only sanitized JSON is retained.
    result = subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            timeout=900, check=False)
    if result.returncode not in allowed:
        raise RuntimeError(f"{args[0]} failed (exit {result.returncode}); scan is incomplete")
    return result.returncode


def write(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n")


def leaks(base: str | None, temp: Path, output: Path) -> bool:
    config = temp / "gitleaks.toml"
    config.write_text("[extend]\nuseDefault = true\n")
    raw = temp / "gitleaks.json"
    code = run(["gitleaks", "git", ".", "--no-banner", "--redact=100",
                "--config", str(config), "--gitleaks-ignore-path", str(temp / "no-ignore"),
                "--ignore-gitleaks-allow", "--log-opts", f"{base}..HEAD" if base else "HEAD",
                "--report-format", "json", "--report-path", str(raw)], (0, 1))
    findings = json.loads(raw.read_text())
    if not isinstance(findings, list):
        raise ValueError("Invalid Gitleaks report")
    # Do not retain matches, secrets, commit messages, authors or email addresses.
    safe = [{k: row[k] for k in ("RuleID", "File", "StartLine", "Commit")}
            for row in findings]
    write(output / "gitleaks.json", safe)
    return code == 1 or bool(safe)


def semgrep(base: str | None, temp: Path, output: Path) -> bool:
    raw = temp / "semgrep.json"
    args = ["semgrep", "scan", "--config", "auto", "--metrics", "off",
            "--disable-nosem", "--no-git-ignore", "--json", "--output", str(raw)]
    if base:
        args += ["--baseline-commit", base]
    run([*args, "."])
    report = json.loads(raw.read_text())
    findings = [{"rule": row["check_id"], "path": row["path"],
                 "line": row["start"]["line"], "severity": row["extra"]["severity"]}
                for row in report["results"]]
    errors = report["errors"]
    write(output / "semgrep.json", {"findings": findings, "error_count": len(errors)})
    # ERROR is the legacy spelling of HIGH. Never treat incomplete scans as clean.
    return bool(errors) or any(row["severity"] in {"ERROR", "HIGH", "CRITICAL"}
                               for row in findings)


def lockfiles(ref: str) -> list[str]:
    paths = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", "-z", ref])
    return [path for path in paths.decode().split("\0") if path and
            (Path(path).name == "package-lock.json" or
             fnmatch.fnmatch(Path(path).name, "*requirements*.txt") or
             fnmatch.fnmatch(Path(path).name, "*requirements*.lock"))]


def osv_report(ref: str, temp: Path) -> tuple[dict, list[str], Path]:
    root = temp / ref
    root.mkdir()
    paths = lockfiles(ref)
    if not paths:
        raise ValueError("No dependency inputs found; scan is incomplete")
    args = ["osv-scanner", "scan", "source", "--no-resolve", "--all-packages",
            "--all-vulns", "--no-ignore", "--format", "json"]
    config = temp / "osv.toml"
    config.write_text("")  # Do not allow a repo config to suppress vulnerabilities.
    raw = temp / f"osv-{ref}.json"
    args += ["--config", str(config), "--output-file", str(raw)]
    for name in paths:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(subprocess.check_output(["git", "show", f"{ref}:{name}"]))
        kind = "package-lock.json" if target.name == "package-lock.json" else "requirements.txt"
        args += ["--lockfile", f"{kind}:{target}"]
    run(args, (0, 1))  # 1 means findings; all infrastructure/parse failures block.
    report = json.loads(raw.read_text())
    if "results" not in report or not isinstance(report["results"], (list, type(None))):
        raise ValueError("Invalid OSV report")
    return report, paths, root


def osv_findings(report: dict, root: Path) -> dict[tuple[str, ...], dict]:
    findings = {}
    for source in report["results"] or []:
        path = str(Path(source["source"]["path"]).relative_to(root))
        for item in source["packages"]:
            package = item["package"]
            for vuln in item.get("vulnerabilities", []):
                key = (path, package["ecosystem"], package["name"], package["version"], vuln["id"])
                # OSV computes CVSS. Do not implement our own score calculator.
                scores = [group["max_severity"] for group in item.get("groups", [])
                          if vuln["id"] in group["ids"] and group.get("max_severity")]
                score = max((float(s) for s in scores), default=None)
                findings[key] = dict(zip(("path", "ecosystem", "package", "version", "id"), key))
                findings[key]["cvss"] = score
    return findings


def osv(base: str | None, temp: Path, output: Path) -> bool:
    head = git("rev-parse", "HEAD")
    report, paths, root = osv_report(head, temp)
    current = osv_findings(report, root)
    previous = {}
    if base and base != head:
        old, _, old_root = osv_report(base, temp)
        previous = osv_findings(old, old_root)
    elif base:
        previous = current
    new = [row for key, row in current.items() if key not in previous]
    write(output / "osv.json", {"lockfiles": paths, "findings": new,
                                "total_findings": len(current), "baseline": base})
    # PR/push: every newly introduced vulnerable version blocks, at any severity.
    # Weekly: high/critical (CVSS >= 7); unknown scores also block for review.
    return bool(new) if base else any(row["cvss"] is None or row["cvss"] >= 7 for row in new)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tool", choices=("gitleaks", "semgrep", "osv"))
    parser.add_argument("--base", help="PR base SHA, or main's before SHA; omit for weekly")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    status = {"tool": args.tool, "head": git("rev-parse", "HEAD"), "base": args.base}
    try:
        base = None
        if args.base and set(args.base) != {"0"}:
            base = git("rev-parse", "--verify", f"{args.base}^{{commit}}")
        # A new-main push with an all-zero before SHA gets a full scan.
        with tempfile.TemporaryDirectory(prefix="security-", dir=args.output.parent) as directory:
            failed = {"gitleaks": leaks, "semgrep": semgrep, "osv": osv}[args.tool](
                base, Path(directory), args.output)
        status["result"] = "findings" if failed else "clean"
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError):
        # No exception text: a tool/library error can echo source or credentials.
        status["result"] = "incomplete"
        failed = True
    write(args.output / f"{args.tool}-status.json", status)
    print(f"{args.tool}: {status['result']}")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
