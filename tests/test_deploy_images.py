"""Images built in CI, merges batched, rollback record (deploy_images.py, 9 Nov).

Fakes only: no Coolify call, no registry call, no network.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / ".github" / "scripts"
_spec = importlib.util.spec_from_file_location("deploy_images", SCRIPTS / "deploy_images.py")
di = importlib.util.module_from_spec(_spec)
sys.modules["deploy_images"] = di
_spec.loader.exec_module(di)

A, B, C, D = ("a" * 40, "b" * 40, "c" * 40, "d" * 40)


class FakeRegistry:
    """Tags -> digests, the way GHCR keeps them."""

    def __init__(self, tags: dict[str, str] | None = None) -> None:
        self.tags = dict(tags or {})
        self.moves: list[tuple[str, str]] = []

    def digest(self, ref: str) -> str:
        if "@" in ref:
            return ref.split("@", 1)[1]
        return self.tags.get(ref, "")

    def tag(self, source: str, target: str) -> None:
        digest = self.digest(source)
        assert digest, f"no such image {source}"
        self.tags[target] = digest
        self.moves.append((source, target))


def _specs(compose: str) -> list[di.BuildSpec]:
    services = {"docker-compose.yml": ["tank", "workspace"], "agents/zenas/docker-compose.yml": ["agent-zenas"]}
    return [di.BuildSpec(compose=compose, service=s, context=".", dockerfile="Dockerfile")
            for s in services.get(compose, ["app"])]


COMPOSES = ["docker-compose.yml", "docker-compose.za.yml", "agents/base/docker-compose.yml",
            "agents/zenas/docker-compose.yml", "agents/zenas/docker-compose.za.yml"]


def _plan(before: str, after: str, record: dict, diffs: dict[tuple[str, str], list[str]],
          known: set[str] | None = None) -> dict:
    return di.plan(before, after, record, diff=lambda b, a: diffs[(b, a)],
                   known=lambda sha: sha in (known if known is not None else {A, B, C, D}),
                   composes=COMPOSES, specs=_specs)


# ---------------------------------------------------------------- changed-app set

def test_a_main_change_builds_both_main_stacks_and_no_room() -> None:
    result = _plan(A, B, {}, {(A, B): ["tank/main.py"]})
    assert result["build"] == ["docker-compose.yml", "docker-compose.za.yml"]
    assert {i["compose"] for i in result["images"]} == set(result["build"])
    assert result["images"][0]["repo"] == "ghcr.io/tervory-ai/tervory-tank/main-tank"


def test_a_room_change_builds_only_that_room_and_its_za_copy() -> None:
    result = _plan(A, B, {}, {(A, B): ["agents/zenas/app.py", "docs/notes.md"]})
    assert result["build"] == ["agents/zenas/docker-compose.yml", "agents/zenas/docker-compose.za.yml"]


def test_shared_room_code_builds_every_room_but_not_main() -> None:
    result = _plan(A, B, {}, {(A, B): ["agents/_chassis/chassis/app.py"]})
    assert result["build"] == COMPOSES[2:]


def test_nothing_deployable_builds_nothing() -> None:
    result = _plan(A, B, {}, {(A, B): ["docs/x.md", "agents/README.md"]})
    assert result["build"] == [] and result["images"] == []


def test_an_app_behind_its_last_good_deploy_gets_its_own_changes_back() -> None:
    # The previous run (A) failed main, so the room never deployed C..A changes. The room's
    # record says it last ran C: its own paths since C are included, main's are not re-added.
    record = {"apps": {"base": {"live": {"sha": C}}, "main": {"live": {"sha": A}}}}
    diffs = {(A, B): ["tank/x.py"], (C, B): ["agents/base/app.py", "tank/y.py", "agents/zenas/z.py"]}
    result = _plan(A, B, record, diffs)
    assert "agents/base/app.py" in result["paths"]
    assert "tank/y.py" not in result["paths"] and "agents/zenas/z.py" not in result["paths"]
    assert result["build"] == ["docker-compose.yml", "docker-compose.za.yml", "agents/base/docker-compose.yml"]


def test_a_recorded_commit_missing_from_the_clone_counts_as_changed() -> None:
    record = {"apps": {"zenas": {"live": {"sha": D}}}}
    result = _plan(A, B, record, {(A, B): []}, known={A, B})
    assert "agents/zenas/docker-compose.yml" in result["build"]


def test_an_app_already_on_this_commit_adds_nothing() -> None:
    record = {"apps": {"base": {"live": {"sha": B}}}}
    assert _plan(A, B, record, {(A, B): []})["build"] == []


def test_deploy_names_keep_main_first_and_follow_room_folders() -> None:
    names = di.deploy_names(["tank/a.py", "agents/market_lab/x.py"], ["base", "market_lab", "zenas"], ["agent-zenas-za"])
    assert names == ["main", "tervory-tank-za", "agent-market-lab"]
    every = di.deploy_names(["agents/_template/x"], ["base", "zenas"], ["agent-zenas-za"])
    assert every == ["agent-base", "agent-zenas", "agent-zenas-za"]


def test_plan_reads_real_git_ranges(tmp_path: Path) -> None:
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=tmp_path, capture_output=True, text=True, check=True).stdout.strip()
    git("init", "-q")
    git("config", "user.email", "t@example.invalid")
    git("config", "user.name", "t")
    (tmp_path / "tank").mkdir()
    (tmp_path / "tank" / "a.py").write_text("1")
    git("add", ".")
    git("commit", "-qm", "one")
    first = git("rev-parse", "HEAD")
    (tmp_path / "agents" / "zenas").mkdir(parents=True)
    (tmp_path / "agents" / "zenas" / "b.py").write_text("2")
    git("add", ".")
    git("commit", "-qm", "two")
    second = git("rev-parse", "HEAD")
    assert di.git_paths(first, second, tmp_path) == ["agents/zenas/b.py"]
    assert di.git_paths("", second, tmp_path) == ["agents/zenas/b.py"]
    assert di.has_commit(first, tmp_path) and not di.has_commit("e" * 40, tmp_path)


# ---------------------------------------------------------------- settle window

def test_settle_waits_for_a_quiet_main_then_deploys() -> None:
    kw = dict(after=A, head=A, oldest_at=1000.0, settle_s=600, max_hold_s=3600)
    assert di.settle_decision(head_at=1000.0, now=1300.0, **kw) == "wait"
    assert di.settle_decision(head_at=1000.0, now=1600.0, **kw) == "deploy"


def test_a_newer_merge_supersedes_this_run() -> None:
    assert di.settle_decision(after=A, head=B, head_at=1000.0, oldest_at=900.0, now=1100.0,
                              settle_s=600, max_hold_s=3600) == "superseded"


def test_max_hold_stops_a_stream_of_merges_holding_a_deploy_back() -> None:
    assert di.settle_decision(after=A, head=B, head_at=4500.0, oldest_at=900.0, now=4600.0,
                              settle_s=600, max_hold_s=3600) == "deploy"
    assert di.settle_decision(after=A, head=A, head_at=4500.0, oldest_at=900.0, now=4600.0,
                              settle_s=600, max_hold_s=3600) == "deploy"


def test_unknown_tip_of_main_deploys_as_today() -> None:
    assert di.settle_decision(after=A, head="", head_at=0.0, oldest_at=0.0, now=1.0) == "deploy"


def _at(minutes: float) -> datetime:
    return datetime(2026, 11, 8, 12, tzinfo=timezone.utc) + timedelta(minutes=minutes)


def test_a_burst_of_merges_becomes_one_deploy_with_every_changed_app() -> None:
    merges = [di.Merge(_at(m), sha, frozenset(apps)) for m, sha, apps in [
        (0, A, {"main"}), (3, B, {"agent-base"}), (7, C, set()), (9, D, {"agent-zenas"})]]
    deploys = di.simulate(merges, settle_s=600, max_hold_s=3600, cost_s=lambda apps: 120)
    assert deploys == [(_at(19), frozenset({"main", "agent-base", "agent-zenas"}))]


def test_merges_far_apart_still_deploy_separately() -> None:
    merges = [di.Merge(_at(0), A, frozenset({"main"})), di.Merge(_at(60), B, frozenset({"main"}))]
    deploys = di.simulate(merges, settle_s=600, max_hold_s=3600, cost_s=lambda apps: 120)
    assert [at for at, _ in deploys] == [_at(10), _at(70)]


def test_a_steady_stream_deploys_at_max_hold_and_loses_nothing() -> None:
    merges = [di.Merge(_at(m), f"{m:040d}", frozenset({f"agent-{m}"})) for m in range(0, 100, 5)]
    deploys = di.simulate(merges, settle_s=600, max_hold_s=1800, cost_s=lambda apps: 60)
    assert deploys[0][0] == _at(30)
    deployed = frozenset().union(*(apps for _, apps in deploys))
    assert deployed == frozenset().union(*(m.apps for m in merges))


def test_merges_during_a_deploy_wait_for_it_and_go_together() -> None:
    merges = [di.Merge(_at(0), A, frozenset({"main"})), di.Merge(_at(15), B, frozenset({"agent-base"})),
              di.Merge(_at(16), C, frozenset({"agent-zenas"}))]
    deploys = di.simulate(merges, settle_s=600, max_hold_s=3600, cost_s=lambda apps: 30 * 60)
    assert deploys == [(_at(10), frozenset({"main"})), (_at(40), frozenset({"agent-base", "agent-zenas"}))]


# ---------------------------------------------------------------- promote, restore, rollback record

def _repo(service: str) -> str:
    return di.image_repo("docker-compose.yml", service)


def test_promote_moves_live_and_records_the_previous_digests() -> None:
    reg = FakeRegistry({f"{_repo('tank')}:{B}": "sha256:tb", f"{_repo('workspace')}:{B}": "sha256:wb",
                        f"{_repo('tank')}:live": "sha256:ta", f"{_repo('workspace')}:live": "sha256:wa"})
    record = {"apps": {"main": {"live": {"sha": A, "images": {"tank": "sha256:ta", "workspace": "sha256:wa"}}}}}
    entry = di.promote("docker-compose.yml", B, reg, record, specs=_specs)
    assert reg.tags[f"{_repo('tank')}:live"] == "sha256:tb"
    assert reg.tags[f"{_repo('tank')}:previous"] == "sha256:ta"
    assert entry["live"] == {"sha": B, "images": {"tank": "sha256:tb", "workspace": "sha256:wb"}}
    assert entry["previous"] == {"sha": A, "images": {"tank": "sha256:ta", "workspace": "sha256:wa"}}
    assert record["apps"]["main"] is entry


def test_promote_moves_no_tag_when_any_image_is_missing() -> None:
    reg = FakeRegistry({f"{_repo('tank')}:{B}": "sha256:tb", f"{_repo('tank')}:live": "sha256:ta"})
    with pytest.raises(di.MissingImage, match="workspace"):
        di.promote("docker-compose.yml", B, reg, {}, specs=_specs)
    assert reg.moves == [] and reg.tags[f"{_repo('tank')}:live"] == "sha256:ta"


def test_first_promote_records_what_was_live_before_any_record() -> None:
    reg = FakeRegistry({f"{_repo('tank')}:{B}": "sha256:tb", f"{_repo('workspace')}:{B}": "sha256:wb",
                        f"{_repo('tank')}:live": "sha256:old"})
    entry = di.promote("docker-compose.yml", B, reg, {}, specs=_specs)
    assert entry["previous"] == {"sha": "", "images": {"tank": "sha256:old"}}


def test_restore_after_a_failed_deploy_puts_the_previous_images_back() -> None:
    reg = FakeRegistry({f"{_repo('tank')}:{B}": "sha256:tb", f"{_repo('workspace')}:{B}": "sha256:wb",
                        f"{_repo('tank')}:live": "sha256:ta", f"{_repo('workspace')}:live": "sha256:wa"})
    record = {"apps": {"main": {"live": {"sha": A, "images": {"tank": "sha256:ta", "workspace": "sha256:wa"}}}}}
    di.promote("docker-compose.yml", B, reg, record, specs=_specs)
    assert di.restore("docker-compose.yml", reg, record) is True
    assert reg.tags[f"{_repo('tank')}:live"] == "sha256:ta" and reg.tags[f"{_repo('workspace')}:live"] == "sha256:wa"
    entry = record["apps"]["main"]
    assert entry["live"]["sha"] == A and entry["failed"]["sha"] == B and entry["state"] == "restored"


def test_restore_without_a_previous_image_says_so() -> None:
    assert di.restore("docker-compose.yml", FakeRegistry(), {}) is False


def test_rollback_is_one_step_and_a_second_rollback_goes_forward() -> None:
    reg = FakeRegistry({f"{_repo('tank')}:live": "sha256:tb", f"{_repo('workspace')}:live": "sha256:wb"})
    record = {"apps": {"main": {"live": {"sha": B, "images": {"tank": "sha256:tb", "workspace": "sha256:wb"}},
                                "previous": {"sha": A, "images": {"tank": "sha256:ta", "workspace": "sha256:wa"}}}}}
    di.rollback("docker-compose.yml", reg, record, specs=_specs)
    assert reg.tags[f"{_repo('tank')}:live"] == "sha256:ta"
    assert record["apps"]["main"]["live"]["sha"] == A and record["apps"]["main"]["previous"]["sha"] == B
    di.rollback("docker-compose.yml", reg, record, specs=_specs)
    assert reg.tags[f"{_repo('tank')}:live"] == "sha256:tb" and record["apps"]["main"]["live"]["sha"] == B


def test_rollback_to_a_named_commit_uses_its_images() -> None:
    reg = FakeRegistry({f"{_repo('tank')}:{C}": "sha256:tc", f"{_repo('workspace')}:{C}": "sha256:wc",
                        f"{_repo('tank')}:live": "sha256:tb", f"{_repo('workspace')}:live": "sha256:wb"})
    record = {"apps": {"main": {"live": {"sha": B, "images": {"tank": "sha256:tb", "workspace": "sha256:wb"}}}}}
    entry = di.rollback("docker-compose.yml", reg, record, C, specs=_specs)
    assert entry["live"] == {"sha": C, "images": {"tank": "sha256:tc", "workspace": "sha256:wc"}}
    assert reg.tags[f"{_repo('workspace')}:live"] == "sha256:wc"
    with pytest.raises(di.MissingImage):
        di.rollback("docker-compose.yml", reg, record, D, specs=_specs)
    with pytest.raises(ValueError):
        di.rollback("docker-compose.yml", reg, record, "main", specs=_specs)


def test_rollback_without_a_record_refuses_and_moves_nothing() -> None:
    reg = FakeRegistry({f"{_repo('tank')}:live": "sha256:tb"})
    with pytest.raises(di.MissingImage):
        di.rollback("docker-compose.yml", reg, {}, specs=_specs)
    assert reg.moves == []


# ---------------------------------------------------------------- compose files and images

def test_every_built_service_pulls_its_ghcr_live_image() -> None:
    composes = di.deployable_composes()
    assert "docker-compose.yml" in composes and "agents/zenas/docker-compose.za.yml" in composes
    for compose in composes:
        assert di.missing_image_lines(compose) == [], f"run deploy_images.py sync-compose ({compose})"
        assert di.add_image_lines(compose) == (ROOT / compose).read_text(encoding="utf-8")
        # The image names are unique, so two services never overwrite each other's :live.
    repos = [s.repo for c in composes for s in di.built_services(c)]
    assert len(repos) == len(set(repos))


def test_sync_compose_only_adds_image_lines(tmp_path: Path) -> None:
    compose = tmp_path / "docker-compose.yml"
    compose.write_text(
        "# top\nservices:\n  web:\n    # the site\n    build: ./site\n    restart: always\n"
        "  Ferry:\n    image: ferry\n    build:\n      context: .\n      dockerfile: tor/Dockerfile\n"
        "  db:\n    image: postgres:16\nvolumes:\n  data:\n")
    text = di.add_image_lines("docker-compose.yml", tmp_path)
    assert text == ("# top\nservices:\n  web:\n    # the site\n"
                    "    image: ghcr.io/tervory-ai/tervory-tank/main-web:live\n    build: ./site\n    restart: always\n"
                    "  Ferry:\n    image: ghcr.io/tervory-ai/tervory-tank/main-ferry:live\n    build:\n      context: .\n"
                    "      dockerfile: tor/Dockerfile\n  db:\n    image: postgres:16\nvolumes:\n  data:\n")
    assert yaml.safe_load(text)["services"]["db"] == {"image": "postgres:16"}


@pytest.mark.parametrize("compose,key", [
    ("docker-compose.yml", "main"), ("docker-compose.za.yml", "za"),
    ("agents/zenas/docker-compose.yml", "zenas"), ("agents/zenas/docker-compose.za.yml", "zenas-za"),
    ("agents/market_lab/docker-compose.yml", "market-lab"), ("agents/ghost/docker-compose.enforce.yml", "ghost-enforce"),
])
def test_compose_keys(compose: str, key: str) -> None:
    assert di.compose_key(compose) == key


def test_compose_for_coolify_app_records() -> None:
    assert di.compose_for_app({"base_directory": "/", "docker_compose_location": "/docker-compose.yml"}) == "docker-compose.yml"
    assert di.compose_for_app({"base_directory": "/agents/zenas", "docker_compose_location": "/docker-compose.za.yml"}) \
        == "agents/zenas/docker-compose.za.yml"
    with pytest.raises(ValueError):
        di.compose_for_app({"base_directory": "/agents/../..", "docker_compose_location": "/x.yml"})


def test_build_command_matches_the_compose_build() -> None:
    tank = next(s for s in di.built_services("docker-compose.yml", sha=B) if s.service == "tank")
    command = di.build_command(tank, B)
    assert command[-1] == "tank" and f"GIT_SHA={B}" in command
    assert f"{tank.repo}:{B}" in command and "--push" in command and "--provenance=false" in command
    assert f"org.opencontainers.image.revision={B}" in command
    workspace = next(s for s in di.built_services("docker-compose.yml", sha=B) if s.service == "workspace")
    assert "cli=cli" in di.build_command(workspace, B)
    zenas = next(s for s in di.built_services("agents/zenas/docker-compose.yml") if s.service == "agent-zenas")
    assert (zenas.context, zenas.dockerfile) == ("agents", "agents/zenas/Dockerfile")
    forge = next(s for s in di.built_services("agents/rig/docker-compose.yml") if s.service == "rig-forge")
    assert di.build_command(forge, B)[-3:-1] == ["--target", "runtime"]


def test_build_args_without_a_default_are_refused(tmp_path: Path) -> None:
    (tmp_path / "docker-compose.yml").write_text(
        "services:\n  web:\n    build:\n      context: .\n      args:\n        TOKEN: ${TOKEN}\n")
    with pytest.raises(ValueError, match="TOKEN"):
        di.built_services("docker-compose.yml", tmp_path)


def test_main_prefixes_are_the_deploy_scripts_prefixes(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _deploy_script(monkeypatch)
    assert mod.MAIN_PREFIXES == di.MAIN_PREFIXES and mod.ALL_ROOMS_PREFIXES == di.ALL_ROOMS_PREFIXES
    assert mod.wanted(["tank/a.py", "agents/zenas/x.py"]) == (True, {"agent-zenas"}, False)


# ---------------------------------------------------------------- deploy_changed.py in image mode (fakes only)

def _deploy_script(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("COOLIFY_URL", "https://coolify.example")
    monkeypatch.setenv("COOLIFY_TOKEN", "test-token")
    monkeypatch.setenv("AFTER", B)
    monkeypatch.syspath_prepend(str(SCRIPTS))
    path = SCRIPTS / "deploy_changed.py"
    spec = importlib.util.spec_from_file_location("deploy_changed_images", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["deploy_changed_images"] = module
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "verify_main_scope", lambda api: True)
    monkeypatch.setattr(module.time, "sleep", lambda s: None)
    return module


APPS = [
    {"name": "main", "uuid": "xnmc0jkz8j9i5jh1jwanbsfv", "base_directory": "/", "docker_compose_location": "/docker-compose.yml"},
    {"name": "tervory-tank-za", "uuid": "za-uuid", "base_directory": "/", "docker_compose_location": "/docker-compose.za.yml"},
    {"name": "agent-zenas", "uuid": "room-uuid", "base_directory": "/agents/zenas", "docker_compose_location": "/docker-compose.yml"},
]


def _image_mode(monkeypatch, tmp_path, mod, build: list[str], status: str = "running:healthy",
                record: dict | None = None):
    images = [{"compose": c, "service": s.service} for c in build for s in _specs(c)]
    plan = {"paths": ["tank/main.py", "agents/zenas/app.py"], "build": build, "images": images}
    (tmp_path / "plan.json").write_text(json.dumps(plan))
    (tmp_path / "record.json").write_text(json.dumps(record or {}))
    monkeypatch.setattr(mod, "PLAN_PATH", str(tmp_path / "plan.json"))
    monkeypatch.setattr(mod, "RECORD_PATH", str(tmp_path / "record.json"))
    tags = {}
    for c in build:
        for s in _specs(c):
            repo = di.image_repo(c, s.service)
            tags[f"{repo}:{B}"] = f"sha256:{s.service}-new"
            tags[f"{repo}:live"] = f"sha256:{s.service}-old"
    reg = FakeRegistry(tags)
    monkeypatch.setattr(mod, "_registry", reg)
    calls: list[str] = []

    def api(method: str, path: str):
        calls.append(f"{method} {path}")
        if path == "/applications":
            return 200, APPS
        if path.startswith("/applications/"):
            return 200, {"status": status}
        return 200, []

    monkeypatch.setattr(mod, "api", api)
    return reg, calls


def test_image_mode_promotes_before_each_deploy_and_writes_the_record(monkeypatch, tmp_path) -> None:
    mod = _deploy_script(monkeypatch)
    build = ["docker-compose.yml", "docker-compose.za.yml", "agents/zenas/docker-compose.yml"]
    reg, _ = _image_mode(monkeypatch, tmp_path, mod, build)
    order: list[str] = []

    def deploy(uuid: str, name: str) -> bool:
        compose = mod._compose[uuid]
        live = reg.tags[f"{di.image_repo(compose, _specs(compose)[0].service)}:live"]
        order.append(f"{name}:{live}")
        return True

    monkeypatch.setattr(mod, "deploy", deploy)
    monkeypatch.setattr(mod, "wait_for", lambda uuid, name, timeout_s=900: True)
    assert mod.main() == 0
    assert order[0] == "main:sha256:tank-new"
    assert sorted(order[1:]) == ["agent-zenas:sha256:agent-zenas-new", "tervory-tank-za:sha256:app-new"]
    record = json.loads((tmp_path / "record.json").read_text())
    assert record["apps"]["main"]["live"]["sha"] == B
    assert record["apps"]["main"]["previous"]["images"]["tank"] == "sha256:tank-old"
    assert set(record["apps"]) == {"main", "za", "zenas"}


def test_a_failed_deploy_puts_live_back_and_redeploys_the_old_images(monkeypatch, tmp_path) -> None:
    mod = _deploy_script(monkeypatch)
    reg, _ = _image_mode(monkeypatch, tmp_path, mod, ["agents/zenas/docker-compose.yml"])
    repo = di.image_repo("agents/zenas/docker-compose.yml", "agent-zenas")
    deploys: list[str] = []
    monkeypatch.setattr(mod, "changed_paths", lambda: ["agents/zenas/app.py"])
    monkeypatch.setattr(mod, "deploy", lambda uuid, name: deploys.append(reg.tags[f"{repo}:live"]) or True)
    waits = iter([False, True])
    monkeypatch.setattr(mod, "wait_for", lambda uuid, name, timeout_s=900: next(waits))
    assert mod.main() == 1
    assert deploys == ["sha256:agent-zenas-new", "sha256:agent-zenas-old"]
    assert reg.tags[f"{repo}:live"] == "sha256:agent-zenas-old"
    record = json.loads((tmp_path / "record.json").read_text())
    assert record["apps"]["zenas"]["state"] == "restored" and record["apps"]["zenas"]["failed"]["sha"] == B


def test_a_failed_health_check_after_a_finished_deploy_also_rolls_back(monkeypatch, tmp_path, capsys) -> None:
    mod = _deploy_script(monkeypatch)
    reg, _ = _image_mode(monkeypatch, tmp_path, mod, ["agents/zenas/docker-compose.yml"], status="running:unhealthy")
    monkeypatch.setattr(mod, "HEALTH_WAIT_S", 0)
    monkeypatch.setattr(mod, "changed_paths", lambda: ["agents/zenas/app.py"])
    monkeypatch.setattr(mod, "deploy", lambda uuid, name: True)
    monkeypatch.setattr(mod, "wait_for", lambda uuid, name, timeout_s=900: True)
    monkeypatch.setattr(mod, "healthy", lambda uuid, name, wait_s=0: False)
    assert mod.main() == 1
    assert reg.tags[f"{di.image_repo('agents/zenas/docker-compose.yml', 'agent-zenas')}:live"] == "sha256:agent-zenas-old"
    assert "rolled back" in capsys.readouterr().out


def test_health_check_reads_coolify_status(monkeypatch, tmp_path) -> None:
    mod = _deploy_script(monkeypatch)
    _image_mode(monkeypatch, tmp_path, mod, [], status="running:healthy")
    assert mod.healthy("room-uuid", "agent-zenas", wait_s=0) is True
    _image_mode(monkeypatch, tmp_path, mod, [], status="exited:unhealthy")
    assert mod.healthy("room-uuid", "agent-zenas", wait_s=0) is False


def test_a_missing_image_stops_only_that_app_and_moves_no_tag(monkeypatch, tmp_path, capsys) -> None:
    mod = _deploy_script(monkeypatch)
    reg, _ = _image_mode(monkeypatch, tmp_path, mod, ["agents/zenas/docker-compose.yml"])
    del reg.tags[f"{di.image_repo('agents/zenas/docker-compose.yml', 'agent-zenas')}:{B}"]
    deployed: list[str] = []
    monkeypatch.setattr(mod, "changed_paths", lambda: ["agents/zenas/app.py"])
    monkeypatch.setattr(mod, "deploy", lambda uuid, name: deployed.append(name) or True)
    monkeypatch.setattr(mod, "wait_for", lambda uuid, name, timeout_s=900: True)
    assert mod.main() == 1
    assert deployed == [] and reg.moves == []
    assert "current images keep serving" in capsys.readouterr().out


def test_a_retry_with_no_new_image_deploys_without_moving_tags(monkeypatch, tmp_path) -> None:
    mod = _deploy_script(monkeypatch)
    reg, _ = _image_mode(monkeypatch, tmp_path, mod, [])
    deployed: list[str] = []
    monkeypatch.setattr(mod, "changed_paths", lambda: ["agents/zenas/app.py"])
    monkeypatch.setattr(mod, "deploy", lambda uuid, name: deployed.append(name) or True)
    monkeypatch.setattr(mod, "wait_for", lambda uuid, name, timeout_s=900: True)
    assert mod.main() == 0 and deployed == ["agent-zenas"] and reg.moves == []


def test_a_timed_out_deploy_keeps_the_new_live_tag(monkeypatch, tmp_path) -> None:
    mod = _deploy_script(monkeypatch)
    reg, _ = _image_mode(monkeypatch, tmp_path, mod, ["agents/zenas/docker-compose.yml"])
    monkeypatch.setattr(mod, "changed_paths", lambda: ["agents/zenas/app.py"])
    monkeypatch.setattr(mod, "deploy", lambda uuid, name: True)

    def wait_for(uuid, name, timeout_s=900):
        mod._timed_out.add(uuid)
        return False

    monkeypatch.setattr(mod, "wait_for", wait_for)
    assert mod.main() == 1
    assert reg.tags[f"{di.image_repo('agents/zenas/docker-compose.yml', 'agent-zenas')}:live"] == "sha256:agent-zenas-new"


def test_rollback_command_goes_back_one_step_and_redeploys(monkeypatch, tmp_path) -> None:
    mod = _deploy_script(monkeypatch)
    compose = "agents/zenas/docker-compose.yml"
    repo = di.image_repo(compose, "agent-zenas")
    record = {"apps": {"zenas": {"live": {"sha": B, "images": {"agent-zenas": "sha256:new"}},
                                 "previous": {"sha": A, "images": {"agent-zenas": "sha256:old"}}}}}
    reg, _ = _image_mode(monkeypatch, tmp_path, mod, [], record=record)
    reg.tags[f"{repo}:live"] = "sha256:new"
    monkeypatch.setattr(mod, "api", lambda method, path: (200, {**APPS[2], "status": "running:healthy"}))
    monkeypatch.setenv("APP", "room-uuid")
    deployed: list[str] = []
    monkeypatch.setattr(mod, "deploy", lambda uuid, name: deployed.append(reg.tags[f"{repo}:live"]) or True)
    monkeypatch.setattr(mod, "wait_for", lambda uuid, name, timeout_s=900: True)
    assert mod.rollback_main() == 0
    assert deployed == ["sha256:old"]
    saved = json.loads((tmp_path / "record.json").read_text())
    assert saved["apps"]["zenas"]["live"]["sha"] == A and saved["apps"]["zenas"]["previous"]["sha"] == B


def test_without_a_plan_nothing_changes_for_coolify_ops(monkeypatch) -> None:
    mod = _deploy_script(monkeypatch)
    assert mod.PLAN_PATH == "" and mod.release("room-uuid", "agent-zenas") is True


# ---------------------------------------------------------------- the workflow

def _flow() -> dict:
    return yaml.safe_load((ROOT / ".github/workflows/deploy-on-merge.yml").read_text(encoding="utf-8"))


def test_workflow_settles_plans_builds_then_deploys() -> None:
    jobs = _flow()["jobs"]
    assert list(jobs) == ["settle", "plan", "build", "deploy", "live-check"]
    assert jobs["settle"]["permissions"] == {"contents": "read", "actions": "write"}
    assert any("deploy_images.py settle" in step.get("run", "") for step in jobs["settle"]["steps"])
    assert jobs["plan"]["needs"] == "settle"
    assert jobs["build"]["strategy"]["matrix"]["include"] == "${{ fromJSON(needs.plan.outputs.images) }}"
    assert jobs["build"]["strategy"]["fail-fast"] is False
    assert jobs["build"]["permissions"] == {"contents": "read", "packages": "write"}
    assert jobs["deploy"]["needs"] == ["settle", "plan", "build"]
    assert "!cancelled()" in jobs["deploy"]["if"]
    text = json.dumps(jobs["deploy"]["steps"])
    assert "DEPLOY_PLAN" in text and "DEPLOY_RECORD" in text and "deploy-record" in text
    # The previous deployed commit only ever comes from a push run, never a manual one.
    assert "event=push" in json.dumps(jobs["settle"]["steps"])


def test_the_build_job_never_reaches_coolify() -> None:
    build = _flow()["jobs"]["build"]
    assert "COOLIFY" not in json.dumps(build)


def test_coolify_ops_rollback_is_one_main_only_step_in_the_deploy_group() -> None:
    ops = yaml.safe_load((ROOT / ".github/workflows/coolify-ops.yml").read_text(encoding="utf-8"))
    job = ops["jobs"]["rollback"]
    assert job["if"] == "inputs.op == 'rollback' && github.ref == 'refs/heads/main'"
    assert ops["jobs"]["op"]["if"] == "inputs.op != 'rollback'"
    assert "inputs.op == 'rollback'" in ops["concurrency"]["group"].split("&& 'coolify-deploy'")[0]
    assert any("deploy_changed.py rollback" in step.get("run", "") for step in job["steps"])
