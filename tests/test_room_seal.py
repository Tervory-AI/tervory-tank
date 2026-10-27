"""SEAL-1: sealed room services must stay off Coolify's internet-facing app network.

Coolify's normal compose mode adds its own app network (not internal) to every
service without network_mode. A sealed service, one declared only on internal
networks, would then reach the internet and every other service in the app.
Raw Compose Deployment mode deploys the file as written, so a compose file that
has a sealed service must say so with `# coolify: raw compose` on its first line.
No network, Docker or secrets are needed.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import httpx
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
RAW_MARKER = "# coolify: raw compose"
COOLIFY_APP_NETWORK = "<coolify app network>"
# Autumbra Watch/Enforce are optional until dogfood; seal-check reports
# absence without failing. Tests expect that status line so Autumbra coverage stays honest.
AUTUMBRA_ABSENT_LINE = (
    "autumbra: no Watch/Enforce rooms running "
    "(ok until dogfood; pin EXPECTED_SEALED after first clean run)"
)
ROOM_FILES = sorted((ROOT / "agents").glob("*/docker-compose*.yml"))
SEAL_CHECK = ROOT / "ops" / "seal-check.sh"
FIXTURES = ROOT / "tests" / "fixtures" / "seal_check"


def is_raw(text: str) -> bool:
    return text.splitlines()[0].strip() == RAW_MARKER if text.strip() else False


def network_flags(text: str) -> dict[str, bool]:
    """Compose network key -> internal. An external network is internal only when the
    file records `docker network create --internal <name>`, or the main compose
    declares that corridor with `internal: true`."""
    compose = yaml.safe_load(text) or {}
    created_internal = set(re.findall(r"docker network create --internal (\S+)", text))
    main = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    created_internal |= {(spec or {}).get("name", key) for key, spec in (main.get("networks") or {}).items()
                         if (spec or {}).get("internal") is True}
    flags = {}
    for key, spec in (compose.get("networks") or {}).items():
        spec = spec or {}
        if spec.get("external"):
            flags[key] = spec.get("name", key) in created_internal
        else:
            flags[key] = spec.get("internal") is True
    return flags


def service_networks(service: dict) -> list[str]:
    networks = service.get("networks")
    if networks is None:
        return ["default"]
    return list(networks) if isinstance(networks, (list, dict)) else []


def leaks(text: str, raw: bool | None = None) -> list[str]:
    """Problems Coolify would deploy. raw=None reads the file's own marker."""
    raw = is_raw(text) if raw is None else raw
    compose = yaml.safe_load(text) or {}
    flags = network_flags(text)
    found = []
    for name, service in (compose.get("services") or {}).items():
        service = service or {}
        declared = service_networks(service)
        internal = [net for net in declared if flags.get(net, False)]
        if internal and service.get("ports"):
            found.append(f"{name} declares ports: on internal network {internal[0]}")
        if "network_mode" in service:
            continue
        deployed = declared if raw else declared + [COOLIFY_APP_NETWORK]
        sealed = bool(declared) and all(flags.get(net, False) for net in declared)
        if sealed:
            for net in deployed:
                if not flags.get(net, False):
                    found.append(f"{name} would join non-internal {net}")
    return found


