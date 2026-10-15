"""RX1: Radix code scans. No database and no network."""

from __future__ import annotations

import base64
import io
import json
import socket
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "_chassis"))
sys.path.insert(0, str(ROOT / "agents" / "radix"))

from scanlib import dependencies, orchestrate, secrets, static, store  # noqa: E402

FIXTURE = "tvfy-example-fixture-key-0001"
TENANT = "11111111-1111-1111-1111-111111111111"
SCAN = "22222222-2222-2222-2222-222222222222"
INJECTION = "def lookup(cur, name):\n    cur.execute(\"SELECT * FROM users WHERE name = '%s'\" % name)\n"
CLEAN_SQL = "def lookup(cur, name):\n    cur.execute(\"SELECT * FROM users WHERE name = %s\", (name,))\n"


class Files:
    def __init__(self, data: dict[str, bytes] | None = None) -> None:
        self.data = data or {}

    def read_file(self, tenant_id: str, name: str) -> bytes:
        assert tenant_id == TENANT
        return self.data[name]


class Ctx:
    def __init__(self, source: str, ref: str = "main", tenant_id: str = TENANT) -> None:
        self.agent = "radix"
        self.tenant_id = tenant_id
        self.job_id = SCAN
        self.kind = "scan"
        self.input = {"tenant_id": tenant_id, "source": source, "ref": ref}
        self.files = Files()


def _tar(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, text in files.items():
            payload = text.encode()
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            tar.addfile(info, io.BytesIO(payload))
    return buf.getvalue()


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _dirty() -> dict[str, str]:
    return {
        "config.env": f"export FIXTURE_TOKEN={FIXTURE}\n",
        "package.json": '{"dependencies": {"minimist": "1.2.5"}}\n',
        "requirements.txt": "PyYAML==5.3.1\n",
        "app.py": INJECTION,
    }


def _clean() -> dict[str, str]:
    return {
        "README.md": "hello\n",
        "package.json": '{"dependencies": {"minimist": "1.2.6"}}\n',
        "requirements.txt": "PyYAML==5.4\n",
        "app.py": CLEAN_SQL,
    }


def _assert_hidden(blob: str) -> None:
    assert FIXTURE not in blob
    assert "***" not in blob or FIXTURE not in blob


class Conn:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple]] = []

    async def execute(self, sql: str, *args: object) -> None:
        self.calls.append((sql, args))

    async def close(self) -> None:
        return None


def test_skill_engines_match_the_radix_scanners() -> None:
    pairs = (
        ("scan.secrets", "secrets.py"),
        ("scan.dependencies", "dependencies.py"),
        ("scan.static", "static.py"),
    )
    for skill, name in pairs:
        engine = ROOT / "tank" / "skills" / skill / "1.0.0" / "engine.py"
        source = ROOT / "agents" / "radix" / "scanlib" / name
        assert engine.read_bytes() == source.read_bytes()
    left = ROOT / "agents" / "radix" / "scanlib" / "osv"
    right = ROOT / "tank" / "skills" / "scan.dependencies" / "1.0.0" / "osv"
    assert sorted(path.name for path in left.glob("*.json")) == sorted(path.name for path in right.glob("*.json"))
    for path in left.glob("*.json"):
        assert path.read_bytes() == (right / path.name).read_bytes()


def test_image_pins_scanners_and_does_not_scan_over_the_network() -> None:
    text = (ROOT / "agents" / "radix" / "Dockerfile").read_text(encoding="utf-8")
    assert "GITLEAKS_VERSION=8.28.0" in text
    assert "a65b5253807a68ac0cafa4414031fd740aeb55f54fb7e55f386acb52e6a840eb" in text
    assert "SEMGREP_VERSION=1.181.0" in text
    assert "PIP_AUDIT_VERSION=2.10.1" in text
    assert "RADIX_USE_SYSTEM_TOOLS=1" in text
    assert "RADIX_OSV_DIR=/opt/osv" in text
    assert "CMD [" in text
    command = text.split("CMD [", 1)[1]
    assert "curl" not in command
    assert "pip-audit and npm audit call a live service" in text


def test_findings_sql_is_additive_and_scoped() -> None:
    schema = "agent_radix"
    for sql in (store.ensure_sql(schema), store.index_sql(schema), store.insert_sql(schema), store.list_sql(schema)):
        assert "DROP" not in sql.upper()
        assert "RENAME" not in sql.upper()
    assert "CREATE TABLE IF NOT EXISTS agent_radix.findings" in store.ensure_sql(schema)
    assert "CREATE INDEX IF NOT EXISTS" in store.index_sql(schema)
    assert "tenant_id" in store.insert_sql(schema)
    assert "WHERE tenant_id = $1 AND scan_id = $2" in store.list_sql(schema)
    with pytest.raises(ValueError):
        store.validate_schema("tank")
    with pytest.raises(ValueError):
        store.validate_schema("agent_radix;drop")


