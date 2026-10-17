"""Weekly re-test for the Tiger change-alert and changed-page gold sets.

    python tests/tiger_alert_page/weekly.py

Prints the scores and exits 2 when a tracked score drops by more than 2 points
from gold/baseline.json. Other agents' gold sets are not run.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
if str(PACKAGE.parents[0]) not in sys.path:
    sys.path.insert(0, str(PACKAGE.parents[0]))

from tiger_alert_page.score import GOLD, score_all, tracked, weekly_alerts  # noqa: E402


def load_baseline() -> dict:
    return json.loads((GOLD / "baseline.json").read_text(encoding="utf-8"))


def write_review(report: dict, path: Path) -> None:
    rows = []
    for key in ("alerts", "alert_traps", "changed", "controls", "page_traps"):
        rows.extend(report[key]["rows"])
    alerts = report["alerts"]["summary"]
    changed = report["changed"]["summary"]
    lines = [
        "# Gold review",
        "",
        "Every gold answer is unverified until Zenas checks it. Scores are provisional.",
        "",
        "Change alerts, build set: caught "
        f"{alerts.get('build', {}).get('catch_pct')}% "
        f"({alerts.get('build', {}).get('catch')}/{alerts.get('build', {}).get('catch_n')}), "
        f"false alarms {alerts.get('build', {}).get('false_pct')}% "
        f"({alerts.get('build', {}).get('false')}/{alerts.get('build', {}).get('quiet_n')}).",
        "Change alerts, held out: caught "
        f"{alerts.get('heldout', {}).get('catch_pct')}% "
        f"({alerts.get('heldout', {}).get('catch')}/{alerts.get('heldout', {}).get('catch_n')}), "
        f"false alarms {alerts.get('heldout', {}).get('false_pct')}% "
        f"({alerts.get('heldout', {}).get('false')}/{alerts.get('heldout', {}).get('quiet_n')}).",
        "Changed pages, build set: "
        f"{changed.get('build', {}).get('ok_pct')}% can't read "
        f"({changed.get('build', {}).get('ok')}/{changed.get('build', {}).get('n')}), "
        f"guesses {changed.get('build', {}).get('guesses')}.",
        "Changed pages, held out: "
        f"{changed.get('heldout', {}).get('ok_pct')}% can't read "
        f"({changed.get('heldout', {}).get('ok')}/{changed.get('heldout', {}).get('n')}), "
        f"guesses {changed.get('heldout', {}).get('guesses')}.",
        "",
        "Columns: case id, what changed, expected outcome, actual outcome, verified.",
        "",
        "| case id | skill | split | source | what changed | expected outcome | actual outcome | verified |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        what = str(row.get("what") or "").replace("|", "/")
        lines.append(
            "| {id} | {skill} | {split} | {source} | {what} | {expected} | {actual} | {verified} |".format(
                id=row["id"],
                skill=row.get("skill") or "",
                split=row.get("split") or "",
                source=row.get("source") or "",
                what=what,
                expected=row.get("expected") or "",
                actual=row.get("actual") or "",
                verified=row.get("mark") or "no",
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    report = score_all()
    current = tracked(report)
    baseline = load_baseline()
    alerts = weekly_alerts(current, baseline)
    numbers = json.dumps(current, indent=2)
    print(numbers)
    if alerts:
        print("ALERT")
        for item in alerts:
            print(item)
        return 2
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
