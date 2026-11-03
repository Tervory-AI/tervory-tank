"""Disposable Compose proof; all runtime networks are internal, no live volumes/settings.

Build the unchanged tiger/Dockerfile first. Runtime tests never use public sites.
"""
import base64
import copy
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]


def call(*args, **kwargs):
    return subprocess.check_output(args, text=True, **kwargs).strip()


def reachable(host, port=3000):
    try:
        with socket.create_connection((host, port), timeout=0.4):
            return True
    except OSError:
        return False


def inside():
    mode = sys.argv[2]
    if mode == "deny":
        for host in sys.argv[3:]:
            assert not reachable(host), f"unexpected reachability: {host}"
        print("denied", *sys.argv[3:])
        return
    if mode == "gold":
        import asyncio
        from types import SimpleNamespace
        import httpx
        spec = importlib.util.spec_from_file_location("price_ocr", "/source/tank/skills/tiger.price_ocr/1.0.1/run.py")
        skill = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(skill)
        async def run():
            cases = sorted(Path("/source/tests/tiger_price_read/gold/shots").glob("*.png"))
            assert cases
            async with httpx.AsyncClient(trust_env=False) as client:
                for png in cases:
                    payload = {"png_base64": base64.b64encode(png.read_bytes()).decode(), "url": "https://example.test/" + png.stem}
                    before = await skill.run(payload, SimpleNamespace(env={"TIGER_URL": "http://baseline:3000"}, http=client))
                    after = await skill.run(payload, SimpleNamespace(env={"TIGER_URL": "http://tiger-ocr:3000"}, http=client))
                    assert before == after, png.name
            print(f"Tank /ocr: {len(cases)} existing PNG cases produce identical items")
        asyncio.run(run())


def run():
    import yaml
    project = f"codex-seal-test-{os.getpid()}"
    image = os.environ.get("SEAL_TEST_IMAGE", "codex-seal-ocr-test:local")
    room = yaml.safe_load((ROOT / "agents/tiger/docker-compose.yml").read_text())
    main = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    assert main["services"]["tank"]["environment"]["TIGER_URL"] == "http://tiger-ocr:3000"
    assert "tiger" not in main["services"]
    ocr = copy.deepcopy(room["services"]["tiger-ocr"])
    ocr.pop("build")
    ocr["image"] = image
    ocr["restart"] = "no"
    ocr["environment"] = {"TIGER_MAX_PAGES": "4"}
    names = {"ocr": "tervory-gw-tiger-ocr", "gw": "tervory-gw-tiger", "browser": "browser", "base": "tervory-gw-base", "other": "other", "baseline": "baseline"}
    networks = {key: {"internal": True} for key in names}
    def probe(nets):
        return {"image": image, "entrypoint": ["python", "-c", "import time; time.sleep(1800)"], "networks": nets,
                "volumes": [str(ROOT) + ":/source:ro"], "cap_drop": ["ALL"], "security_opt": ["no-new-privileges:true"]}
    services = {"tiger-ocr": ocr, "tank": probe(["ocr", "base", "gw", "other", "baseline"]),
                "agent-tiger": probe(room["services"]["agent-tiger"]["networks"]),
                "tiger-browser": probe(room["services"]["tiger-browser"]["networks"]),
                "tiger-browser-gateway": probe(room["services"]["tiger-browser-gateway"]["networks"]),
                "base": probe(["base"]), "other": probe(["other"])}
    baseline = copy.deepcopy(ocr)
    baseline["networks"] = ["baseline"]
    baseline.pop("cap_drop")
    baseline.pop("security_opt")
    services["baseline"] = baseline
    with tempfile.TemporaryDirectory(prefix="seal-compose-") as scratch:
        compose = Path(scratch) / "compose.json"
        compose.write_text(json.dumps({"services": services, "networks": networks}))
        cmd = ["docker", "compose", "-p", project, "-f", str(compose)]
        def execute(service, mode, *targets):
            print(call(*cmd, "exec", "-T", service, "python", "/source/tests/seal_hardening/compose_probe.py", "inside", mode, *targets), flush=True)
        try:
            subprocess.run([*cmd, "up", "-d", "--wait", "--wait-timeout", "120"], check=True)
            ids = {name: call(*cmd, "ps", "-q", name) for name in services}
            ip = json.loads(call("docker", "inspect", "--format", "{{json .NetworkSettings.Networks}}", ids["tiger-ocr"]))
            assert len(ip) == 1
            address = next(iter(ip.values()))["IPAddress"]
            for net in ip:
                assert call("docker", "network", "inspect", "--format", "{{.Internal}}", net) == "true"
            # OCR has no source mount in production; copy this test-only probe into
            # its ephemeral /tmp rather than adding any production attachment.
            subprocess.run(["docker", "cp", str(Path(__file__).resolve()), ids["tiger-ocr"] + ":/tmp/probe.py"], check=True)
            denied = ["tank", "postgres", "redis", "qdrant", "litellm", "agent-tiger", "tiger-browser", "base", "other", "1.1.1.1", "8.8.8.8"]
            print(call(*cmd, "exec", "-T", "tiger-ocr", "python", "/tmp/probe.py", "inside", "deny", *denied[1:]), flush=True)
            # Tank is its one intended neighbour; the OCR endpoint can see Tank's
            # address, but Tank holds no listener in this disposable proof.
            for service in ("agent-tiger", "tiger-browser", "tiger-browser-gateway", "base", "other"):
                execute(service, "deny", "tiger-ocr", address)
            execute("tank", "gold")
            peak = call(*cmd, "exec", "-T", "tiger-ocr", "python", "-c", "from pathlib import Path; print(Path('/sys/fs/cgroup/memory.peak').read_text().strip())")
            print(f"tiger-ocr memory.peak={peak} bytes; mem_limit=1g; shm_size=256m", flush=True)
        finally:
            subprocess.run([*cmd, "down", "--volumes", "--remove-orphans"], check=True)


if __name__ == "__main__":
    if sys.argv[1] == "inside":
        inside()
    else:
        run()
