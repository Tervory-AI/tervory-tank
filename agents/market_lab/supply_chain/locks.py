"""Read every committed lock, including inactive Python markers and nested Node deps."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote, urlsplit

from .sources import TOOL_REPOSITORIES


@dataclass(frozen=True, order=True)
class Dependency:
    ecosystem: str
    name: str
    version: str
    lock: str
    repository: str = ""
    revision: str = ""


@dataclass
class Inventory:
    dependencies: list[Dependency] = field(default_factory=list)
    coverage: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def logical_lines(text: str):
    yield from re.sub(r"\\\r?\n\s*", " ", text).splitlines()


def python_locks(path: str, text: str) -> list[Dependency]:
    result = []
    for line in logical_lines(text):
        line = line.strip()
        if not line or line.startswith("#") or line.startswith(("--index-url ", "--extra-index-url ", "--find-links ")):
            continue
        match = re.match(r"^([\w.-]+)(?:\[[^]]+\])?==([^\s;]+)", line)
        if not match:
            raise ValueError("Python lock entry has no registry version; needs an explicit source identity")
        name, version = match.groups()
        result.append(Dependency("PyPI", re.sub(r"[-_.]+", "-", name.lower()), version, path))
    return result


def node_locks(path: str, data: dict) -> list[Dependency]:
    packages = data.get("packages")
    if not isinstance(packages, dict):
        raise ValueError("Node lock must be v2/v3 with packages")
    result = []
    for location, package in packages.items():
        if not location or package.get("link"):
            continue
        name = package.get("name") or location.rsplit("node_modules/", 1)[-1]
        version = package.get("version")
        if not isinstance(version, str) or not version or ":" in version:
            raise ValueError("Node dependency has no registry version")
        result.append(Dependency("npm", name, version, path))
    return result


def repository_from_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.query:
        raise ValueError("Invalid source repository URL")
    if parsed.hostname in {"github.com", "codeload.github.com"}:
        return "/".join(parsed.path.strip("/").split("/")[:2]).removesuffix(".git")
    return ""


def custom_locks(path: str, data) -> tuple[list[Dependency], str]:
    result = []
    if path.endswith("/models.lock.json"):
        if not isinstance(data, list) or not all(row.get("files") and row.get("revision") for row in data):
            raise ValueError("Invalid model artifact lock")
        return [], "data-only: model weights, no executable package identity (not an advisory clearance)"
    if isinstance(data, list):
        for row in data:
            revision = row.get("revision", "")
            if not re.fullmatch(r"[a-f0-9]{40}", revision):
                raise ValueError("Source lock has no immutable revision")
            repository = repository_from_url(row["repository"])
            result.append(Dependency("GIT", row["repository"], revision, path, repository, revision))
    elif "assets" in data:
        for asset in data["assets"]:
            if urlsplit(asset["url"]).hostname == "registry.npmjs.org":
                result.append(Dependency("npm", asset["name"], asset["version"], path))
            else:
                repository, tag = TOOL_REPOSITORIES[asset["name"]]
                result.append(Dependency("GIT", asset["name"], asset["version"], path, repository,
                                         tag.format(version=asset["version"])))
    elif path.endswith("/flash-attn.lock.json"):
        name = unquote(urlsplit(data["url"]).path).rsplit("/", 1)[-1]
        match = re.fullmatch(r"flash_attn-(.+)\.tar\.gz", name)
        if not match:
            raise ValueError("Unknown flash-attn archive identity")
        result.append(Dependency("PyPI", "flash-attn", match[1], path))
    elif path.endswith("/meshroom.lock.json"):
        for name, version in (("meshroom", data["version"]), ("alicevision", data["alicevision"])):
            repository, tag = TOOL_REPOSITORIES[name]
            result.append(Dependency("GIT", name, version, path, repository, tag.format(version=version)))
    else:
        raise ValueError("Unknown lock format; add a reader before claiming coverage")
    return result, "software"


def is_lock(path: str) -> bool:
    return Path(path).name.endswith((".lock", ".lock.json")) or Path(path).name in {
        "package-lock.json", "npm-shrinkwrap.json", "pnpm-lock.yaml", "Cargo.lock", "Gemfile.lock", "go.sum",
    }


def inventory(root: Path, paths: list[str] | None = None) -> Inventory:
    if paths is None:
        paths = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode().split("\0")
    out = Inventory()
    for path in sorted(set(filter(is_lock, paths))):
        try:
            text = (root / path).read_text()
            status = "software"
            if "requirements" in Path(path).name and path.endswith(".lock"):
                deps = python_locks(path, text)
            elif Path(path).name in {"package-lock.json", "npm-shrinkwrap.json"}:
                deps = node_locks(path, json.loads(text))
            else:
                deps, status = custom_locks(path, json.loads(text))
            if not deps and status == "software":
                raise ValueError("Software lock contains no readable dependency identities")
            out.dependencies.extend(deps)
            out.coverage[path] = status
        except (ValueError, KeyError, TypeError, AttributeError, OSError):
            out.coverage[path] = "unreadable: advisory coverage incomplete"
            out.errors.append(f"{path}: lock format or package identity is unsupported")
    out.dependencies = sorted(set(out.dependencies))
    if not out.coverage:
        out.errors.append("No committed lockfiles found")
    return out