@pytest.mark.parametrize("path", ROOM_FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_no_room_service_would_leak_when_coolify_deploys_it(path: Path) -> None:
    assert leaks(path.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize("room", ["base", "radix", "tiger", "rig"])
def test_sealed_rooms_are_marked_raw_compose(room: str) -> None:
    text = (ROOT / "agents" / room / "docker-compose.yml").read_text(encoding="utf-8")
    assert is_raw(text), f"agents/{room}/docker-compose.yml must start with {RAW_MARKER!r}"


@pytest.mark.parametrize("room, sealed", [
    ("base", {"base-sandbox", "base-browser"}),
    ("tiger", {"tiger-browser"}),
    ("rig", {"rig-sandbox", "rig-browser", "rig-forge"}),
    # Radix is sealed on the live host today; this keeps it so.
    ("radix", {"agent-radix"}),
])
def test_normal_mode_would_put_sealed_services_on_coolifys_network(room: str, sealed: set[str]) -> None:
    text = (ROOT / "agents" / room / "docker-compose.yml").read_text(encoding="utf-8")
    without_marker = "\n".join(line for line in text.splitlines() if line.strip() != RAW_MARKER)
    found = leaks(without_marker)
    assert {item.split()[0] for item in found} == sealed
    assert all(item.endswith(COOLIFY_APP_NETWORK) for item in found)
    assert leaks(text) == []


def test_ports_on_an_internal_network_always_fail() -> None:
    text = RAW_MARKER + """
services:
  sealed:
    image: example
    networks: [inside]
    ports: ["8000:8000"]
networks:
  inside:
    internal: true
"""
    assert leaks(text) == ["sealed declares ports: on internal network inside"]


def test_unmarked_file_with_a_sealed_service_fails() -> None:
    text = """services:
  sealed:
    image: example
    networks: [inside]
  open:
    image: example
networks:
  inside:
    internal: true
"""
    assert leaks(text) == [f"sealed would join non-internal {COOLIFY_APP_NETWORK}"]
    assert leaks(RAW_MARKER + "\n" + text) == []


@pytest.mark.parametrize("path", [p for p in ROOM_FILES if is_raw(p.read_text(encoding="utf-8"))],
                         ids=lambda p: str(p.relative_to(ROOT)))
def test_raw_compose_files_need_nothing_from_coolify(path: Path) -> None:
    compose = yaml.safe_load(path.read_text(encoding="utf-8"))
    for name, service in compose["services"].items():
        # Raw mode has no env_file and adds no network: everything is spelled out.
        assert "env_file" not in service, name
        assert service.get("networks"), f"{name} must name its networks"
        assert "ports" not in service, name
        for key, value in (service.get("environment") or {}).items():
            assert isinstance(value, (str, int, float)), f"{name}.{key} must be explicit"
    for key, spec in (compose.get("volumes") or {}).items():
        # The live name, so the data survives the switch from normal mode.
        assert spec and spec.get("name"), f"volume {key} must keep its live name"


def test_base_volumes_keep_their_live_names() -> None:
    compose = yaml.safe_load((ROOT / "agents/base/docker-compose.yml").read_text(encoding="utf-8"))
    uuid = "r8aprclj8nooe9keywrp9dmb"
    assert {k: v["name"] for k, v in compose["volumes"].items()} == {
        "agent_base_data": f"{uuid}_agent-base-data",
        "base_brain_data": f"{uuid}_base-brain-data",
        "base_browser_data": f"{uuid}_base-browser-data",
    }
    radix = yaml.safe_load((ROOT / "agents/radix/docker-compose.yml").read_text(encoding="utf-8"))
    assert radix["volumes"]["agent_radix_data"]["name"] == "liv4x7vshraiwnnowjv0kgfd_agent-radix-data"


@pytest.mark.parametrize("room", ["base", "tiger", "rig"])
def test_browser_holds_no_tank_key_and_only_the_gateway_talks_to_tank(room: str) -> None:
    compose = yaml.safe_load((ROOT / f"agents/{room}/docker-compose.yml").read_text(encoding="utf-8"))
    services = compose["services"]
    browser_env = services[f"{room}-browser"].get("environment") or {}
    assert "TANK_KEY" not in browser_env and "TANK_REGION" not in browser_env
    assert not any("TANK" in str(value) for value in browser_env.values())
    assert services[f"{room}-browser-gateway"]["environment"]["TANK_KEY"] == "${TANK_KEY_" + room.upper() + ":-}"
    gateway = (ROOT / "agents/_brain/browser_gateway.py").read_text(encoding="utf-8")
    forwarded = gateway[gateway.index('response = await client.post'):]
    forwarded = forwarded[:forwarded.index("})")]
    assert "X-Tank-Key" not in forwarded
    dockerfile = (ROOT / "agents/base/Dockerfile.browser").read_text(encoding="utf-8")
    assert "--no-proxy-headers" in dockerfile


@pytest.mark.asyncio
async def test_browser_accepts_work_only_from_its_gateway(monkeypatch: pytest.MonkeyPatch) -> None:
    from test_agent1_isolation import browser

    async def addresses() -> set[str]:
        return {"10.0.27.3"}

    monkeypatch.setattr(browser, "gateway_addresses", addresses)
    monkeypatch.delenv("TANK_KEY", raising=False)
    for peer, status in (("127.0.0.1", 401), ("10.0.27.9", 401), ("10.0.27.3", 404)):
        transport = httpx.ASGITransport(app=browser.app, client=(peer, 40000))
        async with httpx.AsyncClient(transport=transport, base_url="http://base-browser:3000") as client:
            # /missing passes the gateway check and then 404s; it never opens a browser.
            assert (await client.post("/missing", json={})).status_code == status, peer
            # From the gateway, /render reaches the handler, which refuses a task with no
            # home region (403) before it would launch Chromium. Anywhere else gets 401.
            render = await client.post("/render", json={"url": "https://example.com"})
            assert render.status_code == (401 if status == 401 else 403), peer
            assert (await client.get("/health")).status_code == 200

    async def unknown() -> set[str]:
        raise OSError("no such host")

    monkeypatch.setattr(browser, "gateway_addresses", unknown)
    transport = httpx.ASGITransport(app=browser.app, client=("10.0.27.3", 40000))
    async with httpx.AsyncClient(transport=transport, base_url="http://base-browser:3000") as client:
        assert (await client.post("/missing", json={})).status_code == 503


def run_seal_check(tmp_path: Path, fixture: str) -> subprocess.CompletedProcess:
    fake = tmp_path / "docker"
    fake.write_text(f"#!{sys.executable}\n" + FAKE_DOCKER, encoding="utf-8")
    fake.chmod(0o755)
    env = dict(os.environ, DOCKER=str(fake), SEAL_FIXTURE=str(FIXTURES / fixture))
    return subprocess.run(["bash", str(SEAL_CHECK)], capture_output=True, text=True, env=env, timeout=30)


# Answers only the three read-only calls seal-check.sh makes, from a JSON fixture.
FAKE_DOCKER = r'''
import json, os, sys
data = json.load(open(os.environ["SEAL_FIXTURE"]))
args = sys.argv[1:]
if args[:2] == ["ps", "-q"]:
    print("\n".join(data["containers"]))
elif args[:1] == ["inspect"]:
    c = data["containers"][args[-1]]
    # Raw Compose mode sets no coolify.resourceName, so a fixture may leave it empty.
    print("|".join([c["uuid"], c.get("resource", ""), c["service"], c.get("project", c["uuid"]), "/" + c["name"],
                    "".join(n + " " for n in sorted(c["networks"]))]))
elif args[:2] == ["network", "inspect"]:
    print("true" if data["networks"][args[-1]] else "false")
else:
    sys.exit("fake docker: refused " + " ".join(args))
'''


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
def test_seal_check_reports_sealed_rooms(tmp_path: Path) -> None:
    result = run_seal_check(tmp_path, "sealed.json")
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.splitlines() == [
        "tervory-tankmain (tankuuid): not a room, skipped",
        "agent-base (baseuuid): sealed",
        "agent-radix (radixuuid): sealed",
        "agent-tiger (tigeruuid): sealed",
        "agent-rig (riguuid): sealed",
        AUTUMBRA_ABSENT_LINE,
    ]


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
def test_seal_check_names_each_leaking_container_and_network(tmp_path: Path) -> None:
    result = run_seal_check(tmp_path, "leaking.json")
    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stdout.splitlines() == [
        "agent-base (baseuuid): LEAK: base-sandbox-baseuuid on baseuuid; LEAK: base-browser-baseuuid on baseuuid;"
        " LEAK: base-brain-baseuuid on baseuuid",
        "agent-radix (radixuuid): LEAK: agent-radix-radixuuid on radixuuid",
        "agent-rig (riguuid): sealed",
        "agent-tiger: NOT FOUND",
        AUTUMBRA_ABSENT_LINE,
    ]


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
def test_seal_check_refuses_to_pass_when_it_sees_nothing(tmp_path: Path) -> None:
    result = run_seal_check(tmp_path, "empty.json")
    assert result.returncode == 2
    assert "nothing was checked" in result.stderr


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
def test_seal_check_finds_raw_compose_rooms_by_label_not_container_name(tmp_path: Path) -> None:
    # Live Boston after Raw Compose: Base and Radix containers are <uuid>-<service>-1
    # with no coolify.resourceName; Tank and Tiger keep normal-mode names.
    result = run_seal_check(tmp_path, "raw_sealed.json")
    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stdout.splitlines() == [
        "tervory-tankmain-tankuuid (tankuuid): not a room, skipped",
        "agent-base (baseuuid): sealed",
        "agent-radix (radixuuid): sealed",
        "agent-tiger (tigeruuid): NOT SEALED: no container on an internal network",
        "agent-rig (riguuid): sealed",
        AUTUMBRA_ABSENT_LINE,
    ]


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
@pytest.mark.parametrize("leaking_service", [None, "tiger-browser", "tiger-browser-gateway", "agent-tiger"])
def test_seal_check_raw_tiger_allows_only_its_gateway_corridor(tmp_path: Path, leaking_service: str | None) -> None:
    data = json.loads((FIXTURES / "raw_tiger_sealed.json").read_text())
    if leaking_service:
        for container in data["containers"].values():
            if container["service"] == leaking_service:
                container["networks"].append("tigeruuid_browser" if leaking_service == "agent-tiger" else "tigeruuid")
    fixture = tmp_path / "tiger.json"
    fixture.write_text(json.dumps(data))
    result = run_seal_check(tmp_path, str(fixture))
    assert result.returncode == (1 if leaking_service else 0), result.stdout + result.stderr
    if leaking_service:
        network = "tervory-gw-tiger" if leaking_service == "agent-tiger" else "tigeruuid"
        assert f"agent-tiger (tigeruuid): LEAK: tigeruuid-{leaking_service}-1 on {network}" in result.stdout
    else:
        assert "agent-tiger (tigeruuid): sealed" in result.stdout
        assert "LEAK" not in result.stdout and "NOT FOUND" not in result.stdout


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
def test_seal_check_reports_leaks_in_raw_compose_rooms(tmp_path: Path) -> None:
    result = run_seal_check(tmp_path, "raw_leaking.json")
    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stdout.splitlines() == [
        "tervory-tankmain-tankuuid (tankuuid): not a room, skipped",
        "agent-base (baseuuid): LEAK: baseuuid-base-sandbox-1 on baseuuid",
        "agent-radix (radixuuid): sealed",
        "agent-rig (riguuid): sealed",
        "agent-tiger: NOT FOUND",
        AUTUMBRA_ABSENT_LINE,
    ]


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
def test_seal_check_fails_when_an_expected_room_is_missing(tmp_path: Path) -> None:
    result = run_seal_check(tmp_path, "missing_radix.json")
    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stdout.splitlines() == [
        "tervory-tankmain-tankuuid (tankuuid): not a room, skipped",
        "agent-base (baseuuid): sealed",
        "agent-tiger (tigeruuid): NOT SEALED: no container on an internal network",
        "agent-rig (riguuid): sealed",
        "agent-radix: NOT FOUND",
        AUTUMBRA_ABSENT_LINE,
    ]


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
def test_seal_check_never_passes_when_only_the_hub_is_running(tmp_path: Path) -> None:
    result = run_seal_check(tmp_path, "no_rooms.json")
    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stdout.splitlines() == [
        "tervory-tankmain-tankuuid (tankuuid): not a room, skipped",
        "agent-base: NOT FOUND",
        "agent-radix: NOT FOUND",
        "agent-tiger: NOT FOUND",
        "agent-rig: NOT FOUND",
        AUTUMBRA_ABSENT_LINE,
    ]


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
def test_seal_check_fails_an_expected_room_with_nothing_sealed(tmp_path: Path) -> None:
    result = run_seal_check(tmp_path, "base_not_sealed.json")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "agent-base (baseuuid): NOT SEALED: no container on an internal network" in result.stdout.splitlines()
    assert "agent-radix (radixuuid): sealed" in result.stdout.splitlines()


def test_seal_check_does_not_parse_container_names() -> None:
    script = SEAL_CHECK.read_text(encoding="utf-8").split("set -uo pipefail", 1)[1]
    # Room identity comes from labels; the container name is only printed in a LEAK line.
    assert not re.search(r'\$\{name[#%/]', script.replace("${name#/}", ""))
    assert "coolify.applicationUuid" in script and "com.docker.compose.service" in script


def test_seal_check_is_read_only() -> None:
    script = SEAL_CHECK.read_text(encoding="utf-8")
    calls = re.findall(r'"\$DOCKER" (\w+(?: \w+)?)', script)
    assert set(calls) == {"ps", "inspect", "network inspect"}
    for word in ("disconnect", "connect ", " rm ", " stop", " kill", " run ", " exec ", "create", "prune"):
        assert word not in script.split("set -uo pipefail", 1)[1], word


@pytest.mark.parametrize("service", ["agent-rig", "rig-brain", "rig-browser", "rig-browser-gateway", "rig-sandbox", "rig-forge", "rig-forge-egress"])
def test_rig_extra_network_is_a_leak_even_on_public_api(tmp_path, service):
    data = json.loads((FIXTURES / "sealed.json").read_text())
    data["networks"]["unexpected"] = False
    for container in data["containers"].values():
        if container["service"] == service:
            container["networks"].append("unexpected")
    path = tmp_path / "rig-extra.json"
    path.write_text(json.dumps(data))
    result = run_seal_check(tmp_path, str(path))
    assert result.returncode == 1
    assert f"LEAK: riguuid-{service}-1 on unexpected" in result.stdout


@pytest.mark.parametrize("service", ["rig-browser", "rig-sandbox", "rig-brain", "rig-browser-gateway", "rig-forge", "rig-forge-egress"])
def test_rig_proxy_network_is_for_the_public_api_only(tmp_path, service):
    data = json.loads((FIXTURES / "sealed.json").read_text())
    for container in data["containers"].values():
        if container["service"] == service:
            container["networks"].append("59f8cnpelzwsyte1atyjc4fv")
    path = tmp_path / "rig-private-proxy.json"
    path.write_text(json.dumps(data))
    result = run_seal_check(tmp_path, str(path))
    assert result.returncode == 1
    assert f"LEAK: riguuid-{service}-1 on 59f8cnpelzwsyte1atyjc4fv" in result.stdout


@pytest.mark.parametrize("service", ["rig-browser", "rig-sandbox", "rig-brain", "rig-browser-gateway", "rig-forge", "rig-forge-egress"])
def test_rig_missing_internal_attachment_fails(tmp_path, service):
    data = json.loads((FIXTURES / "sealed.json").read_text())
    for container in data["containers"].values():
        if container["service"] == service:
            container["networks"] = [n for n in container["networks"] if not data["networks"][n]]
    path = tmp_path / "rig-missing.json"
    path.write_text(json.dumps(data))
    result = run_seal_check(tmp_path, str(path))
    assert result.returncode == 1 and f"NOT SEALED: riguuid-{service}-1 missing" in result.stdout


@pytest.mark.parametrize("service", ["rig-browser", "rig-sandbox", "rig-brain", "rig-browser-gateway", "rig-forge", "rig-forge-egress"])
def test_rig_missing_service_cannot_claim_sealed(tmp_path, service):
    data = json.loads((FIXTURES / "sealed.json").read_text())
    data["containers"] = {k: v for k, v in data["containers"].items() if v["service"] != service}
    path = tmp_path / "rig-missing-service.json"
    path.write_text(json.dumps(data))
    result = run_seal_check(tmp_path, str(path))
    assert result.returncode == 1 and f"NOT FOUND: {service}" in result.stdout
    assert "agent-rig (riguuid): sealed" not in result.stdout