def test_secret_rules_and_static_rules_are_vendored() -> None:
    rules = (ROOT / "agents" / "radix" / "scanlib" / "gitleaks.toml").read_text(encoding="utf-8")
    semgrep = (ROOT / "agents" / "radix" / "scanlib" / "semgrep.yml").read_text(encoding="utf-8")
    assert "tvfy-example-fixture-key-[0-9]{4}" in rules
    assert "useDefault = true" in rules
    assert "python-sql-format" in semgrep
    assert "javascript-sql-concat" in semgrep


def test_planted_key_vulnerable_dependency_and_injection_are_found(capsys: pytest.CaptureFixture[str]) -> None:
    ctx = Ctx(_b64(_tar(_dirty())), ref="tervory-rig")
    result = orchestrate.build_result(ctx)
    captured = capsys.readouterr()
    blob = json.dumps(result) + captured.out + captured.err
    _assert_hidden(blob)
    assert result["leaked"] is False
    assert result["deploy_blocked"] is True
    assert result["tenant_id"] == TENANT
    assert "must not deploy" in result["summary"]
    rules = {item["rule"] for item in result["findings"]}
    assert "tervory-fixture-key" in rules
    assert "GHSA-xvch-5gv4-984h" in rules
    assert "GHSA-8q59-q68h-6hv4" in rules
    assert "python-sql-format" in rules
    secret = next(item for item in result["findings"] if item["rule"] == "tervory-fixture-key")
    assert secret["type"] == "fixture-key"
    assert secret["file"] == "config.env"
    assert secret["line"] == 1
    assert set(secret) <= {"tool", "severity", "file", "line", "rule", "fix", "type", "package", "version", "advisory"}
    dep = next(item for item in result["findings"] if item["advisory"] == "GHSA-xvch-5gv4-984h")
    assert dep["package"] == "minimist"
    assert dep["version"] == "1.2.5"
    assert dep["fix"] == "1.2.6"
    assert dep["severity"] == "critical"


def test_clean_tree_has_zero_criticals() -> None:
    result = orchestrate.build_result(Ctx(_b64(_tar(_clean())), ref="clean"))
    assert result["critical"] == 0
    assert result["findings"] == []
    assert result["deploy_blocked"] is False
    assert "does not block the build" in result["summary"]
    assert FIXTURE not in json.dumps(result)


