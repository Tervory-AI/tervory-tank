"""Read saved fixtures. Tests never open a socket."""

from __future__ import annotations

from pathlib import Path


class FixtureReader:
    def __init__(self, roots: list[Path]) -> None:
        self.roots = roots

    def read_text(self, relative: str) -> str:
        for root in self.roots:
            path = root / relative
            if path.is_file():
                return path.read_text(encoding="utf-8")
        raise FileNotFoundError(relative)
