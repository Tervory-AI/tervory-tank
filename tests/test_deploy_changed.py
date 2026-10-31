"""The SA stack deploys after main and before any room. No network, no token printed."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _script(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("COOLIFY_URL", "https://coolify.example")
    monkeypatch.setenv("COOLIFY_TOKEN", "test-token")
    path = ROOT / ".github" / "scripts" / "deploy_changed.py"
    monkeypatch.syspath_prepend(str(path.parent))
    spec = importlib.util.spec_from_file_location("deploy_changed_script", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["deploy_changed_script"] = module
    spec.loader.exec_module(module)
    # These deployment-order fixtures do not contain environment metadata.
    # The scope gate has its own real GET/PATCH integration tests.
    monkeypatch.setattr(module, "verify_main_scope", lambda api: True)
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


def test_main_scope_gate_runs_before_any_deployment(monkeypatch):
    mod = _script(monkeypatch)
    calls = []
    monkeypatch.setattr(mod, "changed_paths", lambda: ["docker-compose.yml"])
    monkeypatch.setattr(mod, "api", _api_with_failed([], set()))
    monkeypatch.setattr(mod, "verify_main_scope", lambda api: calls.append("scope") or False)
    monkeypatch.setattr(mod, "deploy", lambda *args: calls.append("deploy") or True)
    assert mod.main() == 1
    assert calls == ["scope"]


def _live_api(live: dict[str, str]):
    """Coolify fake: app list, and per-app latest deployment {status, commit}."""
    def api(method: str, path: str):
        if path == "/applications":
            return 200, _apps()
        for uuid, commit in live.items():
            if path.startswith(f"/deployments/applications/{uuid}"):
                return 200, {"deployments": [{"status": "finished", "commit": commit}]}
        return 200, {"deployments": [{"status": "finished", "commit": "0" * 40}]}
    return api


def test_a_queued_run_does_not_restart_apps_already_on_the_tip_of_main(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _script(monkeypatch)
    head = "3f57590c87dafe693ebe5aa4a8bb2a14b6ce2939"
    monkeypatch.setattr(mod, "MAIN_HEAD", head)
    order: list[str] = []
    monkeypatch.setattr(mod, "changed_paths", lambda: ["tank/main.py", "agents/zenas/app.py"])
    monkeypatch.setattr(mod, "api", _live_api({mod.MAIN_APP: head, "za-uuid": head, "room-uuid": head}))
    monkeypatch.setattr(mod, "deploy", lambda uuid, name: order.append(name) or True)
    monkeypatch.setattr(mod, "wait_for", lambda uuid, name, timeout_s=900: True)
    assert mod.main() == 0
    # Only the room whose last deploy is an older commit is deployed.
    assert order == ["agent-zenas-za"]


def test_unknown_main_head_deploys_every_wanted_app(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _script(monkeypatch)
    head = "3f57590c87dafe693ebe5aa4a8bb2a14b6ce2939"
    monkeypatch.setattr(mod, "MAIN_HEAD", "")
    order: list[str] = []
    monkeypatch.setattr(mod, "changed_paths", lambda: ["tank/main.py"])
    monkeypatch.setattr(mod, "api", _live_api({mod.MAIN_APP: head, "za-uuid": head}))
    monkeypatch.setattr(mod, "deploy", lambda uuid, name: order.append(name) or True)
    monkeypatch.setattr(mod, "wait_for", lambda uuid, name, timeout_s=900: True)
    assert mod.main() == 0
    assert order == ["main", "tervory-tank-za"]


# --- Waiting on a slow ZA build (31 Oct: ZA deployment 882 took 22 min) ----------


def _clock(monkeypatch: pytest.MonkeyPatch, mod) -> list[float]:
    """Fake time: sleep advances the clock, so the waits run instantly."""
    now = [0.0]
    monkeypatch.setattr(mod.time, "time", lambda: now[0])
    monkeypatch.setattr(mod.time, "sleep", lambda s: now.__setitem__(0, now[0] + s))
    return now


def test_wait_follows_the_queued_deployment_not_the_newest_row(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _script(monkeypatch)
    now = _clock(monkeypatch, mod)
    calls: list[str] = []

    def api(method: str, path: str):
        calls.append(f"{method} {path}")
        if method == "POST":
            return 200, {"deployments": [{"resource_uuid": "za-uuid", "deployment_uuid": "dep-882"}]}
        if path == "/deployments/dep-882":
            # Still building for 19 minutes, then finished: longer than the old 900 s wait.
            return 200, {"status": "in_progress" if now[0] < 19 * 60 else "finished"}
        return 200, [{"status": "failed"}]  # an older or unrelated row must not be read

    monkeypatch.setattr(mod, "api", api)
    assert mod.deploy("za-uuid", "tervory-tank-za")
    assert mod.wait_for("za-uuid", "tervory-tank-za", mod.ZA_TIMEOUT_S) is True
    assert all("/deployments/applications/" not in c for c in calls)


def test_a_deployment_still_building_at_the_deadline_is_reported_as_in_progress(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    mod = _script(monkeypatch)
    _clock(monkeypatch, mod)
    mod._queued["za-uuid"] = "dep-882"
    monkeypatch.setattr(mod, "api", lambda method, path: (200, {"status": "in_progress"}))
    assert mod.wait_for("za-uuid", "tervory-tank-za", 600) is False
    out = capsys.readouterr().out
    assert "still in_progress after 600s (deployment dep-882)" in out
    assert "may still finish in Coolify" in out
    assert "deploy failed" not in out


def test_a_failed_deployment_is_reported_as_failed(monkeypatch: pytest.MonkeyPatch,
                                                   capsys: pytest.CaptureFixture[str]) -> None:
    mod = _script(monkeypatch)
    _clock(monkeypatch, mod)
    mod._queued["za-uuid"] = "dep-1"
    monkeypatch.setattr(mod, "api", lambda method, path: (200, {"status": "failed"}))
    assert mod.wait_for("za-uuid", "tervory-tank-za", 600) is False
    assert "ended with failed" in capsys.readouterr().out


def test_without_a_queued_id_the_wait_reads_the_latest_deployment(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _script(monkeypatch)
    _clock(monkeypatch, mod)
    mod._queued.clear()
    seen: list[str] = []
    monkeypatch.setattr(mod, "api", lambda method, path: seen.append(path) or (200, [{"status": "finished"}]))
    assert mod.wait_for("room-uuid", "agent-zenas") is True
    assert seen == ["/deployments/applications/room-uuid?take=1"]


def test_each_stage_gets_its_own_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _script(monkeypatch)
    waits: dict[str, int] = {}
    monkeypatch.setattr(mod, "changed_paths", lambda: ["tank/main.py", "agents/zenas/app.py"])
    monkeypatch.setattr(mod, "api", lambda method, path: (200, _apps()))
    monkeypatch.setattr(mod, "deploy", lambda uuid, name: True)
    monkeypatch.setattr(mod, "wait_for", lambda uuid, name, timeout_s=900: waits.setdefault(name, timeout_s) or True)
    assert mod.main() == 0
    assert waits == {"main": mod.MAIN_TIMEOUT_S, "tervory-tank-za": mod.ZA_TIMEOUT_S,
                     "agent-zenas": mod.ROOM_TIMEOUT_S, "agent-zenas-za": mod.ZA_ROOM_TIMEOUT_S}
    # The two ZA builds on 31 Oct took 19 and 22 minutes.
    assert mod.ZA_TIMEOUT_S >= 40 * 60
    # agent-zenas-za took 18m00s, 14m35s and 19m49s (deployments 767, 874, 694).
    assert mod.ZA_ROOM_TIMEOUT_S >= 30 * 60


def _repo_rooms() -> tuple[list[str], list[str]]:
    """Room apps the repo defines: one per agents/<room>/, plus <room>-za where the room has
    a ZA compose file (agents/zenas/docker-compose.za.yml -> agent-zenas-za)."""
    folders = sorted(p for p in (ROOT / "agents").iterdir()
                     if p.is_dir() and not p.name.startswith("_") and (p / "docker-compose.yml").exists())
    boston = ["agent-" + p.name.replace("_", "-") for p in folders]
    za = [name + "-za" for name, p in zip(boston, folders) if (p / "docker-compose.za.yml").exists()]
    return boston, za


def test_deploy_job_has_room_for_every_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    import yaml
    mod = _script(monkeypatch)
    job = yaml.safe_load((ROOT / ".github/workflows/deploy-on-merge.yml").read_text(encoding="utf-8"))["jobs"]["deploy"]
    boston, za = _repo_rooms()
    assert "agent-zenas" in boston and za == ["agent-zenas-za"]
    # Worst case: a shared-room change deploys main, ZA, then every room one at a time.
    waits = mod.MAIN_TIMEOUT_S + mod.ZA_TIMEOUT_S + sum(mod.room_timeout(n) for n in boston + za)
    assert waits == 1800 + 2700 + len(boston) * 900 + len(za) * 1800
    # Coolify calls besides the polls, each up to its 30 s socket timeout: the app list,
    # the backup-scope check (GET, PATCH, GET), and per app the retry GET, the
    # already-live GET, the POST and a 404 on an "already queued" id. Each wait can also
    # overrun its deadline by one poll call plus one sleep.
    call_s, overrun_s, checkout_s = 30, 30 + mod.POLL_S, 60
    apps = 2 + len(boston) + len(za)
    overhead = (1 + 3 + apps * 4) * call_s + apps * overrun_s + checkout_s
    budget = int(job["env"]["DEPLOY_BUDGET_S"])
    assert waits + overhead <= budget, "the budget guard would skip a room in the worst case"
    # The guard starts a room only if its whole wait fits the budget, so the job ends at
    # most one room's calls and overrun after the budget.
    assert checkout_s + budget + 3 * call_s + overrun_s <= job["timeout-minutes"] * 60
    assert job["timeout-minutes"] <= 360  # GitHub-hosted job limit


def test_a_room_whose_wait_no_longer_fits_the_budget_is_not_started(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    mod = _script(monkeypatch)
    now = _clock(monkeypatch, mod)
    monkeypatch.setattr(mod, "_run_started", 0.0)
    monkeypatch.setattr(mod, "DEPLOY_BUDGET_S", 1800 + 2700 + 900 + 600)
    order: list[str] = []
    monkeypatch.setattr(mod, "changed_paths", lambda: ["tank/main.py", "agents/zenas/app.py"])
    monkeypatch.setattr(mod, "api", lambda method, path: (200, _apps()))
    monkeypatch.setattr(mod, "deploy", lambda uuid, name: order.append(name) or True)

    def wait_for(uuid: str, name: str, timeout_s: int = 900) -> bool:
        now[0] += timeout_s  # every wait runs to its deadline
        return True

    monkeypatch.setattr(mod, "wait_for", wait_for)
    assert mod.main() == 1
    assert order == ["main", "tervory-tank-za", "agent-zenas"]
    assert "agent-zenas-za not started" in capsys.readouterr().out


def test_sa_stack_that_failed_last_time_is_retried_without_main(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _script(monkeypatch)
    order: list[str] = []
    monkeypatch.setattr(mod, "changed_paths", lambda: ["docs/readme.txt"])
    monkeypatch.setattr(mod, "api", _api_with_failed(_apps(), {"za-uuid"}))
    monkeypatch.setattr(mod, "deploy", lambda uuid, name: order.append(name) or True)
    monkeypatch.setattr(mod, "wait_for", lambda uuid, name, timeout_s=900: True)
    assert mod.main() == 0
    assert order == ["tervory-tank-za"]


def test_sa_stack_retry_respects_za_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _script(monkeypatch)
    order: list[str] = []
    mod.ZA_OFFLINE = True
    monkeypatch.setattr(mod, "changed_paths", lambda: ["docs/readme.txt"])
    monkeypatch.setattr(mod, "api", _api_with_failed(_apps(), {"za-uuid"}))
    monkeypatch.setattr(mod, "deploy", lambda uuid, name: order.append(name) or True)
    assert mod.main() == 0 and order == []


# --- Review of #515: queued ids, failed calls, empty queue replies, missed rooms -------


def test_case_g_already_queued_id_that_404s_follows_the_apps_newest_deployment(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Coolify's "already queued" reply carries an id it never saved; GET on it is 404."""
    mod = _script(monkeypatch)
    now = _clock(monkeypatch, mod)
    calls: list[str] = []

    def api(method: str, path: str):
        calls.append(path)
        if method == "POST":
            return 200, {"deployments": [{"message": "Deployment already queued for this commit.",
                                          "resource_uuid": "za-uuid", "deployment_uuid": "never-saved"}]}
        if path == "/deployments/never-saved":
            return 404, '{"message":"Deployment not found."}'
        if path == "/deployments/applications/za-uuid?take=1":
            return 200, {"deployments": [{"status": "in_progress" if now[0] < 600 else "finished"}]}
        raise AssertionError(path)

    monkeypatch.setattr(mod, "api", api)
    assert mod.deploy("za-uuid", "tervory-tank-za")
    assert mod.wait_for("za-uuid", "tervory-tank-za", mod.ZA_TIMEOUT_S) is True
    assert calls.count("/deployments/never-saved") == 1
    assert calls[-1] == "/deployments/applications/za-uuid?take=1"


