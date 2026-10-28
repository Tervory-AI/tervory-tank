"""Durable chat build ownership, progress delivery and same-PR follow-ups.

The journal lives beside the installed code, outside the per-task secret tmpfs.
Only the service reads it. An interrupted edit is reported, never blindly replayed.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

from workers.github_api import ci_state, ready_body
from workers.issues import WorkerIssue
from workers.redact import redact

if TYPE_CHECKING:
    from workers.service import Service
    from workers.tank_status import TankControl

log = logging.getLogger("workers")


@dataclass(frozen=True)
class CommandTask(WorkerIssue):
    build_id: str
    tenant_id: str
    followups: tuple[dict[str, Any], ...] = ()

    @property
    def branch(self) -> str:
        return f"worker/build-{self.build_id}"

    def payload(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_payload(cls, data: dict[str, Any]) -> CommandTask:
        build_id = str(uuid.UUID(data["build_id"]))
        tenant_id = str(uuid.UUID(data["tenant_id"]))
        markdown = data.get("brief_markdown", data.get("body", ""))
        if not isinstance(markdown, str):
            raise RuntimeError("The confirmed build has no brief")
        title = next((line.strip().lstrip("# ") for line in markdown.splitlines() if line.strip()), "Chat build")
        return cls(number=uuid.UUID(build_id).int, title=title[:200] or "Chat build", body=markdown,
                   brief=f"Chat build {build_id}", build_id=build_id, tenant_id=tenant_id,
                   followups=tuple(data.get("followups", ())))


class CommandTasks:
    def __init__(self, service: Service) -> None:
        self.service = service
        self.directory = Path(service.settings.code_dir).parent / "command-builds"
        self.rows: dict[str, dict[str, Any]] = {}
        self.inflight: set[str] = set()
        self.loaded = False

    @property
    def control(self) -> TankControl:
        assert self.service.control is not None
        return self.service.control

    def save(self, row: dict[str, Any]) -> None:
        build_id = str(uuid.UUID(row["task"]["build_id"]))
        target = self.directory / f"{build_id}.json"
        temporary = target.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as stream:
            os.chmod(temporary, 0o600)
            json.dump(row, stream)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(target)
        fd = os.open(self.directory, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        self.rows[build_id] = row

    def load(self) -> None:
        if self.loaded:
            return
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.directory.chmod(0o700)
        for path in self.directory.glob("*.json"):
            row = json.loads(path.read_text(encoding="utf-8"))
            task = CommandTask.from_payload(row["task"])
            if path.stem != task.build_id:
                raise RuntimeError("Build journal identity mismatch")
            self.rows[task.build_id] = row
            if row["phase"] == "executing":
                # A model call or push may have happened before the restart.
                # Do not charge again or overwrite an uncertain branch.
                self.report(row, "failed", "Worker interrupted; inspect the build branch before starting more work.")
                row["phase"] = "finished"
                self.save(row)
        self.loaded = True

    def report(self, row: dict[str, Any], status: str, label: str, **fields: Any) -> None:
        outcome = row.get("outcome") or {}
        report = {"status": status, "step_label": redact(label)[:500],
                  "pr_url": outcome.get("pr_url"), **fields}
        # Each run's receipts are delivered in chunks (Tank accepts at most 100).
        receipts = outcome.get("ledger_ids") or []
        reports = [{**report, "ledger_ids": receipts[i:i + 100]} for i in range(0, len(receipts), 100)] or [report]
        if reports[-1] != row.get("last_report") or row.get("outbox"):
            row.setdefault("outbox", []).extend(reports)
        self.save(row)

    async def flush(self, row: dict[str, Any]) -> None:
        while row.get("outbox"):
            report = row["outbox"][0]
            await self.control.build_progress(row["task"]["build_id"], report)
            row["last_report"] = row["outbox"].pop(0)
            self.save(row)

    async def available(self) -> bool:
        from workers.service import update_pending
        service = self.service
        if len(service.inflight) + len(self.inflight) >= service.settings.max_tasks or update_pending(service.settings):
            return False
        return not await self.control.paused() and not update_pending(service.settings)

    def start(self, row: dict[str, Any], replies: list[dict[str, Any]]) -> None:
        build_id = row["task"]["build_id"]
        row["phase"] = "executing"
        self.save(row)
        self.inflight.add(build_id)
        self.service.jobs.append(asyncio.create_task(self.run(row, replies)))

    async def poll(self, token: str) -> None:
        self.load()  # Verify durable storage before claiming work.
        self.service.jobs[:] = [job for job in self.service.jobs if not job.done()]
        for build_id, row in list(self.rows.items()):
            if build_id in self.inflight:
                continue
            try:
                await self.flush(row)
                if row["phase"] == "finished":
                    continue
                if row["phase"] == "queued":
                    if await self.available():
                        self.start(row, [])
                    continue
                outcome = row["outcome"]
                pull = await self.service.github.pull(token, outcome["pr_number"])
                if pull.get("state") == "closed":
                    self.report(row, "done", "Pull request merged by a reviewer." if pull.get("merged") else "Pull request closed without merging.",
                                review_status="merged" if pull.get("merged") else "closed")
                    row["phase"] = "finished"
                    self.save(row)
                    await self.flush(row)
                    continue
                replies = await self.control.build_followups(build_id, row["cursor"])
                if replies and await self.available():
                    self.start(row, replies)
                    continue
                sha = pull.get("head", {}).get("sha")
                if not sha:
                    raise RuntimeError("Build pull request has no head revision")
                state = ci_state(await self.service.github.check_runs(token, sha),
                                 await self.service.github.combined_status(token, sha))
                if state == "green" and not replies and not row.get("error") and pull.get("draft") is True:
                    await self.service.github.mark_ready(token, node_id=pull["node_id"], number=pull["number"],
                                                         body=ready_body(f"Chat build {build_id}. Checks passed; ready for founder review. The worker does not merge."))
                labels = {"pending": "Pull request opened; waiting for checks.",
                          "red": "Checks failed. Reply here to fix this pull request.",
                          "green": "Changes ready for review; checks passed. Reply here for further changes."}
                # A failed follow-up remains visible until a newer edit succeeds.
                label = row.get("error") or ("Follow-up queued; waiting for worker capacity." if replies else labels[state])
                self.report(row, "awaiting_review", label, ci_status={"green": "passed", "red": "failed", "pending": "pending"}[state],
                            review_status="pending")
                await self.flush(row)
            except (RuntimeError, OSError, ValueError, KeyError, httpx.HTTPError) as exc:
                log.warning("build %s polling failed: %s", build_id, redact(str(exc))[:300])
        if await self.available():
            build = await self.control.next_build()
            if build is not None:
                task = CommandTask.from_payload(build)
                row = {"task": task.payload(), "phase": "queued", "cursor": 0, "outbox": []}
                self.save(row)
                # Re-check the updater/pause after the claim. A claimed row stays in
                # the journal until capacity is available; it is never discarded.
                if await self.available():
                    self.start(row, [])

    async def run(self, row: dict[str, Any], replies: list[dict[str, Any]]) -> None:
        task = CommandTask.from_payload(row["task"])
        task = replace(task, followups=tuple(replies))
        try:
            self.report(row, "running", "Applying your follow-up to the same pull request." if replies else "Building your confirmed change.",
                        ci_status="pending", review_status="pending")
            await self.flush(row)
            token = await self.service._token()
            outcome = await self.service.launcher.run(replace(self.service.settings, tenant_id=task.tenant_id), task, token)
            row["outcome"] = asdict(outcome) if outcome.pr_url else {**(row.get("outcome") or {}), "ledger_ids": outcome.ledger_ids}
            # A returned result means this batch was attempted, even when it failed.
            # Do not loop forever charging for the same failed reply.
            row["cursor"] = max([row["cursor"], *[int(reply["followup_id"]) for reply in replies]])
            if outcome.status == "failed" or not outcome.pr_url:
                raise RuntimeError(outcome.detail or "The build did not produce a pull request")
            row.pop("error", None)
            row["phase"] = "idle"
            self.report(row, "awaiting_review", "Pull request updated; waiting for checks." if replies else "Pull request opened; waiting for checks.",
                        ci_status="pending", review_status="pending")
        except (RuntimeError, OSError, ValueError, httpx.HTTPError) as exc:
            error = f"Build stopped: {redact(str(exc))[:400]}"
            row["error"] = error
            has_pr = bool((row.get("outcome") or {}).get("pr_url"))
            row["phase"] = "idle" if has_pr else "finished"
            row["cursor"] = max([row["cursor"], *[int(reply["followup_id"]) for reply in replies]])
            self.report(row, "awaiting_review" if has_pr else "failed", error)
            log.warning("build %s: %s", task.build_id, error)
        finally:
            try:
                self.save(row)
                await self.flush(row)
            except (RuntimeError, OSError) as exc:
                log.warning("build %s progress pending: %s", task.build_id, redact(str(exc)))
            finally:
                self.inflight.discard(task.build_id)
