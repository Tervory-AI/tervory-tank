"""Mocked metadata-only recovery and persistent deployment drift protection."""
import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("backup_scope_test", ROOT / ".github/scripts/backup_runtime_scope.py")
scope = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scope)


class Metadata(dict):
    def get(self, key, *args):
        assert key not in {"value", "real_value"}, "value fields must never be accessed"
        return super().get(key, *args)


def inventory():
    return [Metadata(key=key, is_preview=False, is_runtime=True)
            for key in sorted(scope.OWN_PAIR | scope.REPAIR_PAIR)]


def fake_api(rows, calls, fail_key=None):
    def api(method, path, payload=None):
        assert path == "/applications/xnmc0jkz8j9i5jh1jwanbsfv/envs"
        calls.append((method, path, payload))
        if method == "GET":
            return 200, rows
        assert method == "PATCH"
        assert set(payload) == {"key", "is_preview", "is_runtime"}
        assert payload["key"] in scope.REPAIR_PAIR
        assert payload["is_preview"] is False and payload["is_runtime"] is False
        if payload["key"] == fail_key:
            return 404, None
        row = next(row for row in rows if row["key"] == payload["key"])
        row["is_runtime"] = False
        return 201, None
    return api


def test_real_get_patch_repair_is_scoped_idempotent_and_preserves_values(capsys):
    rows, calls = inventory(), []
    api = fake_api(rows, calls)
    assert scope.verify_main_scope(api) is False
    assert scope.repair_main_scope(api, ROOT / "docker-compose.yml") is True
    assert [c[2]["key"] for c in calls if c[0] == "PATCH"] == sorted(scope.REPAIR_PAIR)
    assert all(row["is_runtime"] for row in rows if row["key"] in scope.OWN_PAIR)
    count = len(calls)
    assert scope.repair_main_scope(api, ROOT / "docker-compose.yml") is True
    assert all(c[0] == "GET" for c in calls[count:])
    assert "value" not in capsys.readouterr().out


@pytest.mark.parametrize("failure", ["consumer", "missing", "other_owner", "own_disabled"])
def test_unsafe_preconditions_write_nothing(tmp_path, failure):
    rows, calls = inventory(), []
    compose = tmp_path / "compose.yml"
    compose.write_text("services: {}")
    if failure == "consumer":
        compose.write_text("R2_ACCESS_KEY_ID_GHOST")
    elif failure == "missing":
        rows.pop()
    elif failure == "other_owner":
        rows.append(Metadata(key="R2_ACCESS_KEY_ID_ZENAS", is_runtime=True))
    else:
        next(row for row in rows if row["key"] in scope.OWN_PAIR)["is_runtime"] = False
    with pytest.raises(scope.ScopeError):
        scope.repair_main_scope(fake_api(rows, calls), compose)
    assert all(c[0] == "GET" for c in calls)


def test_partial_patch_failure_never_requests_deployment():
    rows, calls = inventory(), []
    with pytest.raises(scope.ScopeError, match="no deploy requested"):
        scope.repair_main_scope(fake_api(rows, calls, sorted(scope.REPAIR_PAIR)[1]), ROOT / "docker-compose.yml")
    assert {c[0] for c in calls} == {"GET", "PATCH"}
    assert all(c[1] == scope.ENV_PATH for c in calls)


@pytest.mark.parametrize("rows", [None, [{"key": "x"}], [{"key": "x", "is_runtime": "false"}], [{"uuid": "x"}]])
def test_unknown_inventory_blocks_deployment(rows):
    assert scope.verify_main_scope(lambda *args: (200, rows)) is False


def test_patch_response_body_is_never_read(monkeypatch):
    class Response:
        status = 201
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, *args): raise AssertionError("mutation response body accessed")
    class Opener:
        def open(self, request, timeout):
            assert request.method == "PATCH"
            return Response()
    monkeypatch.setenv("COOLIFY_URL", "https://coolify.tervory.com")
    monkeypatch.setenv("COOLIFY_TOKEN", "offline-placeholder")
    monkeypatch.setattr(scope.urllib.request, "build_opener", lambda *args: Opener())
    assert scope.api("PATCH", scope.ENV_PATH, {"key": "R2_ACCESS_KEY_ID_GHOST", "is_runtime": False}) == (201, None)