def test_case_n_a_200_that_queued_nothing_is_an_error(monkeypatch: pytest.MonkeyPatch,
                                                     capsys: pytest.CaptureFixture[str]) -> None:
    mod = _script(monkeypatch)
    mod._queued.clear()
    monkeypatch.setattr(mod, "api", lambda method, path: (
        200, {"deployments": [{"message": "Deployment queue is full.", "resource_uuid": "za"}]}))
    assert mod.deploy("za", "tervory-tank-za") is False
    out = capsys.readouterr().out
    assert "::error title=deploy tervory-tank-za::" in out and "Deployment queue is full." in out
    assert "za" not in mod._queued


class _Resp:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self.body, self.status = body, status

    def read(self) -> bytes:
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        return None


@pytest.mark.parametrize("failure, kind", [
    ("url", "URLError"),           # case I: DNS or connection refused
    ("timeout", "TimeoutError"),   # case J: socket timeout
    ("reset", "ConnectionResetError"),
    ("html", "JSONDecodeError"),   # case K: a proxy's HTML page with status 200
])
def test_cases_i_j_k_a_failed_call_is_code_0_not_a_crash(monkeypatch: pytest.MonkeyPatch,
                                                        failure: str, kind: str) -> None:
    import urllib.error
    mod = _script(monkeypatch)

    def urlopen(req, timeout=30):
        if failure == "url":
            raise urllib.error.URLError("Name or service not known")
        if failure == "timeout":
            raise TimeoutError("timed out")
        if failure == "reset":
            raise ConnectionResetError("reset by peer")
        return _Resp(b"<html><body>502 Bad Gateway</body></html>")

    monkeypatch.setattr(mod, "URL", "https://coolify.tervory.com")  # urlopen is faked: no network
    monkeypatch.setattr(mod.urllib.request, "urlopen", urlopen)
    assert mod.api("GET", "/deployments/x") == (0, kind)


