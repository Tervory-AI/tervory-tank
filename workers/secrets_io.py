"""Per-task secret files. The directory is private. The values are never logged."""

from __future__ import annotations

from pathlib import Path

from workers.github_app import assert_installation_token


def _write(path: Path, value: str) -> None:
    if "\n" in value or "\r" in value or not value:
        raise RuntimeError("refusing to store an unusable secret")
    path.write_text(value, encoding="utf-8")
    # Read-only for everyone in the task: the file is owned by host UID 1002 (root inside the
    # rootless container) and the task process drops to UID 1001 before it reads the token.
    path.chmod(0o444)


def stage(directory: Path, *, token: str, tank_key: str) -> None:
    assert_installation_token(token)
    if len(tank_key) < 8 or len(tank_key) > 500:
        raise RuntimeError("Tank key file is missing or unusable")
    directory.mkdir(parents=True, exist_ok=True)
    # 0711: UID 1001 in the task can open the known file names but not list the directory.
    # Safe on the host because the parent ($XDG_RUNTIME_DIR/tervory-workers) is 0700.
    directory.chmod(0o711)
    _write(directory / "token", token)
    _write(directory / "tank_key", tank_key)


def replace_token(directory: Path, token: str) -> None:
    assert_installation_token(token)
    target = directory / "token"
    if target.exists():
        target.chmod(0o600)
    _write(target, token)
