"""Clone the repo, run Aider through Tank, push a worker branch, open a draft pull request."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx

from workers.github_api import GitHub
from workers.issues import WorkerIssue
from workers.proxy import forward_chat, models_document, read_key
from workers.redact import redact
from workers.settings import from_mapping
from workers.task_run import (
    Outcome,
    aider_argv,
    branch_commands,
    changed_paths,
    commit_paths,
    draft_for,
    existing_files,
    instruction,
    load_rules,
    publish_commands,
)

ROOT = Path("/work/repo")


def _run(argv: list[str], cwd: Path) -> str:
    completed = subprocess.run(argv, cwd=cwd, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if completed.returncode != 0:
        tail = redact(completed.stdout or "")[-400:]
        raise RuntimeError(f"command failed: {argv[0]} {tail}")
    return completed.stdout or ""


def _serve_proxy(costs: list[float], ledger_ids: list[str]) -> None:
    settings = from_mapping(dict(os.environ))
    issue = int(os.environ["WORKER_ISSUE"])
    key = read_key(os.environ["TANK_KEY_FILE"])

    def sync_send(url: str, payload: dict[str, object], tank_key: str) -> dict[str, object]:
        with httpx.Client(timeout=120, follow_redirects=False) as client:
            response = client.post(url, json=payload, headers={"X-Tank-Key": tank_key})
        response.raise_for_status()
        data = response.json()
        costs.append(float(data.get("cost_usd") or 0))
        ledger = data.get("ledger_id")
        if isinstance(ledger, str) and ledger:
            ledger_ids.append(ledger)
        return data

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, _format: str, *_args: object) -> None:
            return

        def _json(self, status: int, payload: dict[str, object]) -> None:
            raw = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self) -> None:
            if self.path.split("?", 1)[0].rstrip("/") == "/v1/models":
                self._json(200, models_document())
                return
            self._json(404, {"error": "not found"})

        def do_POST(self) -> None:
            if self.path.split("?", 1)[0] != "/v1/chat/completions":
                self._json(404, {"error": "not found"})
                return
            length = int(self.headers.get("Content-Length") or "0")
            if length > 2_000_000:
                self._json(413, {"error": "too large"})
                return
            try:
                body = json.loads(self.rfile.read(length) or b"{}")

                async def send(url: str, payload: dict[str, object], tank_key: str) -> dict[str, object]:
                    return await asyncio.to_thread(sync_send, url, payload, tank_key)

                result = asyncio.run(forward_chat(body, settings, issue=issue, key=key, send=send))
            except Exception as exc:  # noqa: BLE001 — Aider needs an error, never a secret
                self._json(502, {"error": redact(str(exc))[:300]})
                return
            self._json(200, result)

    server = ThreadingHTTPServer(("127.0.0.1", settings.proxy_port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()


def main() -> int:
    started = time.monotonic()
    costs: list[float] = []
    ledger_ids: list[str] = []
    issue = WorkerIssue(
        number=int(os.environ["WORKER_ISSUE"]),
        title=os.environ.get("WORKER_TITLE") or "Worker task",
        body=os.environ["WORKER_BRIEF"],
        brief=os.environ["WORKER_BRIEF"],
    )
    branch = os.environ["WORKER_BRANCH"]
    try:
        _serve_proxy(costs, ledger_ids)
        Path("/work").mkdir(parents=True, exist_ok=True)
        for argv in branch_commands(os.environ["WORKER_REPO"], str(ROOT), branch)[:1]:
            _run(argv, Path("/work"))
        for argv in branch_commands(os.environ["WORKER_REPO"], str(ROOT), branch)[1:]:
            _run(argv, ROOT)
        rules = load_rules(ROOT / issue.brief)
        message = Path("/tmp/worker-message.txt")
        message.write_text(instruction(issue, rules), encoding="utf-8")
        _run(aider_argv(str(message), existing_files(ROOT, rules), proxy_port=int(os.environ.get("WORKER_PROXY_PORT", "8765"))), ROOT)
        committed = _run(["git", "diff", "--name-only", "main...HEAD"], ROOT)
        unstaged = _run(["git", "diff", "--name-only", "HEAD"], ROOT)
        untracked = _run(["git", "ls-files", "--others", "--exclude-standard"], ROOT)
        changed = changed_paths(committed + "\n" + unstaged, untracked)
        commit_paths(changed, rules)
        dirty = changed_paths(unstaged, untracked)
        if dirty:
            for argv in publish_commands(branch, dirty)[:-1]:
                _run(argv, ROOT)
        _run(publish_commands(branch, dirty or changed)[-1], ROOT)
        sha = _run(["git", "rev-parse", "HEAD"], ROOT).strip()
        token = Path(os.environ["GITHUB_TOKEN_FILE"]).read_text(encoding="utf-8").strip()

        async def open_draft() -> dict[str, object]:
            async with httpx.AsyncClient(timeout=60) as client:
                return await GitHub(os.environ["WORKER_REPO"], client).create_draft(
                    token,
                    branch=branch,
                    title=issue.title,
                    body=draft_for(issue),
                )

        created = asyncio.run(open_draft())
        outcome = Outcome(
            status="draft",
            pr_url=str(created.get("html_url") or ""),
            pr_number=int(created["number"]),
            node_id=str(created.get("node_id") or ""),
            sha=sha,
            minutes=(time.monotonic() - started) / 60,
            cost_usd=sum(costs),
            ledger_ids=ledger_ids,
        )
    except Exception as exc:  # noqa: BLE001 — the service reads one result line and discards the container
        outcome = Outcome(status="failed", detail=redact(str(exc))[:400], minutes=(time.monotonic() - started) / 60, cost_usd=sum(costs), ledger_ids=ledger_ids)
    print(outcome.line(), flush=True)
    return 0 if outcome.status == "draft" else 1


if __name__ == "__main__":
    raise SystemExit(main())