def test_a_failed_call_mid_wait_does_not_end_the_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    import urllib.error
    mod = _script(monkeypatch)
    now = _clock(monkeypatch, mod)
    mod._queued["room-uuid"] = "dep-1"

    def urlopen(req, timeout=30):
        if now[0] < 120:
            raise urllib.error.URLError("connection refused")
        return _Resp(b'{"status": "finished"}')

    monkeypatch.setattr(mod, "URL", "https://coolify.tervory.com")  # urlopen is faked: no network
    monkeypatch.setattr(mod.urllib.request, "urlopen", urlopen)
    assert mod.wait_for("room-uuid", "agent-zenas") is True


def test_a_failed_call_for_one_room_does_not_stop_the_later_rooms(monkeypatch: pytest.MonkeyPatch) -> None:
    import urllib.error
    mod = _script(monkeypatch)
    _clock(monkeypatch, mod)
    apps = [{"name": "agent-base", "uuid": "b"}, {"name": "agent-rig", "uuid": "r"}]
    deployed: list[str] = []

    def urlopen(req, timeout=30):
        url, method = req.full_url, req.get_method()
        if url.endswith("/applications"):
            return _Resp(json.dumps(apps).encode())
        if method == "POST":
            uuid = url.split("uuid=")[1].split("&")[0]
            if uuid == "b":
                raise TimeoutError("timed out")
            deployed.append(uuid)
            return _Resp(json.dumps({"deployments": [{"deployment_uuid": f"dep-{uuid}"}]}).encode())
        if "/deployments/dep-" in url:
            return _Resp(b'{"status": "finished"}')
        return _Resp(b'{"deployments": []}')

    monkeypatch.setattr(mod, "changed_paths", lambda: ["agents/_chassis/chassis/app.py"])
    monkeypatch.setattr(mod, "URL", "https://coolify.tervory.com")  # urlopen is faked: no network
    monkeypatch.setattr(mod.urllib.request, "urlopen", urlopen)
    assert mod.main() == 1  # agent-base's failed POST is reported
    assert deployed == ["r"]


