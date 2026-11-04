"""Offline, read-only checks for the PR436 documentation reconciliation."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import re
import struct
import zlib


def validate() -> dict:
    here = Path(__file__).resolve().parent
    repo = here.parents[2]
    manifest = json.loads((here / "RECONCILIATION-20261104.json").read_text())
    canonical = (here / "SPEC.md").read_bytes()
    prefix = canonical[:manifest["main_crm_prefix_bytes"]]
    assert hashlib.sha256(prefix).hexdigest() == manifest["main_crm_prefix_sha256"]
    case = (here.parent / "case-studies/SPEC.md").read_bytes()
    assert hashlib.sha256(case).hexdigest() == manifest["case_spec_sha256"]
    for path, digest in manifest["archived_payloads"].items():
        payload = (here / path).read_bytes().split(b"<!-- BEGIN UNALTERED PR436 SNAPSHOT -->\n", 1)[1]
        assert hashlib.sha256(payload).hexdigest() == digest, path

    pngs = 0
    for item in manifest["evidence"]:
        data = (here / item["path"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == item["sha256"], item["path"]
        if not item["path"].endswith(".png"):
            continue
        assert data[:8] == b"\x89PNG\r\n\x1a\n", item["path"]
        width, height = struct.unpack(">II", data[16:24])
        assert (width, height) == (item["width"], item["height"])
        assert width > 0 and height > 0
        offset = 8
        while offset < len(data):
            size = int.from_bytes(data[offset:offset + 4], "big")
            kind = data[offset + 4:offset + 8]
            content = data[offset + 8:offset + 8 + size]
            crc = int.from_bytes(data[offset + 8 + size:offset + 12 + size], "big")
            assert zlib.crc32(kind + content) & 0xFFFFFFFF == crc, item["path"]
            offset += 12 + size
            if kind == b"IEND":
                break
        assert kind == b"IEND" and offset == len(data)
        pngs += 1
    assert pngs == 10

    folder = here / "evidence/2026-11-03-fix4"
    node_syntax = re.compile(r"I?\d+:\d+(?:;\d+:\d+)*")
    counts = {}
    for filename, count in [("changed-nodes.csv", 10981), ("created-nodes.csv", 1120)]:
        with (folder / filename).open(newline="") as stream:
            records = list(csv.DictReader(stream))
        ids = [row["node_id"] for row in records]
        assert len(ids) == len(set(ids)) == count, filename
        assert all(node_syntax.fullmatch(ident) for ident in ids), filename
        assert all(row["operations"] for row in records)
        counts[filename] = count
    checks = json.loads((folder / "final-checks.json").read_text())
    exceptions = json.loads((folder / "spacing-exceptions.json").read_text())
    fields = ("id", "property", "value")
    assert [tuple(row[k] for k in fields) for row in checks["problems"]["spacing"]] == [tuple(row[k] for k in fields) for row in exceptions]
    assert len(exceptions) == 16 and all(row["value"] == 104 for row in exceptions)
    assert checks["status"] == "Changed after approval, awaiting founder"
    for key in ["darkSurfaces", "shortMenuTargets", "recordCorners", "inputBorders", "redNonDelete", "headerFit"]:
        assert not checks["problems"][key], key
    words = json.loads((folder / "new-words.json").read_text())
    assert len(words) == 15
    assert all(row["status"] == "Changed after approval, awaiting founder" for row in words)
    assert len({row["after"] for row in words}) == 15

    # These inherited main references are verified by pinned Git blob IDs in
    # the manifest; the isolated source-head checkout need not contain them.
    inherited = {(repo / path).resolve() for path in manifest["canonical_inputs"]}
    docs = [here / "RECONCILIATION-20261104.md", folder / "README.md"]
    appendix = canonical[manifest["main_crm_prefix_bytes"]:].decode()
    checked_links = 0
    for doc, content in [(p, p.read_text()) for p in docs] + [(here / "SPEC.md", appendix)]:
        assert not re.search(r"^(<<<<<<<|=======|>>>>>>>)", content, re.M), doc
        for target in re.findall(r"\]\(([^)]+)\)", content):
            if target.startswith(("http://", "https://", "#", "/")):
                continue
            path = (doc.parent / target.split("#", 1)[0]).resolve()
            assert path.exists() or path in inherited, (doc, target)
            checked_links += 1
    for text in [canonical.decode(), (here / "RECONCILIATION-20261104.md").read_text()]:
        for ident in re.findall(r"node-id=(\d+-\d+)", text):
            assert node_syntax.fullmatch(ident.replace("-", ":"))
    return {
        "result": "pass",
        "pr": 436,
        "source_head": manifest["source_head"],
        "main_snapshot": manifest["main_snapshot"],
        "canonical_crm_prefix": "byte-identical",
        "canonical_case_study": "byte-identical",
        "historical_snapshots": 2,
        "png_files_crc_and_hash_verified": pngs,
        "csv_unique_ids": counts,
        "pending_proposed_labels": len(words),
        "declared_spacing_exceptions": len(exceptions),
        "relative_references_checked": checked_links,
        "live_canvas_writes": 0,
        "application_tests_run": False,
    }


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2))
