"""Durable local artifacts; room storage never falls back to a temporary volume."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any


def durable_root(explicit: Path | None = None) -> Path:
    root = Path(explicit if explicit is not None else os.environ.get('DATA_DIR', '/data')).resolve()
    root.mkdir(parents=True, exist_ok=True)
    # A unique probe avoids concurrent jobs deleting one another's probe.
    with tempfile.NamedTemporaryFile(dir=root, prefix='.write-probe-'):
        pass
    return root


def tenant_folder(root: Path, category: str, tenant: str, *parts: str) -> Path:
    if category not in {'builds', 'readings', 'reviews'}:
        raise ValueError('invalid stored build')
    names = (category, tenant, *parts)
    if any(not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', name) for name in names):
        raise ValueError('invalid stored build')
    current = root.resolve()
    for name in names:
        current = current / name
        if current.is_symlink():
            raise ValueError('invalid stored build')
        current.mkdir(exist_ok=True)
    return current


def atomic_json(path: Path, value: Any) -> None:
    if path.is_symlink():
        raise ValueError('invalid stored build')
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                prefix='.' + path.name + '-', suffix='.partial', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