def test_scan_makes_no_network_call(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("network call")

    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    result = orchestrate.build_result(Ctx(_b64(_tar(_dirty()))))
    assert result["critical"] >= 1
    assert FIXTURE not in json.dumps(result)


def test_remote_source_is_refused() -> None:
    with pytest.raises(ValueError, match="handed over"):
        orchestrate.build_result(Ctx("https://example.com/repo.tar.gz"))
    with pytest.raises(ValueError, match="handed over"):
        orchestrate.build_result(Ctx("git@github.com:Tervory-AI/tervory-rig.git"))


def test_other_tenant_is_refused() -> None:
    ctx = Ctx(_b64(_tar(_clean())))
    ctx.input["tenant_id"] = "33333333-3333-3333-3333-333333333333"
    with pytest.raises(PermissionError):
        orchestrate.build_result(ctx)


def test_zip_slip_is_refused() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zipped:
        zipped.writestr("../outside.txt", "nope")
    with pytest.raises(ValueError, match="not safe"):
        orchestrate.build_result(Ctx(_b64(buf.getvalue())))


def test_file_source_stays_inside_the_tenant() -> None:
    raw = _tar(_dirty())
    ctx = Ctx("file:repo.tar.gz")
    ctx.files = Files({"repo.tar.gz": raw})
    result = orchestrate.build_result(ctx)
    assert result["deploy_blocked"] is True
    assert FIXTURE not in json.dumps(result)


@pytest.mark.asyncio
async def test_rows_and_logs_do_not_contain_the_secret(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    conn = Conn()

    async def connect() -> Conn:
        return conn

    monkeypatch.setattr(orchestrate, "_connect", connect)
    ctx = Ctx(_b64(_tar(_dirty())), ref="main")
    app = _load_app()
    result = await app.scan(ctx)
    captured = capsys.readouterr()
    blob = json.dumps(result) + captured.out + captured.err
    _assert_hidden(blob)
    assert result["leaked"] is False
    inserts = [call for call in conn.calls if "INSERT INTO" in call[0]]
    assert inserts
    for sql, args in conn.calls:
        assert "tenant_id" in sql
        assert FIXTURE not in sql
        assert FIXTURE not in repr(args)
        if "INSERT INTO" in sql:
            assert args[0].hex  # uuid
            assert str(args[0]) == TENANT
    assert "CREATE TABLE IF NOT EXISTS agent_radix.findings" in conn.calls[0][0]


def test_gitleaks_report_is_masked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    script = tmp_path / "gitleaks"
    script.write_text(
        "#!/bin/sh\n"
        "report=\n"
        "prev=\n"
        "for arg in \"$@\"; do\n"
        "  if [ \"$prev\" = \"--report-path\" ]; then report=$arg; fi\n"
        "  prev=$arg\n"
        "done\n"
        f"printf '%s' '[{{\"RuleID\":\"tervory-fixture-key\",\"File\":\"config.env\",\"StartLine\":1,\"Secret\":\"{FIXTURE}\",\"Match\":\"{FIXTURE}\"}}]' > \"$report\"\n"
        "exit 1\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    monkeypatch.setenv("RADIX_USE_SYSTEM_TOOLS", "1")
    monkeypatch.setenv("GITLEAKS_BIN", str(script))
    root = tmp_path / "repo"
    root.mkdir()
    (root / "config.env").write_text(f"export FIXTURE_TOKEN={FIXTURE}\n", encoding="utf-8")
    findings, hidden = secrets.scan_tree(root)
    assert FIXTURE in hidden
    assert FIXTURE not in json.dumps(findings)
    assert findings[0]["rule"] == "tervory-fixture-key"
    assert not (root.parent / "gitleaks-report.json").exists()


def test_failing_gitleaks_falls_back_without_leaking_stderr(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    script = tmp_path / "gitleaks"
    script.write_text(f"#!/bin/sh\necho {FIXTURE} >&2\nexit 2\n", encoding="utf-8")
    script.chmod(0o755)
    monkeypatch.setenv("RADIX_USE_SYSTEM_TOOLS", "1")
    monkeypatch.setenv("GITLEAKS_BIN", str(script))
    root = tmp_path / "repo"
    root.mkdir()
    (root / "config.env").write_text(f"export FIXTURE_TOKEN={FIXTURE}\n", encoding="utf-8")
    findings, _hidden = secrets.scan_tree(root)
    captured = capsys.readouterr()
    assert findings[0]["rule"] == "tervory-fixture-key"
    assert FIXTURE not in json.dumps(findings)
    assert FIXTURE not in captured.out
    assert FIXTURE not in captured.err


def test_fixed_versions_are_not_critical() -> None:
    files = [
        ("package.json", '{"dependencies": {"minimist": "0.2.3"}}\n'),
        ("requirements.txt", "PyYAML==5.4\n"),
    ]
    found = dependencies.scan_files(files)
    assert [item["advisory"] for item in found] == ["GHSA-xvch-5gv4-984h"]
    assert found[0]["fix"] == "0.2.4"
    assert dependencies.scan_files([("package.json", '{"dependencies": {"minimist": "0.2.4"}}\n')]) == []
    assert dependencies.scan_files([("package.json", '{"dependencies": {"minimist": "1.2.6"}}\n')]) == []


def test_javascript_concat_is_critical_and_a_placeholder_is_not() -> None:
    bad = static.scan_files([("db.js", 'db.query("SELECT * FROM t WHERE id = " + userId)\n')])
    good = static.scan_files([("db.js", 'db.query("SELECT * FROM t WHERE id = ?", [userId])\n')])
    assert bad[0]["rule"] == "javascript-sql-concat"
    assert bad[0]["severity"] == "critical"
    assert good == []


def test_git_bundle_is_scanned_without_fetching(tmp_path: Path) -> None:
    repo = tmp_path / "src"
    repo.mkdir()
    (repo / "config.env").write_text(f"export FIXTURE_TOKEN={FIXTURE}\n", encoding="utf-8")
    subprocess.check_call(["git", "init", "-q"], cwd=repo)
    subprocess.check_call(["git", "config", "user.email", "scan@example.com"], cwd=repo)
    subprocess.check_call(["git", "config", "user.name", "Scan"], cwd=repo)
    subprocess.check_call(["git", "add", "config.env"], cwd=repo)
    subprocess.check_call(["git", "commit", "-q", "-m", "fixture"], cwd=repo)
    bundle = tmp_path / "repo.bundle"
    subprocess.check_call(["git", "bundle", "create", str(bundle), "--all"], cwd=repo)
    result = orchestrate.build_result(Ctx(_b64(bundle.read_bytes()), ref="bundle"))
    assert any(item["rule"] == "tervory-fixture-key" for item in result["findings"])
    assert FIXTURE not in json.dumps(result)
    assert result["leaked"] is False


def _load_app():
    import importlib.util

    path = ROOT / "agents" / "radix" / "app.py"
    spec = importlib.util.spec_from_file_location("radix_app_rx1", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
