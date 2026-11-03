"""Scaffold an unapproved engine: python agents/base/engines/new_engine.py <id>."""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines import ROOT, check_id, load_engine


def scaffold(engine_id: str, repository: Path | None = None) -> list[Path]:
    """Copy skeletons only. No database, eval, approval, or network operations."""
    engine_id = check_id(engine_id)
    repository = (repository or ROOT.parents[2]).resolve()
    engine = repository / "agents/base/engines" / engine_id
    skills = repository / "tank/skills"
    destinations = [engine, skills / f"{engine_id}.ingest", skills / f"{engine_id}.profile"]
    if any(path.exists() or path.is_symlink() for path in destinations):
        raise ValueError("engine id already exists")
    template = load_engine(ROOT / "_template")
    created: list[Path] = []
    with tempfile.TemporaryDirectory(prefix="base-engine-") as temporary:
        staging = Path(temporary)
        for source in sorted(template.path.rglob("*")):
            if not source.is_file() or "__pycache__" in source.parts or source.suffix == ".pyc":
                continue
            relative = source.relative_to(template.path)
            destination = staging / str(relative).replace("template.", f"{engine_id}.")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(source.read_text(encoding="utf-8").replace("template", engine_id), encoding="utf-8")
        # Skills belong only in Skala, not in the generated Base engine package.
        staged_skills = staging / "skills"
        engine_staging = staging / "engine"
        engine_staging.mkdir()
        for source in list(staging.iterdir()):
            if source not in (staged_skills, engine_staging):
                shutil.move(str(source), engine_staging / source.name)
        load_engine(_validation_folder(engine_staging, engine_id))
        try:
            for source, destination in zip(
                [engine_staging / engine_id, staged_skills / f"{engine_id}.ingest", staged_skills / f"{engine_id}.profile"],
                destinations,
            ):
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(source, destination)
                created.append(destination)
        except Exception:
            for destination in reversed(created):
                shutil.rmtree(destination)
            raise
    return destinations


def _validation_folder(staging: Path, engine_id: str) -> Path:
    """Use the final folder name while validating the staged manifest."""
    named = staging / engine_id
    named.mkdir()
    for source in list(staging.iterdir()):
        if source != named:
            shutil.move(str(source), named / source.name)
    return named


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("id")
    parser.add_argument("--root", type=Path, help="destination repository (temporary folder for offline proof)")
    args = parser.parse_args()
    try:
        paths = scaffold(args.id, args.root)
    except ValueError as exc:
        parser.error(str(exc))
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
