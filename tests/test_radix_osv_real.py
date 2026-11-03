"""GHOST-2 follow-up: Radix bakes the real OSV PyPI + npm data at build, reads it offline.

No network and no database. The real-data test runs when RADIX_OSV_REAL points at a baked
osv.sqlite (or the image's /opt/osv/osv.sqlite exists); otherwise it is skipped.
"""

from __future__ import annotations

import io
import json
import os
import sqlite3
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RADIX = ROOT / "agents" / "radix"
sys.path.insert(0, str(ROOT / "agents" / "_chassis"))
sys.path.insert(0, str(RADIX))

import osv_bake  # noqa: E402
from scanlib import dependencies  # noqa: E402

FIXTURES = RADIX / "scanlib" / "osv"


def _zip(path: Path, docs: list[dict]) -> Path:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        for doc in docs:
            archive.writestr(doc["id"] + ".json", json.dumps(doc))
    path.write_bytes(buf.getvalue())
    return path


def _adv(ident: str, eco: str, name: str, ranges: list[list[dict]], **extra) -> dict:
    doc = {"id": ident, "affected": [{"package": {"ecosystem": eco, "name": name},
                                       "ranges": [{"type": "ECOSYSTEM", "events": r} for r in ranges]}]}
    doc.update(extra)
    return doc


@pytest.fixture()
def baked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    fixtures = [json.loads(p.read_text()) for p in sorted(FIXTURES.glob("*.json"))]
    pypi = [d for d in fixtures if d["affected"][0]["package"]["ecosystem"] == "PyPI"] + [
        _adv("GHSA-only-in-db-0001", "PyPI", "Some_Pkg", [[{"introduced": "0"}, {"fixed": "2.0"}]],
             aliases=["PYSEC-2099-1"], database_specific={"severity": "MODERATE"}),
        _adv("PYSEC-2099-1", "PyPI", "some-pkg", [[{"introduced": "0"}, {"fixed": "2.0"}]], aliases=["GHSA-only-in-db-0001"]),
        _adv("GHSA-withdrawn-0001", "PyPI", "some-pkg", [[{"introduced": "0"}]], withdrawn="2026-01-01T00:00:00Z"),
    ]
    npm = [d for d in fixtures if d["affected"][0]["package"]["ecosystem"] == "npm"] + [
        _adv("MAL-2099-1", "npm", "evil-pkg", [[{"introduced": "0"}]]),
        {"id": "GHSA-list-only-0001", "affected": [{"package": {"ecosystem": "npm", "name": "listed"},
                                                     "versions": ["1.0.0", "1.0.1"]}]},
    ]
    out = tmp_path / "osvdir"
    out.mkdir()
    report = osv_bake.bake(out / "osv.sqlite",
                           {"PyPI": _zip(tmp_path / "PyPI.zip", pypi), "npm": _zip(tmp_path / "npm.zip", npm)},
                           floors={"pypi": 1, "npm": 1})
    assert report["PyPI"]["records"] == len(pypi) and report["npm"]["records"] == len(npm)
    monkeypatch.setenv("RADIX_OSV_DIR", str(out))
    return out


def test_baked_database_is_used_and_still_finds_the_47_advisories(baked: Path) -> None:
    files = [
        ("package.json", '{"dependencies": {"minimist": "1.2.5", "evil-pkg": "9.9.9", "listed": "1.0.1"}}\n'),
        ("requirements.txt", "PyYAML==5.3.1\nsome.pkg==1.5\n"),
    ]
    found = {(f["package"], f["advisory"]): f for f in dependencies.scan_files(files)}
    assert ("minimist", "GHSA-xvch-5gv4-984h") in found
    assert ("pyyaml", "GHSA-8q59-q68h-6hv4") in found
    # Only in the baked database, PEP 503 name match, and its PYSEC alias is not repeated.
    assert found[("some-pkg", "GHSA-only-in-db-0001")]["severity"] == "medium"
    assert ("some-pkg", "PYSEC-2099-1") not in found
    assert ("some-pkg", "GHSA-withdrawn-0001") not in found
    assert found[("evil-pkg", "MAL-2099-1")]["severity"] == "critical"
    assert ("listed", "GHSA-list-only-0001") in found
    clean = [("package.json", '{"dependencies": {"minimist": "1.2.6", "listed": "1.0.2"}}\n'),
             ("requirements.txt", "PyYAML==5.4\nsome-pkg==2.0\n")]
    assert dependencies.scan_files(clean) == []


