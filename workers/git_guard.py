"""Git commands that cannot push to main and cannot put a token in a URL."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from workers.github_app import assert_installation_token, assert_push_branch

CLONE_HOST = "github.com"


def credential_fill(stdin: str, token: str) -> str:
    assert_installation_token(token)
    fields = {}
    for line in stdin.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            fields[key.strip().lower()] = value.strip()
    host = fields.get("host", "")
    protocol = fields.get("protocol", "https")
    if host != CLONE_HOST or protocol != "https":
        raise PermissionError("git may only authenticate to github.com over https")
    return f"username=x-access-token\npassword={token}\n"


def clone_command(repo: str, directory: str) -> list[str]:
    if repo.count("/") != 1 or ":" in repo or "@" in repo:
        raise ValueError("repo must be owner/name")
    url = f"https://{CLONE_HOST}/{repo}.git"
    if "@" in url.split("://", 1)[-1].split("/", 1)[0]:
        raise ValueError("clone URL must not contain a token")
    return [
        "git",
        "-c",
        "credential.helper=",
        "-c",
        "credential.helper=!python3 -m workers.git_guard",
        "clone",
        "--depth",
        "1",
        "--branch",
        "main",
        url,
        directory,
    ]


def push_command(branch: str) -> list[str]:
    name = assert_push_branch(branch)
    return [
        "git",
        "-c",
        "credential.helper=",
        "-c",
        "credential.helper=!python3 -m workers.git_guard",
        "push",
        "origin",
        f"HEAD:refs/heads/{name}",
    ]


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    action = args[0] if args else "get"
    if action != "get":
        return 0
    path = os.environ.get("GITHUB_TOKEN_FILE", "")
    if not path:
        return 1
    token = Path(path).read_text(encoding="utf-8").strip()
    try:
        sys.stdout.write(credential_fill(sys.stdin.read(), token))
    except (PermissionError, RuntimeError):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
