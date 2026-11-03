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
import urllib.request

ROOT = Path("/source") if len(sys.argv) > 1 and sys.argv[1] == "inside" else Path(__file__).resolve().parents[2]


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
            for port in (3000, 443, 5432, 6379, 6333, 8000):
                assert not reachable(host, port), f"unexpected reachability: {host}:{port}"
        print("denied", *sys.argv[3:])
        return
    if mode == "gold":
        rows = []
        cases = sorted(Path("/source/tests/tiger_price_read/gold/shots").glob("*.png"))
        assert cases
        for png in cases:
            payload = {"png_base64": base64.b64encode(png.read_bytes()).decode()}
            texts = []
            for service in ("baseline", "tiger-ocr"):
                request = urllib.request.Request("http://" + service + ":3000/ocr", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(request, timeout=120) as response:
                    texts.append(json.load(response)["text"])
            rows.append([png.stem, *texts])
        print(json.dumps(rows))



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
            rows = json.loads(call(*cmd, "exec", "-T", "tank", "python", "/source/tests/seal_hardening/compose_probe.py", "inside", "gold"))
            spec = importlib.util.spec_from_file_location("price_ocr", ROOT / "tank/skills/tiger.price_ocr/1.0.1/run.py")
            skill = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(skill)
            count = 0
            for name, before, after in rows:
                url = "https://example.test/" + name
                old_items = skill.prices_from_text(before, url)
                new_items = skill.prices_from_text(after, url)
                assert old_items == new_items, name
                count += bool(new_items)
            assert count > 0, "PNG parity must include actual extracted prices"
            print(f"Tank /ocr: {len(rows)} existing PNG cases produce identical items ({count} with prices)", flush=True)
            peak = call(*cmd, "exec", "-T", "tiger-ocr", "python", "-c", "from pathlib import Path; print(Path('/sys/fs/cgroup/memory.peak').read_text().strip())")
            print(f"tiger-ocr memory.peak={peak} bytes; mem_limit=1g; shm_size=256m", flush=True)
        except BaseException:
            subprocess.run([*cmd, "logs", "--no-color", "--tail", "80", "tiger-ocr", "baseline"], check=False)
            raise
        finally:
            subprocess.run([*cmd, "down", "--volumes", "--remove-orphans"], check=True)


if __name__ == "__main__":
    if sys.argv[1] == "inside":
        inside()
    else:
        run()