def test_scan_reads_only_named_packages_not_the_whole_database(baked: Path) -> None:
    # load_advisories reads the small JSON files only; the sqlite file is queried per package.
    assert {row["advisory"] for row in dependencies.load_advisories()} <= {p.stem for p in FIXTURES.glob("*.json")}
    assert dependencies.databases() == [baked / "osv.sqlite"]


def test_bake_refuses_truncated_or_incomplete_exports(tmp_path: Path) -> None:
    small = _zip(tmp_path / "npm.zip", [_adv("GHSA-x", "npm", "a", [[{"introduced": "0"}]])])
    with pytest.raises(SystemExit, match="truncated"):
        osv_bake.bake(tmp_path / "a.sqlite", {"npm": small})
    with pytest.raises(SystemExit, match="GHSA-xvch-5gv4-984h missing"):
        osv_bake.bake(tmp_path / "b.sqlite", {"npm": small}, floors={"npm": 1})


def test_osv_range_semantics() -> None:
    two = [{"introduced": "0"}, {"fixed": "1.0"}, {"introduced": "1.4"}, {"fixed": "1.6"}]
    assert dependencies._in_range("0.9", two) == (True, "1.0")
    assert dependencies._in_range("1.2", two) == (False, "")
    assert dependencies._in_range("1.5", two) == (True, "1.6")
    assert dependencies._in_range("1.6", two) == (False, "")
    last = [{"introduced": "0"}, {"last_affected": "2.0"}]
    assert dependencies._in_range("2.0", last)[0] and not dependencies._in_range("2.0.1", last)[0]
    fixed = [{"introduced": "1.0.0"}, {"fixed": "1.2.6"}]
    assert dependencies._in_range("1.2.6-beta.1", fixed)[0]
    assert dependencies._in_range("1.2.6rc1", fixed)[0]
    assert not dependencies._in_range("1.2.6", fixed)[0]
    assert not dependencies._in_range("1.2.6.post1", fixed)[0]
    assert not dependencies._in_range("0.9.9", fixed)[0]


DOCKERFILE = """FROM node:20
ARG MINI=1.2.5
ENV YAML_VERSION=5.3.1
# RUN pip install commented==1.0
RUN npm install -g minimist@${MINI} @scope/pkg@2.0.0 left-pad \\
    && pip3 install --no-cache-dir "PyYAML==${YAML_VERSION}" unknown==${NOT_SET} \\
    && /opt/venv/bin/pip install -r requirements.txt
RUN python -m pip install flask==2.0.1 && yarn add lodash@4.17.20
"""


def test_dockerfile_pins_are_read() -> None:
    rows = dependencies._packages_from_dockerfile(DOCKERFILE)
    assert ("npm", "minimist", "1.2.5", 5) in rows
    assert ("npm", "@scope/pkg", "2.0.0", 5) in rows
    assert ("PyPI", "PyYAML", "5.3.1", 5) in rows
    assert ("PyPI", "flask", "2.0.1", 8) in rows
    assert ("npm", "lodash", "4.17.20", 8) in rows
    assert not any(name in {"left-pad", "unknown", "commented"} for _e, name, _v, _l in rows)
    found = dependencies.scan_files([("docker/Dockerfile.web", DOCKERFILE)])
    assert {(f["package"], f["advisory"], f["line"]) for f in found} >= {
        ("minimist", "GHSA-xvch-5gv4-984h", 5), ("pyyaml", "GHSA-8q59-q68h-6hv4", 5)}


