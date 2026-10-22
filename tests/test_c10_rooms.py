"""C10: Radix and Tisan rooms. No database and no network."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "_chassis"))
SCRIPT = ROOT / "agents" / "check_isolation.sh"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _service_block(compose: str, name: str) -> str:
    lines = compose.splitlines()
    start = next(index for index, line in enumerate(lines) if line == f"  {name}:")
    chunk: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("  ") and not line.startswith("   "):
            break
        chunk.append(line)
    return "\n".join(chunk)


def test_main_compose_joins_both_corridors_and_both_keys() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    services = compose["services"]
    for corridor in ("tervory-gw-radix", "tervory-gw-tisan"):
        assert compose["networks"][corridor]["external"] is True
        assert compose["networks"][corridor]["name"] == corridor
        for name in ("tank", "postgres", "hermes"):
            assert corridor in services[name]["networks"]
        for name in ("redis", "qdrant", "litellm", "searxng", "tiger", "workspace", "agent-roles"):
            assert corridor not in (services[name].get("networks") or [])
    for key in ("TANK_KEY_RADIX", "TANK_KEY_TISAN"):
        assert services["tank"]["environment"][key] == f"${{{key}:-}}"
        assert services["hermes"]["environment"][key] == f"${{{key}:-}}"
    roles = services["agent-roles"]["environment"]
    assert "AGENT_DB_PASSWORD_RADIX" in roles
    assert "AGENT_DB_PASSWORD_TISAN" in roles
    text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "docker network create --internal tervory-gw-radix" in text
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    for name in (
        "TANK_KEY_RADIX=",
        "TANK_KEY_TISAN=",
        "AGENT_DB_PASSWORD_RADIX=",
        "AGENT_DB_PASSWORD_TISAN=",
        "RADIX_ALLOWED_HOSTS=",
    ):
        assert name in example


@pytest.mark.parametrize(
    ("folder", "service", "corridor", "role", "key"),
    [
        ("tisan", "agent-tisan", "tervory-gw-tisan", "agent_tisan", "TANK_KEY_TISAN"),
    ],
)
def test_agent_compose_is_one_corridor_with_a_limit_and_a_healthcheck(
    folder: str, service: str, corridor: str, role: str, key: str
) -> None:
    box = yaml.safe_load((ROOT / "agents" / folder / "docker-compose.yml").read_text(encoding="utf-8"))
    assert list(box["networks"]) == ["gw"]
    assert box["networks"]["gw"]["external"] is True
    assert box["networks"]["gw"]["name"] == corridor
    spec = box["services"][service]
    assert spec["networks"] == ["gw"]
    # Founder, 14 Oct 2026: Tisan's room is 1g so a site build can finish. Radix stays 256m.
    assert spec["mem_limit"] == ("1g" if folder == "tisan" else "256m")
    assert spec["cpus"] in (0.25, "0.25")
    assert "health" in str(spec["healthcheck"]["test"])
    env = spec["environment"]
    assert env["DATABASE_URL"].startswith(f"postgresql://{role}:")
    assert env["TANK_KEY"] == f"${{{key}:-}}"
    assert env["HERMES_URL"] == "http://hermes:8000"
    assert "POSTGRES_USER" not in env
    assert "POSTGRES_PASSWORD" not in env
    raw = (ROOT / "agents" / folder / "docker-compose.yml").read_text(encoding="utf-8")
    assert "POSTGRES_USER" not in raw
    assert "POSTGRES_PASSWORD" not in raw
    readme = (ROOT / "agents" / folder / "README.md").read_text(encoding="utf-8")
    assert len(readme.splitlines()) > 8


def test_radix_reaches_one_host_only_through_the_proxy() -> None:
    raw = (ROOT / "agents" / "radix" / "docker-compose.yml").read_text(encoding="utf-8")
    box = yaml.safe_load(raw)
    assert list(box["networks"]) == ["gw", "proxy-link", "egress"]
    assert box["networks"]["gw"]["external"] is True
    assert box["networks"]["gw"]["name"] == "tervory-gw-radix"
    assert box["networks"]["proxy-link"]["internal"] is True
    outward = [name for name, spec in box["networks"].items() if spec.get("internal") is False]
    assert outward == ["egress"]

    agent = box["services"]["agent-radix"]
    proxy = box["services"]["egress-proxy"]
    assert agent["networks"] == ["gw", "proxy-link"]
    assert "egress" not in agent["networks"]
    on_egress = [name for name, spec in box["services"].items() if "egress" in spec.get("networks", [])]
    assert on_egress == ["egress-proxy"]
    assert proxy["networks"] == ["proxy-link", "egress"]
    assert "ports" not in agent
    assert "ports" not in proxy

    assert agent["mem_limit"] == "256m"
    assert agent["cpus"] in (0.25, "0.25")
    assert "health" in str(agent["healthcheck"]["test"])
    env = agent["environment"]
    assert env["DATABASE_URL"].startswith("postgresql://agent_radix:")
    assert env["TANK_KEY"] == "${TANK_KEY_RADIX:-}"
    assert env["HERMES_URL"] == "http://hermes:8000"
    assert env["RADIX_ALLOWED_HOSTS"] == "lokd.co.za"
    assert env["RADIX_EGRESS_PROXY"] == "http://egress-proxy:8080"
    assert "POSTGRES_USER" not in env
    assert "POSTGRES_PASSWORD" not in env
    assert "POSTGRES_USER" not in raw
    assert "POSTGRES_PASSWORD" not in raw
    readme = (ROOT / "agents" / "radix" / "README.md").read_text(encoding="utf-8")
    assert len(readme.splitlines()) > 8


def test_radix_client_refuses_hosts_that_are_not_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RADIX_ALLOWED_HOSTS", "")
    net = _load("radix_net", ROOT / "agents" / "radix" / "net.py")
    assert net.allowed_hosts() == frozenset()
    client = net.Client()
    for url in ("https://example.com/scan", "http://1.1.1.1/", "https://tank:8000/health", ""):
        with pytest.raises(net.HostNotAllowed):
            client.get(url)
    listed = net.allowed_hosts("reports.example, OTHER.Example.")
    assert net.require_allowed("https://reports.example/a", listed) == "reports.example"
    assert net.require_allowed("http://other.example/b", listed) == "other.example"
    guarded = net.Client(allow=listed)
    with pytest.raises(net.HostNotAllowed) as raised:
        guarded.request("GET", "https://evil.example/x")
    assert raised.value.host == "evil.example"


def test_internet_check_runs_only_on_the_radix_corridor() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    subprocess.check_call(["sh", "-n", str(SCRIPT)])
    start = text.index('if [ "$radix_corridor" -eq 1 ]; then')
    end = text.index("\nfi\n", start)
    block = text[start:end]
    assert 'socket.create_connection(("1.1.1.1", 443), 5)' in block
    assert block.count("internet is unreachable") == 2
    assert text.count("internet is unreachable") == 2
    assert "tervory-gw-tisan" not in text
    assert "tervory-gw-radix" in text


def test_readme_has_one_row_each() -> None:
    text = (ROOT / "agents" / "README.md").read_text(encoding="utf-8")
    assert "| Radix | `tervory-gw-radix`" in text
    assert "| Tisan | `tervory-gw-tisan`" in text


def _load_room_app(folder: str):
    """Load a room's app.py so its bare imports (e.g. gold_sources) find that room's files.

    Other tests put agents/rig on sys.path and can leave Rig's gold_sources cached,
    so put this room's folder first and hide any cached copy while loading. Both
    are put back afterwards so later tests see what they saw before.
    """
    room = str(ROOT / "agents" / folder)
    cached = sys.modules.pop("gold_sources", None)
    sys.path.insert(0, room)
    try:
        return _load(f"{folder}_app", ROOT / "agents" / folder / "app.py")
    finally:
        sys.path.remove(room)
        if cached is not None:
            sys.modules["gold_sources"] = cached
        else:
            sys.modules.pop("gold_sources", None)


def test_ping_schedules_are_the_template_heartbeat() -> None:
    for folder, agent in (("radix", "radix"), ("tisan", "tisan")):
        module = _load_room_app(folder)
        assert module.app.state.agent == agent
        handlers = set(module.app.state.handlers)
        # RX1 adds scan on Radix. TS1 adds scaffold on Tisan. TS2 adds figma.
        # Each room keeps ping, and neither assertion may strip the other room's job.
        if folder == "radix":
            assert handlers == {"ping", "scan"}
        else:
            assert handlers == {"ping", "scaffold", "figma"}
            # Founder, 14 Oct 2026: a site build is allowed 10 minutes.
            assert module.app.state.job_timeouts == {"scaffold": 600}
        assert module.app.state.schedules == [
            {
                "tenant_id": "00000000-0000-0000-0000-000000000001",
                "cron": "*/5 * * * *",
                "kind": "ping",
                "input": {"heartbeat": True},
            }
        ]
