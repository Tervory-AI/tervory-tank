"""Validated, code-only Base engine discovery. Skill versions remain Skala's choice."""

from __future__ import annotations

import importlib
import importlib.util
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parent
_IDENTIFIER = re.compile(r"[a-z][a-z0-9_]*")
PROFILE_DATA_KEYS = ("generic_words", "blocked_hosts", "generic_locals")


def check_id(value: Any) -> str:
    # Import lazily: pipeline can continue to boot without loading any engine code.
    from pipeline import _ENGINE_ID

    if not isinstance(value, str) or _ENGINE_ID.fullmatch(value) is None:
        raise ValueError("invalid engine id")
    return value


@dataclass(frozen=True)
class Engine:
    path: Path
    id: str
    skills: dict[str, str]
    routes: dict[str, str]
    gold_lists: Path
    profile_data_keys: tuple[str, ...]

    def module(self, name: str) -> ModuleType:
        """Resolve engine-owned code in both repository and flat /app layouts."""
        if not isinstance(name, str) or _IDENTIFIER.fullmatch(name) is None:
            raise ValueError("invalid engine module")
        if self.path.parent == ROOT:
            return importlib.import_module(f"{__name__}.{self.path.name}.{name}")
        # A temporary scaffold has no installed package. Give its relative imports
        # a private namespace, without changing sys.path or the installed engines.
        package = f"{__name__}._scaffold_{self.id}_{abs(hash(str(self.path)))}"
        if package not in sys.modules:
            spec = importlib.util.spec_from_file_location(
                package, self.path / "__init__.py",
                submodule_search_locations=[str(self.path)],
            )
            if spec is None or spec.loader is None:
                raise ValueError("engine package cannot be loaded")
            module = importlib.util.module_from_spec(spec)
            sys.modules[package] = module
            spec.loader.exec_module(module)
        return importlib.import_module(f"{package}.{name}")

    def register(self, app: Any) -> None:
        register = getattr(self.module(self.routes["module"]), self.routes["function"])
        if not callable(register):
            raise ValueError("engine route registrar is not callable")
        register(app)


def load_engine(engine: str | Path, root: Path = ROOT) -> Engine:
    """Load and check exactly one manifest; explicit _template loading is allowed."""
    path = engine if isinstance(engine, Path) else root / check_id(engine)
    path = path.resolve()
    manifest = json.loads((path / "engine.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("engine manifest must be an object")
    engine_id = check_id(manifest.get("id"))
    if path.name != "_template" and path.name != engine_id:
        raise ValueError("engine id must match its folder")
    skills = manifest.get("skills")
    if skills != {"ingest": f"{engine_id}.ingest", "profile": f"{engine_id}.profile"}:
        raise ValueError("engine skill ids must match its id, without versions")
    routes = manifest.get("routes")
    if not isinstance(routes, dict) or set(routes) != {"module", "function"}:
        raise ValueError("engine routes require a module and function")
    if any(not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None for value in routes.values()):
        raise ValueError("invalid engine route registrar")
    if not (path / (routes["module"] + ".py")).is_file():
        raise ValueError("engine route module is missing")
    gold = manifest.get("gold_lists")
    if not isinstance(gold, str) or Path(gold).name != gold or not gold.endswith(".json"):
        raise ValueError("gold list must be a local JSON file")
    gold_path = path / gold
    if not gold_path.is_file() or gold_path.is_symlink():
        raise ValueError("engine gold list is missing or a symlink")
    json.loads(gold_path.read_text(encoding="utf-8"))
    if manifest.get("profile_data_keys") != list(PROFILE_DATA_KEYS):
        raise ValueError("engine profile data keys must match engine_terms")
    return Engine(path, engine_id, skills, routes, gold_path, PROFILE_DATA_KEYS)


def list_engines(root: Path = ROOT) -> list[Engine]:
    """List installed engines in stable order, never template/private folders."""
    return [load_engine(path) for path in sorted(root.iterdir())
            if path.is_dir() and not path.name.startswith("_")]
