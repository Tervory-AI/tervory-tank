"""100 product pages. 20% held out of the score used while building.

Gold answers are unverified until a person checks them. Scores are provisional.
"""

from __future__ import annotations

import json

from weekly import BASELINE, GOLD, HERE, alert_for, load_rows, score_rows

REVIEW = HERE / "gold" / "GOLD_REVIEW.tsv"
PASS_MARK = 98.0


def _write_review(details: list[dict]) -> None:
    lines = ["page id\tlayout\texpected price\tpredicted price\tmatch\tverified\tsource\tsplit"]
    by_id = {row["id"]: row for row in load_rows()}
    for row in details:
        origin = by_id[row["id"]].get("source", "")
        match = "yes" if row["match"] else "no"
        lines.append(
            "\t".join([
                row["id"],
                str(row["layout"]),
                str(row["expected_price"]),
                str(row["predicted_price"] or ""),
                match,
                "no",
                origin,
                row["split"],
            ])
        )
    REVIEW.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_price_read_gold_set() -> None:
    rows = load_rows()
    priced = [row for row in rows if row.get("expected_price")]
    assert len(priced) >= 100
    layouts = {row["layout"] for row in priced}
    assert len(layouts) >= 8
    assert all(row["verified"] is False for row in priced)
    splits = {row["split"] for row in priced}
    assert splits == {"build", "holdout"}
    holdout_n = sum(row["split"] == "holdout" for row in priced)
    # About 20% is kept back. Allow a little rounding.
    assert 0.15 <= holdout_n / len(priced) <= 0.25
    sources = {row["source"] for row in priced}
    assert "existing" in sources
    assert "live" in sources or "synthetic" in sources

    scored = score_rows(priced)
    build = scored["groups"]["build"]
    holdout = scored["groups"]["holdout"]
    assert build["pct"] >= PASS_MARK
    assert holdout["pct"] >= PASS_MARK
    _write_review(scored["details"])
    BASELINE.write_text(json.dumps({"groups": scored["groups"]}, indent=2) + "\n", encoding="utf-8")
    again = alert_for(scored, json.loads(BASELINE.read_text(encoding="utf-8")))
    assert again["alert"] is False
    assert REVIEW.is_file()
    assert "verified" in REVIEW.read_text(encoding="utf-8").splitlines()[0]
    assert GOLD.is_file()
