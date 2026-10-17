"""Load Tiger's price reader. Tests stay offline."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
READER = ROOT / "tank" / "skills" / "tiger.price_extract" / "1.1.0" / "run.py"

_spec = importlib.util.spec_from_file_location("tiger_price_extract_110", READER)
if _spec is None or _spec.loader is None:
    raise ImportError(READER)
reader = importlib.util.module_from_spec(_spec)
sys.modules["tiger_price_extract_110"] = reader
_spec.loader.exec_module(reader)


def read_price(html: str, url: str = "") -> dict:
    return reader.extract(html, url)


def primary_price(result: dict) -> str | None:
    for item in result.get("items") or []:
        price = item.get("price")
        if price:
            return str(price)
    return None
