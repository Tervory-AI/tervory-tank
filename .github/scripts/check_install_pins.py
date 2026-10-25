"""Reject mutable build/CI installs; report locations without printing commands."""

from __future__ import annotations

import base64
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
DIGEST = re.compile(r"@sha256:[a-f0-9]{64}$")
PYTHON_PIN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*(?:\[[^]]+\])?==[^\s,;*<>=]+(?:\s*;[^\n]+)?$")


def logical_lines(text: str):
    pending, first = "", 0
    for number, line in enumerate(text.splitlines(), 1):
        if not pending:
            first = number
        if line.lstrip().startswith("#"):
            continue
        pending += line.strip().removesuffix("\\") + " "
        if line.rstrip().endswith("\\"):
            continue
        yield first, pending.strip()
        pending = ""
    if pending:
        yield first, pending.strip()


def lock_errors(text: str) -> list[tuple[int, str]]:
    errors = []
    for number, line in logical_lines(text):
        if not line:
            continue
        requirement = re.split(r"\s+--hash=", line, maxsplit=1)[0]
        hashes = re.findall(r"--hash=([^\s]+)", line)
        if not PYTHON_PIN.fullmatch(requirement) or not hashes or any(
            not re.fullmatch(r"sha256:[a-f0-9]{64}", value) for value in hashes
        ):
            errors.append((number, "Python lock entry needs an exact version and SHA256 hashes"))
    return errors


def install_errors(text: str) -> list[tuple[int, str]]:
    errors = []
    for number, line in logical_lines(text):
        if not line:
            continue
        # Commands may be chained in a Docker RUN or a YAML run block.
        for command in re.split(r"&&|;|\|\|", line):
            pip = re.search(
                r"(?:\bpython[\d.]*\s+-m\s+pip|\bpip3?)\s+(?:--[\w-]+\s+)*install\b(.*)", command,
            )
            if pip:
                try:
                    args = shlex.split(pip[1], comments=True)
                except ValueError:
                    errors.append((number, "Cannot verify Python install arguments"))
                    continue
                files = [args[i + 1] for i, arg in enumerate(args[:-1]) if arg in ("-r", "--requirement")]
                files += [arg.split("=", 1)[1] for arg in args if arg.startswith("--requirement=")]
                files += [arg[2:] for arg in args if arg.startswith("-r") and arg != "-r"]
                if "--require-hashes" not in args or not files or any(
                    not path.endswith(".lock") or "$" in path for path in files
                ):
                    errors.append((number, "Python install must use --require-hashes and a requirements lock"))
            if re.search(r"\bnpm\b.*\b(?:install|i|add|update|upgrade)\b", command):
                errors.append((number, "Node packages must be installed with npm ci from a committed lock"))
            if re.search(r"\b(?:yarn|pnpm)\s+(?:install|add|update)\b", command):
                errors.append((number, "Use the committed npm lock and npm ci"))
            os_install = re.search(r"\b(?:apt-get|apt|apk)\s+(?:install|add)\b(.*)", command)
            if os_install:
                try:
                    packages = [arg for arg in shlex.split(os_install[1], comments=True) if not arg.startswith("-")]
                except ValueError:
                    packages = []
                if not packages or any(not re.fullmatch(r"[\w.+:-]+=[^\s$*]+", arg) for arg in packages):
                    errors.append((number, "OS package installs need exact package=version pins"))
            if re.search(r"\b(?:curl|wget)\b.*\|\s*(?:sh|bash)\b", command):
                errors.append((number, "Remote installers must be downloaded and checksum-verified before execution"))
    return errors


def docker_errors(text: str) -> list[tuple[int, str]]:
    errors, stages = [], set()
    for number, line in logical_lines(text):
        match = re.match(r"FROM\s+(?:--platform=\S+\s+)?(\S+)(?:\s+AS\s+(\S+))?", line, re.I)
        if not match:
            continue
        base, alias = match.groups()
        if base.lower() not in stages and base.lower() != "scratch" and not DIGEST.search(base):
            errors.append((number, "External Docker base image must be pinned by @sha256"))
        if alias:
            stages.add(alias.lower())
    return errors + install_errors(text)


def node_lock_errors(package: dict, lock: dict) -> list[str]:
    errors = []
    if lock.get("lockfileVersion", 0) < 2 or not isinstance(lock.get("packages"), dict):
        return ["Node lock must contain package versions and integrity hashes"]
    root = lock["packages"].get("", {})
    for group in ("dependencies", "devDependencies", "optionalDependencies"):
        if package.get(group, {}) != root.get(group, {}):
            errors.append("Node lock does not match package.json")
    for name, item in lock["packages"].items():
        if not name or item.get("link"):
            continue
        integrity = item.get("integrity", "")
        try:
            algorithm, digest = integrity.split("-", 1)
            size = {"sha256": 32, "sha384": 48, "sha512": 64}[algorithm]
            valid = len(base64.b64decode(digest, validate=True)) == size
        except (ValueError, KeyError):
            valid = False
        if not item.get("version") or not valid:
            errors.append(f"Node lock package {name} needs a version and integrity hash")
    return errors


def check(root: Path, paths: list[Path]) -> list[str]:
    errors = []
    for path in paths:
        relative = path.relative_to(root)
        if not path.is_file():
            continue
        if path.name.startswith("Dockerfile"):
            errors.extend(f"{relative}:{line}: {reason}" for line, reason in docker_errors(path.read_text()))
        elif relative.parts[:2] == (".github", "workflows") and path.suffix in (".yml", ".yaml"):
            errors.extend(f"{relative}:{line}: {reason}" for line, reason in install_errors(path.read_text()))
        elif path.suffix == ".sh" or path.name == "Makefile":
            errors.extend(f"{relative}:{line}: {reason}" for line, reason in install_errors(path.read_text()))
        if "requirements" in path.name and path.suffix == ".lock":
            errors.extend(f"{relative}:{line}: {reason}" for line, reason in lock_errors(path.read_text()))
        elif "requirements" in path.name and path.suffix in (".txt", ".in"):
            if not path.with_suffix(".lock").is_file():
                errors.append(f"{relative}: missing adjacent requirements lock")
        if path.name == "package.json":
            lock = path.with_name("package-lock.json")
            if not lock.is_file():
                errors.append(f"{relative}: missing package-lock.json")
            else:
                try:
                    reasons = node_lock_errors(json.loads(path.read_text()), json.loads(lock.read_text()))
                except (ValueError, TypeError):
                    reasons = ["Cannot parse Node manifest/lock"]
                errors.extend(f"{relative}: {reason}" for reason in reasons)
    return errors


def main() -> int:
    tracked = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT,
    ).decode().split("\0")
    errors = check(ROOT, [ROOT / name for name in sorted(set(tracked)) if name])
    for error in errors:
        print(error)
    print(f"Install pin check: {len(errors)} violation(s)")
    return bool(errors)


if __name__ == "__main__":
    sys.exit(main())
