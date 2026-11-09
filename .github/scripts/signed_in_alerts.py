"""One GitHub issue per failed signed-in page, closed when the page recovers.

Reads results.json from ops/signed_in_check.mjs. Titles are "Signed-in check failed: <page>",
label incident, so a page never gets a second open issue. A page that passes again gets a
comment and its issue is closed. A newly opened issue also sends one push to the founder
when the repo secret FOUNDER_PUSH_URL is set (an ntfy-style URL that takes a plain-text
POST); without it no push is sent. Never prints a token, a URL secret or a page body.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from collections.abc import Callable
from pathlib import Path

PREFIX = "Signed-in check failed: "


def body_for(row: dict, run: str, artifact: str) -> str:
    lines = [f"Signed-in check failed for **{row['id']}** ({row['url']}).", "",
             f"[Run]({run})", f"[Screenshots and results]({artifact or run})", ""]
    lines += [f"- {reason}" for reason in row["reasons"]]
    if row.get("screenshot"):
        lines.append(f"\nScreenshot in the linked artifact: `{row['screenshot']}`")
    return "\n".join(lines)


def sync(rows: list[dict], github, run: str, artifact: str, push: Callable[[str], None]) -> list[str]:
    """Open, update or close issues for rows. Returns what was done, for the log."""
    done: list[str] = []
    github.ensure_label()
    opened = github.open_incidents()
    for row in rows:
        title = PREFIX + row["id"]
        current = opened.get(title)
        if row["passed"]:
            if current is not None:
                number = int(current["number"])
                github.comment(number, f"Passed again: the page shows real content. Closing. [Run]({run})")
                github.close(number)
                done.append(f"closed #{number} {title}")
            continue
        # Same failure reasons keep the issue as it is; the run link alone is not news.
        body = body_for(row, run, artifact)
        reasons = "\n".join(f"- {reason}" for reason in row["reasons"])
        if current is None:
            number = github.open_issue(title, body)
            opened[title] = {"number": number, "body": body}
            done.append(f"opened #{number} {title}")
            push(f"{row['id']} failed the signed-in check: {'; '.join(row['reasons'])[:150]}")
        elif reasons not in str(current.get("body") or ""):
            number = int(current["number"])
            github.set_body(number, body)
            github.comment(number, "Still failing, for a new reason:\n" + reasons)
            done.append(f"updated #{number} {title}")
        else:
            done.append(f"already open #{current['number']} {title}")
    return done


def push_to(url: str) -> Callable[[str], None]:
    def send(message: str) -> None:
        if not url.startswith("https://"):
            return
        request = urllib.request.Request(url, data=message.encode(), method="POST",
                                         headers={"Title": "Tervory signed-in check", "User-Agent": "tervory-live-check"})
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                print(f"push: HTTP {response.status}", flush=True)
        except OSError as exc:
            print(f"::warning::push not sent ({type(exc).__name__})", flush=True)
    return send


def main() -> int:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from watchdog import GitHub

    report = Path(os.environ["SIGNED_IN_OUTPUT"]) / "results.json"
    if not report.exists():
        print("::error::Signed-in check produced no results; see the failed step log")
        return 1
    rows = json.loads(report.read_text())
    run = f"{os.environ['GITHUB_SERVER_URL']}/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
    url = os.environ.get("FOUNDER_PUSH_URL", "").strip()
    if not url:
        print("push: FOUNDER_PUSH_URL is not set; issues only", flush=True)
    github = GitHub(os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_TOKEN"])
    for line in sync(rows, github, run, os.environ.get("ARTIFACT_URL", ""), push_to(url)):
        print(line, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
