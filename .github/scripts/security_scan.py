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


def annotation(kind: str, text: str, path: str = "", line: int | None = None) -> None:
    """Escape workflow command syntax; callers supply only permitted metadata."""
    def escape(value: str) -> str:
        return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")

    properties = []
    if path:
        properties.append("file=" + escape(path).replace(":", "%3A").replace(",", "%2C"))
    if line is not None:
        properties.append(f"line={int(line)}")
    suffix = " " + ",".join(properties) if properties else ""
    print(f"::{kind}{suffix}::{escape(text)}")


def semgrep_error(error: dict) -> dict:
    # Tagged error variants can carry skipped source tokens. Retain only the tag.
    kind = error.get("type", "UnknownError")
    if isinstance(kind, list):
        kind = kind[0] if kind else "UnknownError"
    if not isinstance(kind, str):
        kind = "UnknownError"
    path = error.get("path") or ""
    if not isinstance(path, str):
        path = ""
    # Semgrep 1.182.1 represents registry download failures as SemgrepError.
    # Inspect its stable prefix for classification, but never retain/emit the message.
    download_failed = str(error.get("message", "")).lower().startswith(
        "failed to download configuration")
    fatal = (str(error.get("level", "")).lower() == "fatal"
             or kind in {"Fatal error", "FatalError", "RuleDownloadError", "ConfigDownloadError"}
             or download_failed)
    return {"type": kind, "path": path, "fatal": fatal}


def leaks(base: str | None, temp: Path, output: Path) -> bool:
    # PR #374: Claude-reviewed fingerprints and one exact public CI dummy value.
    config = Path(".gitleaks.toml").resolve()
    ignore = Path(".gitleaksignore").resolve()
    raw = temp / "gitleaks.json"
    code = run(["gitleaks", "git", ".", "--no-banner", "--redact=100",
                "--config", str(config), "--gitleaks-ignore-path", str(ignore),
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
            "--disable-version-check", "--disable-nosem", "--no-git-ignore",
            "--json", "--output", str(raw)]
    if base:
        args += ["--baseline-commit", base]
    try:
        # Read findings/errors even when the CLI returns nonzero. In particular,
        # exit 3 denotes target parse errors, which are notices under this policy.
        code = run([*args, "."], tuple(range(256)))
        if not raw.is_file():
            annotation("notice", f"SemgrepReportMissingExit{code}", str(raw))
            raise RuntimeError("Semgrep did not create its JSON report")
        report = json.loads(raw.read_text())
    except FileNotFoundError as error:
        annotation("notice", "SemgrepExecutableMissing", error.filename or "semgrep")
        raise
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        # A missing-report notice above already identifies the path and exit code.
        if not isinstance(error, RuntimeError) or raw.is_file():
            annotation("notice", type(error).__name__)
        raise
    findings = [{"rule": row["check_id"], "path": row["path"],
                 "line": row["start"]["line"], "severity": row["extra"]["severity"]}
                for row in report["results"]]
    errors = [semgrep_error(error) for error in report["errors"]]
    # Fatal process/configuration exits and a missing report still fail closed.
    # 0 = success, 1 = findings, 3 = target parsing errors in the pinned CLI.
    if (code not in (0, 1, 3) or (code == 3 and not errors)) and not any(e["fatal"] for e in errors):
        errors.append({"type": "SemgrepProcessError", "path": "", "fatal": True})
    fatal_count = sum(error["fatal"] for error in errors)
    write(output / "semgrep.json", {"findings": findings, "errors": errors,
                                    "error_count": len(errors), "fatal_error_count": fatal_count,
                                    "non_fatal_error_count": len(errors) - fatal_count,
                                    "exit_code": code})
    for finding in findings:
        annotation("error", f"{finding['rule']} {finding['severity']}",
                   finding["path"], finding["line"])
    for error in errors:
        annotation("notice", error["type"], error["path"])
    if fatal_count:
        raise RuntimeError("Semgrep scan is incomplete")
    # ERROR is the legacy spelling of HIGH; non-fatal notices do not alter this gate.
    return any(row["severity"] in {"ERROR", "HIGH", "CRITICAL"} for row in findings)


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
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError) as error:
        # No exception text: a tool/library error can echo source or credentials.
        status["result"] = "incomplete"
        status["error_type"] = type(error).__name__
        failed = True
    write(args.output / f"{args.tool}-status.json", status)
    print(f"{args.tool}: {status['result']}")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
