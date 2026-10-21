"""Read-only deployment gate for the Base pilot's five-container topology.

Run on the authorized cloud Docker host, never on a laptop:
python agents/base/check_brain_isolation.py ROOM BRAIN SANDBOX BROWSER GATEWAY
"""
import json
import subprocess
import sys


def docker(*args):
    return subprocess.check_output(["docker", *args], text=True)


def main(names):
    if len(names) != 5:
        raise SystemExit("Supply ROOM BRAIN SANDBOX BROWSER GATEWAY container names")
    room, brain, sandbox, browser, gateway = [json.loads(docker("inspect", name))[0] for name in names]
    rows = [room, brain, sandbox, browser, gateway]
    for row in rows:
        assert row["State"].get("Health", {}).get("Status") == "healthy", "service is not healthy"
        assert not row["HostConfig"]["PortBindings"], "room service publishes a host port"
        assert all(m["Type"] == "volume" for m in row["Mounts"]), "unexpected host mount"
        keys = {v.split("=", 1)[0] for v in row["Config"]["Env"]}
        assert not keys & {"OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY", "LITELLM_MASTER_KEY"}, "model key in room"
    memberships = [set(row["NetworkSettings"]["Networks"]) for row in rows]
    assert memberships[0] == {"tervory-gw-base"}, "room corridor mismatch"
    sandbox_net, = memberships[2]
    browser_net, = memberships[3]
    assert sandbox_net != browser_net
    assert memberships[1] == {"tervory-gw-base", sandbox_net}
    assert memberships[4] == {"tervory-gw-base", browser_net}
    for network, members in [(sandbox_net, {brain["Id"], sandbox["Id"]}), (browser_net, {browser["Id"], gateway["Id"]})]:
        info = json.loads(docker("network", "inspect", network))[0]
        assert info["Internal"], "private network has external egress"
        assert set(info["Containers"]) == members, "another service joined Base's private tools"
    own = {row["Id"] for row in rows}
    corridor = json.loads(docker("network", "inspect", "tervory-gw-base"))[0]
    for identity in corridor["Containers"]:
        if identity in own:
            continue
        peer = json.loads(docker("inspect", identity))[0]
        service = peer["Config"].get("Labels", {}).get("com.docker.compose.service")
        assert service in {"tank", "postgres", "hermes", "searxng", "tiger"}, "unexpected corridor neighbour"
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
    docker("exec", names[0], "python", "-c", room_script)
    proof = "import socket; s=socket.socket(); s.settimeout(3); assert s.connect_ex(('1.1.1.1',443)) != 0"
    docker("exec", names[2], "docker", "run", "--rm", "--network", "none", "--read-only", "--cap-drop", "ALL",
           "tervory-base-sandbox:python3.12", "python", "-c", proof)
    docker("exec", names[3], "python", "-c", proof)
    print("PASS Base topology, private tools, volumes, keys, database role and denied direct egress")


if __name__ == "__main__":
    main(sys.argv[1:])
