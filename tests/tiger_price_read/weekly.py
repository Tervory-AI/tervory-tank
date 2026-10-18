"""Re-test Tiger's price-read gold set. Alert when a score falls more than 2 points.

Offline. Reads saved pages only. This is the weekly entry point for this gold
set; it does not touch the shared app.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from reader import primary_price, read_price

HERE = Path(__file__).resolve().parent
GOLD = HERE / "gold" / "pages.jsonl"
BASELINE = HERE / "gold" / "baseline.json"
DROP_LIMIT = 2.0


def load_rows(path: Path = GOLD) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def html_for(row: dict, root: Path = HERE) -> str:
    rel = Path(row["html"])
    if rel.is_absolute():
        return rel.read_text(encoding="utf-8")
    for base in (root, root.parents[1]):
        candidate = base / rel
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    raise FileNotFoundError(rel)


def score_rows(rows: list[dict], root: Path = HERE) -> dict:
    groups: dict[str, list[bool]] = {}
    details = []
    for row in rows:
        if row.get("split") == "inbox":
            group = "inbox"
        else:
            group = row.get("split") or "build"
        predicted = primary_price(read_price(html_for(row, root), row.get("url") or ""))
        expected = row.get("expected_price")
        match = predicted == expected
        groups.setdefault(group, []).append(match)
        details.append({
            "id": row["id"],
            "layout": row.get("layout"),
            "expected_price": expected,
            "predicted_price": predicted,
            "match": match,
            "split": group,
            "verified": False,
        })
    summary = {}
    for name, flags in groups.items():
        total = len(flags)
        hits = sum(flags)
        summary[name] = {
            "n": total,
            "hits": hits,
            "pct": round(100.0 * hits / total, 2) if total else None,
        }
    return {"groups": summary, "details": details}


def alert_for(current: dict, baseline: dict, limit: float = DROP_LIMIT) -> dict:
    """Alert when a tracked score drops by more than `limit` points."""
    reasons = []
    for name in ("build", "holdout"):
        now = (current.get("groups") or {}).get(name, {}).get("pct")
        then = (baseline.get("groups") or {}).get(name, {}).get("pct")
        if now is None or then is None:
            continue
        drop = round(then - now, 2)
        if drop > limit:
            reasons.append(f"{name} fell from {then} to {now} ({drop} points)")
    return {"alert": bool(reasons), "reasons": reasons}


def main() -> int:
    parser = argparse.ArgumentParser(description="Re-test the price-read gold set")
    parser.add_argument("--baseline", type=Path, default=BASELINE)
    args = parser.parse_args()
    current = score_rows(load_rows())
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    result = alert_for(current, baseline)
    print(json.dumps({"scores": current["groups"], **result}, indent=2))
    return 1 if result["alert"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