def test_workflow_uses_fixed_scope_operation_and_excludes_generic_body_logging():
    workflow = yaml.safe_load((ROOT / ".github/workflows/coolify-ops.yml").read_text())
    steps = workflow["jobs"]["op"]["steps"]
    repair = next(s for s in steps if s.get("if") == "inputs.op == 'backup-scope'")
    assert repair["run"] == "python3 .github/scripts/backup_runtime_scope.py --apply"
    generic = next(s for s in steps if s.get("name") == "Run")
    assert "inputs.op != 'backup-scope'" in generic["if"]
    gate = next(s for s in steps if s.get("name") == "Verify main backup scope before manual deploy")
    assert gate["if"] == "inputs.op == 'deploy' && inputs.app == 'xnmc0jkz8j9i5jh1jwanbsfv'"
    assert gate["run"] == "python3 .github/scripts/backup_runtime_scope.py"
    assert not gate.get("continue-on-error", False)
    assert steps.index(gate) < steps.index(generic)
    assert "always()" not in generic["if"]


def test_real_transport_repairs_metadata_without_changing_server_values(monkeypatch, capsys):
    rows = inventory()
    for row in rows:
        row["value"] = "unchanged-offline-marker-" + row["key"]
    original = {row["key"]: row["value"] for row in rows}
    patches = []
    class GetResponse(io.BytesIO):
        status = 200
    class PatchResponse:
        status = 201
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, *args): raise AssertionError("PATCH body must not be read")
    class Controller:
        def open(self, request, timeout):
            assert request.full_url == "https://coolify.tervory.com/api/v1" + scope.ENV_PATH
            if request.method == "GET":
                return GetResponse(json.dumps(rows).encode())
            assert request.method == "PATCH"
            payload = json.loads(request.data)
            assert set(payload) == {"key", "is_preview", "is_runtime"}
            assert payload["key"] in scope.REPAIR_PAIR
            assert payload["is_preview"] is False and payload["is_runtime"] is False
            next(row for row in rows if row["key"] == payload["key"])["is_runtime"] = False
            patches.append(payload)
            return PatchResponse()
    monkeypatch.setenv("COOLIFY_URL", "https://coolify.tervory.com")
    monkeypatch.setenv("COOLIFY_TOKEN", "offline-placeholder")
    monkeypatch.setattr(scope.urllib.request, "build_opener", lambda *args: Controller())
    assert scope.repair_main_scope(scope.api, ROOT / "docker-compose.yml") is True
    assert len(patches) == 2
    assert {row["key"]: row["value"] for row in rows} == original
    assert all(row["is_runtime"] is False for row in rows if row["key"] in scope.REPAIR_PAIR)
    assert "unchanged-offline-marker" not in capsys.readouterr().out


def test_real_automatic_gate_refuses_drift_without_deploying(monkeypatch):
    path = ROOT / ".github/scripts/deploy_changed.py"
    monkeypatch.syspath_prepend(str(path.parent))
    monkeypatch.setenv("COOLIFY_URL", "https://coolify.tervory.com")
    monkeypatch.setenv("COOLIFY_TOKEN", "offline-placeholder")
    spec = importlib.util.spec_from_file_location("deploy_scope_integration", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    calls = []
    def api(method, path):
        calls.append((method, path))
        assert method == "GET", "scope drift must block every deployment POST"
        if path == "/applications": return 200, []
        if path == scope.ENV_PATH: return 200, inventory()
        return 200, [{"status": "finished"}]
    monkeypatch.setattr(mod, "api", api)
    monkeypatch.setattr(mod, "changed_paths", lambda: ["docker-compose.yml"])
    assert mod.main() == 1
    assert ("GET", scope.ENV_PATH) in calls
