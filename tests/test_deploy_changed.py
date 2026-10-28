"""The SA stack deploys after main and before any room. No network, no token printed."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _script(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("COOLIFY_URL", "https://coolify.example")
    monkeypatch.setenv("COOLIFY_TOKEN", "test-token")
    path = ROOT / ".github" / "scripts" / "deploy_changed.py"
    spec = importlib.util.spec_from_file_location("deploy_changed_script", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["deploy_changed_script"] = module
    spec.loader.exec_module(module)
    return module


def _apps() -> list[dict[str, str]]:
    return [
        {"name": "tervory-tank-za", "uuid": "za-uuid"},
        {"name": "agent-zenas", "uuid": "room-uuid"},
        {"name": "agent-zenas-za", "uuid": "room-za-uuid"},
    ]


def test_sa_stack_deploys_after_main_and_before_rooms(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _script(monkeypatch)
    order: list[tuple[str, str, str]] = []
    monkeypatch.setattr(mod, "changed_paths", lambda: ["tank/main.py", "agents/zenas/app.py"])
    monkeypatch.setattr(mod, "api", lambda method, path: (200, _apps()))

    def deploy(uuid: str, name: str) -> bool:
        order.append(("deploy", name, uuid))
        return True

    def wait_for(uuid: str, name: str, timeout_s: int = 900) -> bool:
        order.append(("wait", name, uuid))
        return True

    monkeypatch.setattr(mod, "deploy", deploy)
    monkeypatch.setattr(mod, "wait_for", wait_for)
    assert mod.main() == 0
    assert order == [
        ("deploy", "main", mod.MAIN_APP),
        ("wait", "main", mod.MAIN_APP),
        ("deploy", "tervory-tank-za", "za-uuid"),
        ("wait", "tervory-tank-za", "za-uuid"),
        ("deploy", "agent-zenas", "room-uuid"),
        ("wait", "agent-zenas", "room-uuid"),
        ("deploy", "agent-zenas-za", "room-za-uuid"),
        ("wait", "agent-zenas-za", "room-za-uuid"),
    ]


def test_a_failed_main_deploy_does_not_touch_the_sa_stack(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _script(monkeypatch)
    order: list[str] = []
    monkeypatch.setattr(mod, "changed_paths", lambda: ["tank/main.py"])
    monkeypatch.setattr(mod, "api", lambda method, path: (200, _apps()))

    def deploy(uuid: str, name: str) -> bool:
        order.append(name)
        return False

    monkeypatch.setattr(mod, "deploy", deploy)
    monkeypatch.setattr(mod, "wait_for", lambda uuid, name, timeout_s=900: True)
    assert mod.main() == 1
    assert order == ["main"]


def test_a_failed_sa_deploy_skips_za_rooms_but_deploys_boston_rooms(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _script(monkeypatch)
    order: list[tuple[str, str]] = []
    monkeypatch.setattr(mod, "changed_paths", lambda: ["docker-compose.yml", "agents/zenas/app.py"])
    monkeypatch.setattr(mod, "api", lambda method, path: (200, _apps()))

    def deploy(uuid: str, name: str) -> bool:
        order.append(("deploy", name))
        return name != "tervory-tank-za"

    def wait_for(uuid: str, name: str, timeout_s: int = 900) -> bool:
        order.append(("wait", name))
        return True

    monkeypatch.setattr(mod, "deploy", deploy)
    monkeypatch.setattr(mod, "wait_for", wait_for)
    assert mod.main() == 1  # still reported as a failure, so the ZA outage stays visible
    assert order == [
        ("deploy", "main"),
        ("wait", "main"),
        ("deploy", "tervory-tank-za"),
        ("deploy", "agent-zenas"),
        ("wait", "agent-zenas"),
    ]
    assert ("deploy", "agent-zenas-za") not in order


def test_a_main_change_with_no_rooms_still_deploys_the_sa_stack(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _script(monkeypatch)
    order: list[str] = []
    monkeypatch.setattr(mod, "changed_paths", lambda: ["tank/main.py"])
    monkeypatch.setattr(mod, "api", lambda method, path: (200, [{"name": "tervory-tank-za", "uuid": "za-uuid"}]))

    def deploy(uuid: str, name: str) -> bool:
        order.append(name)
        return True

    monkeypatch.setattr(mod, "deploy", deploy)
    monkeypatch.setattr(mod, "wait_for", lambda uuid, name, timeout_s=900: True)
    assert mod.main() == 0
    assert order == ["main", "tervory-tank-za"]


def test_a_missing_sa_app_still_deploys_boston_rooms(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _script(monkeypatch)
    order: list[str] = []
    monkeypatch.setattr(mod, "changed_paths", lambda: ["tank/main.py", "agents/zenas/app.py"])
    monkeypatch.setattr(mod, "api", lambda method, path: (200, [{"name": "agent-zenas", "uuid": "room-uuid"}]))

    def deploy(uuid: str, name: str) -> bool:
        order.append(name)
        return True

    monkeypatch.setattr(mod, "deploy", deploy)
    monkeypatch.setattr(mod, "wait_for", lambda uuid, name, timeout_s=900: True)
    assert mod.main() == 1
    assert order == ["main", "agent-zenas"]


def test_a_room_only_change_does_not_deploy_the_sa_stack(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _script(monkeypatch)
    order: list[str] = []
    monkeypatch.setattr(mod, "changed_paths", lambda: ["agents/zenas/app.py"])
    monkeypatch.setattr(mod, "api", lambda method, path: (200, _apps()))

    def deploy(uuid: str, name: str) -> bool:
        order.append(name)
        return True

    monkeypatch.setattr(mod, "deploy", deploy)
    monkeypatch.setattr(mod, "wait_for", lambda uuid, name, timeout_s=900: True)
    assert mod.main() == 0
    assert order == ["agent-zenas", "agent-zenas-za"]


def test_za_offline_skips_the_sa_stack_and_za_rooms_without_failing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZA_OFFLINE", "true")
    mod = _script(monkeypatch)
    order: list[tuple[str, str]] = []
    monkeypatch.setattr(mod, "changed_paths", lambda: ["tank/main.py", "agents/zenas/app.py"])
    monkeypatch.setattr(mod, "api", lambda method, path: (200, _apps()))

    def deploy(uuid: str, name: str) -> bool:
        order.append(("deploy", name))
        return name != "tervory-tank-za"

    def wait_for(uuid: str, name: str, timeout_s: int = 900) -> bool:
        order.append(("wait", name))
        return True

    monkeypatch.setattr(mod, "deploy", deploy)
    monkeypatch.setattr(mod, "wait_for", wait_for)
    assert mod.main() == 0
    assert order == [("deploy", "main"), ("wait", "main"), ("deploy", "agent-zenas"), ("wait", "agent-zenas")]


def test_za_offline_other_values_keep_todays_behaviour(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZA_OFFLINE", "false")
    mod = _script(monkeypatch)
    monkeypatch.setattr(mod, "changed_paths", lambda: ["tank/main.py"])
    monkeypatch.setattr(mod, "api", lambda method, path: (200, _apps()))
    monkeypatch.setattr(mod, "deploy", lambda uuid, name: name != "tervory-tank-za")
    monkeypatch.setattr(mod, "wait_for", lambda uuid, name, timeout_s=900: True)
    assert mod.main() == 1


def test_rooms_deploy_one_at_a_time_and_a_failed_room_does_not_stop_the_rest(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _script(monkeypatch)
    order: list[tuple[str, str]] = []
    apps = [{"name": "agent-base", "uuid": "b"}, {"name": "agent-rig", "uuid": "r"}, {"name": "agent-tiger", "uuid": "t"}]
    monkeypatch.setattr(mod, "changed_paths", lambda: ["agents/_chassis/chassis/app.py"])
    monkeypatch.setattr(mod, "api", lambda method, path: (200, apps))

    def deploy(uuid: str, name: str) -> bool:
        order.append(("deploy", name))
        return name != "agent-rig"

    def wait_for(uuid: str, name: str, timeout_s: int = 900) -> bool:
        order.append(("wait", name))
        return True

    monkeypatch.setattr(mod, "deploy", deploy)
    monkeypatch.setattr(mod, "wait_for", wait_for)
    assert mod.main() == 1
    assert order == [
        ("deploy", "agent-base"), ("wait", "agent-base"),
        ("deploy", "agent-rig"),
        ("deploy", "agent-tiger"), ("wait", "agent-tiger"),
    ]


def _api_with_failed(apps, failed):
    def api(method, path):
        if path.startswith("/deployments/applications/"):
            uuid = path.split("/")[3].split("?")[0]
            return 200, [{"status": "failed" if uuid in failed else "finished"}]
        return 200, apps
    return api


def test_a_room_that_failed_last_time_is_retried_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _script(monkeypatch)
    order: list[str] = []
    apps = [{"name": "agent-base", "uuid": "b"}, {"name": "agent-zenas", "uuid": "z"}, {"name": "agent-rig", "uuid": "r"}]
    monkeypatch.setattr(mod, "changed_paths", lambda: ["agents/rig/app.py"])
    monkeypatch.setattr(mod, "api", _api_with_failed(apps, {"z"}))
    monkeypatch.setattr(mod, "deploy", lambda uuid, name: order.append(name) or True)
    monkeypatch.setattr(mod, "wait_for", lambda uuid, name, timeout_s=900: True)
    assert mod.main() == 0
    assert order == ["agent-rig", "agent-zenas"]  # agent-base is untouched


def test_nothing_changed_and_nothing_failed_deploys_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _script(monkeypatch)
    order: list[str] = []
    apps = [{"name": "agent-base", "uuid": "b"}]
    monkeypatch.setattr(mod, "changed_paths", lambda: ["docs/readme.txt"])
    monkeypatch.setattr(mod, "api", _api_with_failed(apps, set()))
    monkeypatch.setattr(mod, "deploy", lambda uuid, name: order.append(name) or True)
    assert mod.main() == 0 and order == []


def test_main_that_failed_last_time_is_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _script(monkeypatch)
    order: list[str] = []
    monkeypatch.setattr(mod, "changed_paths", lambda: ["docs/readme.txt"])
    monkeypatch.setattr(mod, "api", _api_with_failed([], {mod.MAIN_APP}))
    monkeypatch.setattr(mod, "deploy", lambda uuid, name: order.append(name) or True)
    monkeypatch.setattr(mod, "wait_for", lambda uuid, name, timeout_s=900: True)
    monkeypatch.setenv("ZA_OFFLINE", "true")
    mod.ZA_OFFLINE = True
    assert mod.main() == 0 and order == ["main"]
