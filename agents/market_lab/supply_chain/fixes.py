"""Prepare real lock changes in isolation; publish one draft PR per package/fixed version.

No merge, deployment or force-update operation exists here. Resolver failures
produce an error instead of a PR that only contains an advisory note.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile
from urllib.parse import quote, urlencode

from .http import Client, SourceError
from .locks import inventory, logical_lines
from .watch import scan
from .sources import SOURCE_URLS


class FixError(RuntimeError):
    pass


def command(args: list[str], root: Path, timeout: int = 300) -> bytes:
    try:
        return subprocess.run(args, cwd=root, capture_output=True, check=True, timeout=timeout).stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        # Resolver output can include authenticated index URLs. Do not print it.
        raise FixError(f"{args[0]} verification failed; no fix published.") from None


def grouped_fixes(report: dict) -> list[dict]:
    if not report.get("complete") or report.get("errors"):
        raise FixError("Incomplete source coverage; publishing is blocked.")
    groups = {}
    for item in report["fixes"]:
        key = (item["ecosystem"], item["package"], item["fixed_version"])
        group = groups.setdefault(key, {"ecosystem": key[0], "package": key[1], "target": key[2],
                                        "versions": set(), "locks": set(), "advisories": set(), "known_exploited": set(),
                                        "baseline_findings": report["findings"]})
        group["versions"].add(item["version"])
        for field in ("locks", "advisories", "known_exploited"):
            group[field].update(item[field])
    return [{key: sorted(value) if isinstance(value, set) else value for key, value in group.items()}
            for group in groups.values()]


def fix_key(fix: dict) -> str:
    return hashlib.sha256(json.dumps([fix["ecosystem"], fix["package"], fix["target"]]).encode()).hexdigest()[:24]


def _safe_file(root: Path, path: str) -> Path:
    target = root / path
    if Path(path).is_absolute() or ".." in Path(path).parts or target.is_symlink() or not target.resolve().is_relative_to(root.resolve()):
        raise FixError("Unsafe lock path; no fix published.")
    return target


def _replace_python(text: str, fix: dict, hashes: list[str] | None = None) -> str:
    name = re.escape(fix["package"]).replace(r"\-", "[-_.]")
    pattern = re.compile(rf"^({name}(?:\[[^]]+\])?==)([^\s;]+)(.*)$", re.I)
    blocks, pending = [], ""
    for line in text.splitlines(keepends=True):
        pending += line
        if line.rstrip().endswith("\\"):
            continue
        logical = next(logical_lines(pending)).strip()
        matched = pattern.fullmatch(logical)
        if matched and matched[2] in fix["versions"]:
            suffix = matched[3].split("--hash=", 1)[0].rstrip().removesuffix("\\").rstrip()
            if hashes is not None:
                # Preserve environment markers; replace the old release's entire hash set.
                pending = matched[1] + fix["target"] + suffix + " \\\n" + " \\\n".join("    --hash=sha256:" + value for value in hashes) + "\n"
            else:
                pending = matched[1] + fix["target"] + suffix + "\n"
        blocks.append(pending)
        pending = ""
    return "".join(blocks) + pending


def python_fix(root: Path, fix: dict, client: Client) -> None:
    release = client.json(f"https://pypi.org/pypi/{quote(fix['package'], safe='')}/{quote(fix['target'], safe='')}/json")
    if release.get("info", {}).get("version") != fix["target"]:
        raise FixError("Registry release does not match the fixed version.")
    hashes = sorted({row.get("digests", {}).get("sha256", "") for row in release.get("urls", []) if not row.get("yanked")})
    if not hashes or any(not re.fullmatch(r"[a-f0-9]{64}", value) for value in hashes):
        raise FixError("Fixed release has no verified distribution hashes.")
    for lock in fix["locks"]:
        path = _safe_file(root, lock)
        if not ("requirements" in path.name and path.suffix == ".lock"):
            raise FixError("Source/tool lock needs a reviewed source rebuild; automatic registry fix blocked.")
        before = path.read_text()
        after = _replace_python(before, fix, hashes)
        if before == after:
            raise FixError("Expected vulnerable Python version is absent.")
        path.write_text(after)
        for manifest in path.parent.iterdir():
            if manifest.suffix in {".in", ".txt"} and any(word in manifest.name for word in ("requirements", "constraints")):
                target = _safe_file(root, str(manifest.relative_to(root)))
                target.write_text(_replace_python(target.read_text(), fix))
        with tempfile.TemporaryDirectory() as downloads:
            # Wheels only: never execute a package build hook while evaluating an advisory.
            command(["python3", "-m", "pip", "download", "--require-hashes", "--only-binary=:all:",
                     "--dest", downloads, "-r", str(path)], root)


def node_fix(root: Path, fix: dict) -> None:
    for lock in fix["locks"]:
        path = _safe_file(root, lock)
        if path.name != "package-lock.json":
            raise FixError("Tool archive requires a reviewed source rebuild; automatic Node fix blocked.")
        manifest = _safe_file(root, str(path.with_name("package.json").relative_to(root)))
        data = json.loads(manifest.read_text())
        direct = False
        for group in ("dependencies", "devDependencies", "optionalDependencies"):
            if fix["package"] in data.get(group, {}):
                data[group][fix["package"]] = fix["target"]
                direct = True
        if not direct:
            overrides = data.setdefault("overrides", {})
            for version in fix["versions"]:
                overrides[f"{fix['package']}@{version}"] = fix["target"]
        manifest.write_text(json.dumps(data, indent=2) + "\n")
        # This updates lock metadata only, installs nothing, and cannot run lifecycle hooks.
        command(["npm", "update", "--package-lock-only", "--ignore-scripts", "--no-audit", "--no-fund", fix["package"]], path.parent)
        # npm ci validates lock/manifest agreement; scripts remain disabled.
        command(["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"], path.parent)


def prepare(root: Path, fix: dict, client: Client, tracked: list[str]) -> dict[str, str]:
    if not re.fullmatch(r"(?:@[a-z0-9_.-]+/)?[A-Za-z0-9_.-]+", fix["package"]) or not re.fullmatch(r"[0-9][A-Za-z0-9.+!-]*", fix["target"]):
        raise FixError("Invalid registry fix identity.")
    if fix["ecosystem"] == "PyPI":
        python_fix(root, fix, client)
    elif fix["ecosystem"] == "npm":
        node_fix(root, fix)
    else:
        raise FixError("No automatic resolver for this ecosystem.")
    after = inventory(root, tracked)
    if after.errors:
        raise FixError("Updated lock inventory is incomplete.")
    for dep in after.dependencies:
        if dep.lock in fix["locks"] and dep.name == fix["package"] and dep.version in fix["versions"]:
            raise FixError("Vulnerable package still present after resolution.")
    # New versions and transitive changes must also be checked against all three sources.
    after.dependencies = [dep for dep in after.dependencies if dep.lock in fix["locks"]]
    verified = scan(after, client)
    if not verified["complete"] or any(row["package"] == fix["package"] for row in verified["findings"]):
        raise FixError("Fixed package is still vulnerable or source verification is incomplete.")
    known = {(row["ecosystem"], row["package"], row["version"], lock)
             for row in fix.get("baseline_findings", []) for lock in row["locks"]}
    if any((row["ecosystem"], row["package"], row["version"], lock) not in known
           for row in verified["findings"] for lock in row["locks"]):
        raise FixError("Resolver introduced a new vulnerable dependency; no fix published.")
    return verified


def publish(root: Path, report: dict, client: Client, repository: str) -> list[str]:
    """Called only by the scheduled trusted-main job. Returns existing/new draft URLs."""
    planned = grouped_fixes(report)
    if not planned:
        return []
    if not client.token:
        raise FixError("SUPPLY_CHAIN_GITHUB_TOKEN is empty; draft publication is blocked.")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise FixError("Invalid repository name.")
    api = SOURCE_URLS["github"] + "repos/" + repository
    repo = client.json(api)
    base = repo["default_branch"]
    sha = client.json(api + "/git/ref/heads/" + quote(base, safe=""))["object"]["sha"]
    local = command(["git", "rev-parse", "HEAD"], root).decode().strip()
    if local != sha:
        raise FixError("Main moved during the scan; next run will scan the new main before publication.")
    tracked = command(["git", "ls-files", "-z"], root).decode().split("\0")
    urls, errors = [], []
    for fix in planned:
        try:
            urls.append(_publish_one(root, fix, client, repository, api, base, sha, tracked))
        except (FixError, SourceError, KeyError, TypeError, ValueError) as error:
            reason = str(error) if isinstance(error, (FixError, SourceError)) else "Invalid resolver or GitHub response."
            errors.append(f"{fix['package']}: {reason}")
    if errors:
        # Successful draft URLs remain available to the CLI and importing Autumbra caller.
        raise PublicationError(errors, urls)
    return urls


class PublicationError(FixError):
    def __init__(self, errors: list[str], urls: list[str]):
        super().__init__("\n".join(errors))
        self.urls = urls


def _publish_one(root: Path, fix: dict, client: Client, repository: str, api: str,
                 base: str, sha: str, tracked: list[str]) -> str:
    branch = "autumbra/supply-chain-" + fix_key(fix)
    existing = client.json(api + "/pulls?" + urlencode({"head": repository.split("/")[0] + ":" + branch, "state": "all"}))
    if existing:
        return existing[0]["html_url"]  # Preserve open reviews and closed decisions.
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory) / "repo"
        work.mkdir()
        archive = Path(directory) / "repo.tar"
        archive.write_bytes(command(["git", "archive", "HEAD"], root))
        with tarfile.open(archive) as tar:
            tar.extractall(work, filter="data")
        prepare(work, fix, client, tracked)
        changes = {}
        for name in tracked:
            if not name:
                continue
            before, after = root / name, work / name
            if before.is_symlink() or after.is_symlink():
                continue
            if before.read_bytes() != after.read_bytes():
                if not (after.name in {"package.json", "package-lock.json"} or
                        (after.suffix in {".lock", ".txt", ".in"} and any(part in after.name for part in ("requirements", "constraints")))):
                    raise FixError("Resolver changed a file outside dependency manifests/locks.")
                changes[name] = after.read_text()
        if not changes:
            raise FixError("Resolver produced no dependency fix.")
        base_commit = client.json(api + "/git/commits/" + sha)
        entries = []
        for name, content in sorted(changes.items()):
            blob = client.json(api + "/git/blobs", {"content": content, "encoding": "utf-8"}, method="POST")
            entries.append({"path": name, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        tree = client.json(api + "/git/trees", {"base_tree": base_commit["tree"]["sha"], "tree": entries}, method="POST")
        title = f"Autumbra: fix {fix['package']} at {fix['target']}"
        commit = client.json(api + "/git/commits", {"message": title, "tree": tree["sha"], "parents": [sha]}, method="POST")
        try:
            client.json(api + "/git/refs", {"ref": "refs/heads/" + branch, "sha": commit["sha"]}, method="POST")
        except SourceError as error:
            if error.status != 422:
                raise
            # Recover a prior successful branch creation followed by a failed PR API call.
            # Reuse only an identical verified tree; never force-update an existing branch.
            ref = client.json(api + "/git/ref/heads/" + quote(branch, safe=""))
            previous = client.json(api + "/git/commits/" + ref["object"]["sha"])
            if previous["tree"]["sha"] != tree["sha"] or previous["message"] != title:
                raise FixError("Existing fix branch differs; preserved for review.") from None
        body = (
            f"Market Lab matched {', '.join(fix['advisories'])} against committed locks.\n\n"
            f"Changes {fix['package']} from {', '.join(fix['versions'])} to {fix['target']}.\n\n"
            "Tested: hash-checked wheel resolution or npm ci with scripts disabled; OSV, GitHub advisories "
            "and CISA KEV queried again for the changed locks. CI and independent review are still required.\n\n"
            "Decisions I made: one draft per package/fixed version across all affected locks; no merge or deployment.\n\n"
            "Proof: open Files changed to inspect the lock hashes, then Checks to inspect install-pins, gitleaks "
            "and application tests. This backend change has no client page.\n"
        )
        pull = client.json(api + "/pulls", {"title": title, "body": body, "head": branch, "base": base, "draft": True}, method="POST")
        return pull["html_url"]
