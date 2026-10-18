"""Screenshot saved HTML locally. Does not open the live site."""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import time

from weekly import HERE, html_for, load_rows

SHOTS = HERE / "gold" / "shots"
CHROME = "google-chrome"


def _local_html(page_id: str, html: str) -> str:
    """Drop external links so the browser does not fetch the store again."""
    html = re.sub(r"\s(?:src|href)=[\"']https?://[^\"']+[\"']", "", html, flags=re.I)
    banner = (
        "<div style=\"position:fixed;top:0;left:0;right:0;z-index:99999;"
        "background:#001840;color:#fff;font:14px/1.4 sans-serif;padding:8px 12px\">"
        f"{page_id}</div><div style=\"height:36px\"></div>"
    )
    if "<body" in html.lower():
        return re.sub(r"(<body[^>]*>)", r"\1" + banner, html, count=1, flags=re.I)
    return banner + html


def shoot(rows: list[dict] | None = None) -> int:
    SHOTS.mkdir(parents=True, exist_ok=True)
    rows = rows if rows is not None else load_rows()
    done = 0
    for row in rows:
        target = SHOTS / f"{row['id']}.png"
        local = _local_html(row["id"], html_for(row))
        tmp = SHOTS / f".{row['id']}.html"
        tmp.write_text(local, encoding="utf-8")
        target.unlink(missing_ok=True)
        # Chrome writes the png, then often stays open. Stop it once the file is there.
        proc = subprocess.Popen(
            [
                CHROME,
                "--headless=new",
                "--disable-gpu",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--hide-scrollbars",
                "--virtual-time-budget=1500",
                "--window-size=1100,1400",
                f"--screenshot={target}",
                tmp.resolve().as_uri(),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            if target.is_file() and target.stat().st_size > 1000:
                time.sleep(0.3)
                break
            if proc.poll() is not None:
                break
            time.sleep(0.2)
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=5)
        tmp.unlink(missing_ok=True)
        if not target.is_file() or target.stat().st_size < 1000:
            raise RuntimeError(f"screenshot missing for {row['id']}")
        done += 1
        print(f"shot {row['id']}", flush=True)
    return done


if __name__ == "__main__":
    print(json.dumps({"shots": shoot()}))
