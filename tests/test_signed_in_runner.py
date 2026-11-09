"""ops/signed_in_check.mjs end to end against the saved fixtures on 127.0.0.1.

Needs Playwright for Node, so it runs in signed-in-check.yml (like test_live_check.py runs
in live-check.yml), not in the offline suite. Signed-out mode: no account is used.
"""
from __future__ import annotations

import http.server
import json
import os
import subprocess
import tempfile
import threading
import unittest
from functools import partial
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "signed_in_fixtures"


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self) -> None:
        name = self.path.strip("/") + ".html"
        path = FIXTURES / name
        if not path.is_file():
            self.send_error(404)
            return
        body = path.read_bytes()
        self.send_response(503 if name.startswith("service-unavailable") else 200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: object) -> None:
        return None


class RunnerTest(unittest.TestCase):
    def test_runner_fails_bad_pages_passes_good_and_saves_screenshots(self) -> None:
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, directory=str(FIXTURES)))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{server.server_address[1]}"
        rig = {"expect": ["What's built", "Next step"],
               "required": [{"name": "Ask Rig answers", "selector": '[aria-label="Ask Rig"] .thread'}]}
        pages = {"signIn": base + "/sign-in", "pages": [
            {"id": "good", "url": base + "/good-rig-overview", **rig},
            {"id": "blank", "url": base + "/blank-next-step", **rig},
            {"id": "down", "url": base + "/service-unavailable"},
        ]}
        try:
            with tempfile.TemporaryDirectory() as tmp:
                config = Path(tmp) / "pages.json"
                config.write_text(json.dumps(pages))
                out = Path(tmp) / "out"
                env = {k: v for k, v in os.environ.items() if k not in ("LIVE_CHECK_EMAIL", "LIVE_CHECK_PASSWORD")}
                done = subprocess.run(["node", str(ROOT / "ops/signed_in_check.mjs"), "--signed-out",
                                       "--pages", str(config), "--output", str(out)],
                                      capture_output=True, text=True, timeout=180, env=env, check=False)
                self.assertEqual(done.returncode, 1, done.stderr[-2000:])
                rows = {row["id"]: row for row in json.loads((out / "results.json").read_text())}
                self.assertEqual(list(rows), ["good", "blank", "down"])
                self.assertTrue(rows["good"]["passed"])
                self.assertIsNone(rows["good"]["screenshot"])
                self.assertIn("Empty section: Next step", rows["blank"]["reasons"])
                self.assertIn("Empty: Ask Rig answers", rows["blank"]["reasons"])
                self.assertEqual(rows["down"]["reasons"][0], "HTTP 503")
                for failed in ("blank", "down"):
                    self.assertTrue((out / rows[failed]["screenshot"]).is_file())
                summary = (out / "summary.md").read_text()
                self.assertIn("| good | PASS | Real content |", summary)
                self.assertIn("| down | FAIL | HTTP 503", summary)
        finally:
            server.shutdown()


if __name__ == "__main__":
    unittest.main()
