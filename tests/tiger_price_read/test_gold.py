"""100 unique product pages. 20% held out of the score used while building.

Gold answers are unverified until a person checks them. Scores are provisional.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal
from urllib.parse import urlparse

from label_pages import split_for
from weekly import BASELINE, GOLD, HERE, alert_for, load_rows, score_rows

REVIEW = HERE / "gold" / "GOLD_REVIEW.tsv"
PASS_MARK = 98.0
VERIFIED_BY_ZENAS = {
    "live-075",
    "live-076",
    "live-077",
    "live-078",
    "live-049",
    "live-064",
    "live-107",
    "live-108",
}


def _member_override(evidence: str) -> bool:
    """The member-hero rule wrote the label when it is below the structured price."""
    hero = re.search(r"hero=([0-9.]+)", evidence)
    structured = re.search(r"jsonld=([0-9.]+)", evidence)
    if not hero or not structured:
        return False
    return Decimal(hero.group(1)) < Decimal(structured.group(1))


def _note(row: dict) -> str:
    if row.get("verified"):
        return "verified by Zenas"
    if row.get("unreadable"):
        return "can't read"
    return ""


def _product_key(row: dict) -> str:
    if row.get("source") == "existing":
        return "fixture:" + row["id"]
    parsed = urlparse(row.get("url") or "")
    if not parsed.netloc:
        return row["id"]
    return parsed.netloc.lower() + parsed.path.rstrip("/").lower()


def _write_review(details: list[dict]) -> None:
    lines = [
        "page id\tlayout\texpected price\tpredicted price\tmatch\tverified\tsource\tsplit\tnote"
    ]
    by_id = {row["id"]: row for row in load_rows()}
    for row in details:
        origin = by_id[row["id"]]
        match = "yes" if row["match"] else "no"
        lines.append(
            "\t".join([
                row["id"],
                str(row["layout"]),
                "" if row["expected_price"] is None else str(row["expected_price"]),
                "" if row["predicted_price"] is None else str(row["predicted_price"]),
                match,
                "yes" if origin.get("verified") else "no",
                origin.get("source", ""),
                row["split"],
                _note(origin),
            ])
        )
    REVIEW.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_price_read_gold_set() -> None:
    rows = load_rows()
    scored_rows = [row for row in rows if row.get("expected_price") or row.get("unreadable")]
    assert len(scored_rows) >= 100
    keys = [_product_key(row) for row in scored_rows]
    assert len(keys) == len(set(keys))
    assert len(keys) >= 100
    layouts = {row["layout"] for row in scored_rows}
    assert len(layouts) >= 8
    verified = {row["id"] for row in scored_rows if row.get("verified")}
    assert verified == VERIFIED_BY_ZENAS
    splits = {row["split"] for row in scored_rows}
    assert splits == {"build", "holdout"}
    holdout_n = sum(row["split"] == "holdout" for row in scored_rows)
    assert 0.15 <= holdout_n / len(scored_rows) <= 0.25
    sources = {row["source"] for row in scored_rows}
    assert "existing" in sources
    assert "live" in sources or "synthetic" in sources

    # The hash stands, except one sale-and-higher page held back on purpose.
    exceptions = [row for row in scored_rows if row["split"] != split_for(row["id"])]
    assert len(exceptions) == 1
    assert exceptions[0]["split"] == "holdout"
    assert exceptions[0].get("unreadable") is True
    assert exceptions[0].get("evidence") == "sale price and a higher price"

    sales = [
        row for row in scored_rows
        if row.get("evidence") == "sale price and a higher price"
    ]
    assert sales
    assert any(row["split"] == "holdout" for row in sales)
    assert all(row["verified"] is False for row in sales)
    members = [row for row in scored_rows if _member_override(row.get("evidence") or "")]
    assert members
    assert any(row["split"] == "holdout" for row in members)
    for row in members:
        hero = re.search(r"hero=([0-9.]+)", row["evidence"])
        assert hero is not None
        assert row["expected_price"] == hero.group(1)

    unread = [row for row in scored_rows if row.get("unreadable")]
    assert unread

    scored = score_rows(scored_rows)
    build = scored["groups"]["build"]
    holdout = scored["groups"]["holdout"]
    assert build["pct"] >= PASS_MARK
    assert holdout["pct"] >= PASS_MARK
    by_id = {row["id"]: row for row in scored["details"]}
    assert all(
        by_id[row["id"]]["match"] and by_id[row["id"]]["predicted_price"] is None
        for row in unread
    )
    _write_review(scored["details"])
    BASELINE.write_text(json.dumps({"groups": scored["groups"]}, indent=2) + "\n", encoding="utf-8")
    again = alert_for(scored, json.loads(BASELINE.read_text(encoding="utf-8")))
    assert again["alert"] is False
    sheet = REVIEW.read_text(encoding="utf-8")
    assert sheet.splitlines()[0].endswith("\tnote")
    assert "verified" in sheet.splitlines()[0]
    for row in scored_rows:
        line = next(line for line in sheet.splitlines() if line.startswith(row["id"] + "\t"))
        if row["id"] in VERIFIED_BY_ZENAS:
            assert "\tyes\t" in line
            assert line.endswith("\tverified by Zenas")
        else:
            assert "\tno\t" in line
            assert not line.endswith("\tverified by Zenas")
    assert GOLD.is_file()