def _git(repo: Path, *args: str) -> str:
    import subprocess
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                          text=True).stdout.strip()


def _history(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    """A repo: rig change (r1), base change (b1), docs change (d1), shared room change (c1)."""
    repo = tmp_path / "repo"
    (repo / "agents" / "rig").mkdir(parents=True)
    (repo / "agents" / "base").mkdir()
    (repo / "agents" / "_chassis").mkdir()
    (repo / "docs").mkdir()
    _git(repo.parent, "init", "-q", str(repo))
    shas: dict[str, str] = {}
    for key, path in [("r1", "agents/rig/app.py"), ("b1", "agents/base/app.py"), ("d1", "docs/a.txt"),
                      ("c1", "agents/_chassis/app.py")]:
        (repo / path).write_text(key, encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", key)
        shas[key] = _git(repo, "rev-parse", "HEAD")
    return repo, shas


def test_stale_finds_a_room_a_run_never_deployed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    mod = _script(monkeypatch)
    repo, sha = _history(tmp_path)
    monkeypatch.setattr(mod, "REPO", str(repo))
    monkeypatch.setattr(mod, "AFTER", sha["d1"])
    row = lambda commit, status="finished": {"status": status, "commit": commit}  # noqa: E731
    # agent-base's code changed in b1; it last deployed r1, so a run skipped it.
    assert mod.stale("b", "agent-base", row(sha["r1"])) is True
    assert mod.stale("b", "agent-base", row(sha["b1"])) is False
    assert mod.stale("b", "agent-base", row(sha["d1"])) is False
    # agent-rig last deployed b1, after its only change r1.
    assert mod.stale("r", "agent-rig", row(sha["b1"])) is False
    # A regional copy follows its room's folder.
    assert mod.stale("r", "agent-base-za", row(sha["r1"])) is True
    # Unknowns never redeploy: a commit outside the clone, no commit, a running deploy.
    assert mod.stale("b", "agent-base", row("f" * 40)) is False
    assert mod.stale("b", "agent-base", row("HEAD")) is False
    assert mod.stale("b", "agent-base", row(sha["r1"], "in_progress")) is False
    assert mod.stale("x", "agent-unknown", row(sha["r1"])) is False
    # A shared room change makes every room behind it stale.
    monkeypatch.setattr(mod, "AFTER", sha["c1"])
    assert mod.stale("r", "agent-rig", row(sha["d1"])) is True


def test_a_room_skipped_by_an_earlier_run_is_deployed_by_the_next(monkeypatch: pytest.MonkeyPatch,
                                                                 tmp_path: Path) -> None:
    mod = _script(monkeypatch)
    repo, sha = _history(tmp_path)
    monkeypatch.setattr(mod, "REPO", str(repo))
    monkeypatch.setattr(mod, "AFTER", sha["d1"])
    apps = [{"name": "agent-base", "uuid": "b"}, {"name": "agent-rig", "uuid": "r"}]
    live = {"b": sha["r1"], "r": sha["b1"], mod.MAIN_APP: "f" * 40}

    def api(method: str, path: str):
        if path == "/applications":
            return 200, apps
        uuid = path.split("/")[3].split("?")[0]
        return 200, {"deployments": [{"status": "finished", "commit": live[uuid]}]}

    order: list[str] = []
    monkeypatch.setattr(mod, "changed_paths", lambda: ["docs/a.txt"])
    monkeypatch.setattr(mod, "api", api)
    monkeypatch.setattr(mod, "deploy", lambda uuid, name: order.append(name) or True)
    monkeypatch.setattr(mod, "wait_for", lambda uuid, name, timeout_s=900: True)
    assert mod.main() == 0
    assert order == ["agent-base"]


def test_room_folder_prefers_the_longest_match(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    mod = _script(monkeypatch)
    for d in ("market", "market_lab", "_template"):
        (tmp_path / "agents" / d).mkdir(parents=True)
    monkeypatch.setattr(mod, "REPO", str(tmp_path))
    assert mod.room_folder("agent-market-lab-za") == "market_lab"
    assert mod.room_folder("agent-market") == "market"
    assert mod.room_folder("agent-template") == ""
    assert mod.room_folder("agent-marketing") == ""
