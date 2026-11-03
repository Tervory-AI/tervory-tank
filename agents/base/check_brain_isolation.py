"""Read-only deployment gate for the Base pilot's five-container topology.

Run on the authorized cloud Docker host, never on a laptop:
python agents/base/check_brain_isolation.py ROOM BRAIN SANDBOX BROWSER GATEWAY
"""
import json
import subprocess
import sys
import shlex
import re


def docker(*args):
    return subprocess.check_output(["docker", *args], text=True)


def sandbox_probe_script(sandbox_host="base-sandbox"):
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,62}", sandbox_host):
        raise ValueError("Invalid sandbox host")
    scratch = "blocked=False\ntry:\n import socket\n socket.socket()\nexcept (ImportError,OSError): blocked=True\nassert blocked\nfrom pathlib import Path\nPath('proof').write_text('offline')\nprint('OFFLINE')"
    sandbox_check = "import json,os,urllib.request,uuid\ncommand=" + repr("python -c " + shlex.quote(scratch)) + "\n" + """body = json.dumps({'tenant_id':str(uuid.uuid4()),'task_id':str(uuid.uuid4()),'command':command}).encode()
request = urllib.request.Request(SANDBOX_URL,data=body,headers={'Content-Type':'application/json','X-Sandbox-Key':os.environ['SANDBOX_KEY']})
result = json.load(urllib.request.urlopen(request,timeout=35))
assert result['exit_code']==0 and 'OFFLINE' in result['output'], result
"""
    return sandbox_check.replace("SANDBOX_URL", repr("http://" + sandbox_host + ":8002/exec"))


def main(names):
    if len(names) != 5:
        raise SystemExit("Supply ROOM BRAIN SANDBOX BROWSER GATEWAY container names")
    room, brain, sandbox, browser, gateway = [json.loads(docker("inspect", name))[0] for name in names]
    rows = [room, brain, sandbox, browser, gateway]
    for row in rows:
        assert row["State"].get("Health", {}).get("Status") == "healthy", "service is not healthy"
        config = row["HostConfig"]
        assert not config.get("Privileged"), "privileged room service"
        assert not config.get("CapAdd"), "room service adds capabilities"
        assert config.get("NetworkMode") != "host" and not str(config.get("NetworkMode", "")).startswith("container:"), "shared host/container network"
        assert config.get("PidMode", "") in {"", "private"}, "shared PID namespace"
        assert not row["HostConfig"]["PortBindings"], "room service publishes a host port"
        assert all(m["Type"] == "volume" or (m["Type"] == "tmpfs" and m["Destination"] in {"/tmp", "/work"}) for m in row["Mounts"]), "unexpected host mount"
        keys = {v.split("=", 1)[0] for v in row["Config"]["Env"]}
        assert not keys & {"OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY", "LITELLM_MASTER_KEY"}, "model key in room"
    service = room["Config"].get("Labels", {}).get("com.docker.compose.service")
    room_name = {"agent-base": "base", "agent-tiger": "tiger"}.get(service)
    assert room_name is not None, "unsupported room"
    corridor_name = "tervory-gw-" + room_name
    sandbox_host = sandbox["Config"].get("Labels", {}).get("com.docker.compose.service")
    assert sandbox_host == room_name + "-sandbox", "sandbox belongs to another room"
    sandbox_keys = {value.split("=", 1)[0] for value in sandbox["Config"]["Env"]}
    assert "TANK_KEY" not in sandbox_keys, "Tank key in sandbox"
    assert sandbox["HostConfig"].get("ReadonlyRootfs"), "sandbox root must be read-only"
    assert "ALL" in sandbox["HostConfig"].get("CapDrop", []), "sandbox must drop all capabilities"
    assert any("no-new-privileges" in option for option in sandbox["HostConfig"].get("SecurityOpt", [])), "sandbox can gain privileges"
    assert not any(m["Type"] == "volume" for m in sandbox["Mounts"]), "sandbox must not mount room/session data"
    assert "/work" in sandbox["HostConfig"].get("Tmpfs", {}), "sandbox lacks isolated tmpfs work"
    memberships = [set(row["NetworkSettings"]["Networks"]) for row in rows]
    assert memberships[0] == {corridor_name}, "room corridor mismatch"
    sandbox_net, = memberships[2]
    browser_net, = memberships[3]
    assert sandbox_net != browser_net
    assert memberships[1] == {corridor_name, sandbox_net}
    assert memberships[4] == {corridor_name, browser_net}
    for network, members in [(sandbox_net, {brain["Id"], sandbox["Id"]}), (browser_net, {browser["Id"], gateway["Id"]})]:
        info = json.loads(docker("network", "inspect", network))[0]
        assert info["Internal"], "private network has external egress"
        assert set(info["Containers"]) == members, "another service joined Base's private tools"
    own = {row["Id"] for row in rows}
    corridor = json.loads(docker("network", "inspect", corridor_name))[0]
    for identity in corridor["Containers"]:
        if identity in own:
            continue
        peer = json.loads(docker("inspect", identity))[0]
        service = peer["Config"].get("Labels", {}).get("com.docker.compose.service")
        assert service in {"tank", "postgres", "hermes", "searxng"}, "unexpected corridor neighbour"
    room_script = '''import asyncio, os, asyncpg
async def run():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'])
    assert await conn.fetchval('SELECT current_user') == 'agent_base'
    assert not await conn.fetchval('SELECT rolsuper FROM pg_roles WHERE rolname=current_user')
    for sql in ['SELECT 1 FROM tank.ledger LIMIT 1', 'SELECT 1 FROM base.records LIMIT 1']:
        try:
            await conn.execute(sql)
        except asyncpg.InsufficientPrivilegeError:
            pass
        else:
            raise AssertionError('Base can read another schema')
    await conn.close()
asyncio.run(run())
'''
    room_script = room_script.replace("'agent_base'", repr("agent_" + room_name)).replace("Base can read", room_name.title() + " can read")
    docker("exec", names[0], "python", "-c", room_script)
    proof = "import socket; s=socket.socket(); s.settimeout(3); assert s.connect_ex(('1.1.1.1',443)) != 0"
    sandbox_check = sandbox_probe_script(sandbox_host)
    docker("exec", names[1], "python", "-c", sandbox_check)
    gateway_address = gateway["NetworkSettings"]["Networks"][corridor_name]["IPAddress"]
    docker("exec", names[1], "python", "-c", "import socket; s=socket.socket(); s.settimeout(3); assert s.connect_ex(('" + gateway_address + "',3128)) != 0")
    docker("exec", names[2], "python", "-c", proof)
    docker("exec", names[3], "python", "-c", proof)
    print("PASS " + room_name.title() + " topology, private tools, volumes, keys, database role and denied direct egress")


if __name__ == "__main__":
    main(sys.argv[1:])
