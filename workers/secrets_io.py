"""Per-task secret files. The directory is private. The values are never logged."""

from __future__ import annotations

from pathlib import Path

from workers.github_app import assert_installation_token


def _write(path: Path, value: str) -> None:
    if "\n" in value or "\r" in value or not value:
        raise RuntimeError("refusing to store an unusable secret")
    path.write_text(value, encoding="utf-8")
    path.chmod(0o644)


def stage(directory: Path, *, token: str, tank_key: str) -> None:
    assert_installation_token(token)
    if len(tank_key) < 8 or len(tank_key) > 500:
        raise RuntimeError("Tank key file is missing or unusable")
    directory.mkdir(parents=True, exist_ok=True)
    directory.chmod(0o700)
    _write(directory / "token", token)
    _write(directory / "tank_key", tank_key)


def replace_token(directory: Path, token: str) -> None:
    assert_installation_token(token)
    _write(directory / "token", token)