def test_dockerfiles_are_collected_from_a_tree(tmp_path: Path) -> None:
    (tmp_path / "svc").mkdir()
    (tmp_path / "svc" / "Dockerfile").write_text(DOCKERFILE)
    (tmp_path / "web.dockerfile").write_text("RUN pip install pyyaml==5.3.1\n")
    (tmp_path / "notes.txt").write_text("RUN pip install pyyaml==5.3.1\n")
    names = [path for path, _text in dependencies.iter_manifests(tmp_path)]
    assert names == ["svc/Dockerfile", "web.dockerfile"]
    radix = dependencies._packages_from_dockerfile((RADIX / "Dockerfile").read_text())
    assert ("PyPI", "semgrep", "1.182.1", ) == radix[0][:3]


def test_osv_is_fetched_only_at_build_and_the_seal_is_unchanged() -> None:
    text = (RADIX / "Dockerfile").read_text(encoding="utf-8")
    bake_stage, final = text.split("\nFROM python:3.12-slim\n", 1)
    assert "FROM python:3.12-slim AS osv" in bake_stage
    assert "https://osv-vulnerabilities.storage.googleapis.com" in bake_stage
    assert "ADD ${OSV_BUCKET}/PyPI/all.zip" in bake_stage and "ADD ${OSV_BUCKET}/npm/all.zip" in bake_stage
    assert "osv-vulnerabilities" not in final and "all.zip" not in final
    assert "COPY --from=osv /out/osv.sqlite /opt/osv/osv.sqlite" in final
    assert "curl" not in final.split("CMD [", 1)[1]
    bake = (RADIX / "osv_bake.py").read_text(encoding="utf-8")
    for word in ("urllib", "socket", "requests", "httpx", "http.client"):
        assert f"import {word}" not in bake and f"from {word}" not in bake
    engine = (RADIX / "scanlib" / "dependencies.py").read_text(encoding="utf-8")
    assert "mode=ro" in engine
    for word in ("urllib", "socket", "requests", "httpx"):
        assert f"import {word}" not in engine
    compose = (RADIX / "docker-compose.yml").read_text(encoding="utf-8")
    assert compose.startswith("# coolify: raw compose")
    assert "ports:" not in compose
    # #426 raised the room cap to 1 GiB for ZAP (JVM capped at 512 MiB).
    assert "mem_limit: 1g" in compose
    assert "proxy-link:\n    internal: true" in compose


def _real_db() -> Path | None:
    raw = os.environ.get("RADIX_OSV_REAL", "").strip()
    for candidate in ([Path(raw)] if raw else []) + [Path("/opt/osv/osv.sqlite")]:
        if candidate.is_file():
            return candidate
    return None


@pytest.mark.skipif(_real_db() is None, reason="no baked real OSV osv.sqlite on this machine")
def test_real_osv_export_is_complete_and_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _real_db()
    assert db is not None
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    meta = {row[0]: row[1] for row in conn.execute("SELECT ecosystem, records FROM meta")}
    conn.close()
    assert meta["PyPI"] >= osv_bake.FLOORS["pypi"] and meta["npm"] >= osv_bake.FLOORS["npm"]
    monkeypatch.setenv("RADIX_OSV_DIR", str(db.parent))
    found = dependencies.scan_files([
        ("package.json", '{"dependencies": {"minimist": "1.2.5"}}\n'),
        ("requirements.txt", "PyYAML==5.3.1\n"),
    ])
    ids = {f["advisory"] for f in found}
    assert {"GHSA-xvch-5gv4-984h", "GHSA-8q59-q68h-6hv4"} <= ids
    assert dependencies.scan_files([("requirements.txt", "PyYAML==6.0.2\n")]) == []
