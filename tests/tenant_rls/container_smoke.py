"""Build and start four non-root images with no network or provider credentials."""

import json
from pathlib import Path
import subprocess
import tempfile
import time
from uuid import uuid4

import yaml

ROOT = Path(__file__).resolve().parents[2]


def command(*args, capture=False):
    return subprocess.run(args, cwd=ROOT, check=True, text=True,
                          stdout=subprocess.PIPE if capture else None).stdout


def main():
    with tempfile.TemporaryDirectory(prefix="rls-images-") as folder:
        temp = Path(folder)
        config = yaml.safe_load((ROOT / "searxng/settings.yml").read_text())
        # The real image keeps Ferry/Tor. Offline smoke never connects to it.
        config["outgoing"]["using_tor_proxy"] = False
        config["outgoing"]["proxies"] = {}
        (temp / "searxng.yml").write_text(yaml.safe_dump(config))
        (temp / "litellm.yml").write_text("model_list: []\n")
        temp.chmod(0o755)
        for path in temp.iterdir():
            path.chmod(0o644)
        for service, port, path in [("litellm", 4000, "/health/liveliness"),
                                    ("searxng", 8080, "/healthz"),
                                    ("site", 3000, "/"), ("tiger", 3000, "/health")]:
            image = f"tervory-rls-{service}:test"
            command("docker", "build", "--memory=1g", "-t", image, service)
            name = "rls-smoke-" + service + "-" + uuid4().hex[:10]
            options = ["docker", "run", "-d", "--name", name, "--network", "none", "--memory=1g", "--cpus=1"]
            if service == "litellm":
                # Documented upstream LOCAL mode avoids creating/handling a key.
                # Not baked into an image, compose or any production environment.
                options += ["-e", "LITELLM_DANGEROUSLY_PERMIT_WEAK_OR_UNSET_MASTER_KEY=true",
                            "-v", f"{temp / 'litellm.yml'}:/tmp/offline.yml:ro"]
            if service == "searxng":
                options += ["-v", f"{temp / 'searxng.yml'}:/etc/searxng/settings.yml:ro"]
            options += [image]
            if service == "litellm":
                options += ["--config", "/tmp/offline.yml", "--port", "4000"]
            command(*options)
            try:
                url = f"http://127.0.0.1:{port}{path}"
                if service == "site":
                    probe = ["node", "-e", "if(process.getuid()===0)process.exit(1);"
                             "require('fs').accessSync('/data',require('fs').constants.W_OK);"
                             f"fetch({json.dumps(url)}).then(r=>{{if(!r.ok)process.exit(1);"
                             "console.log('uid',process.getuid(),'health',r.status)})"]
                else:
                    python = "/usr/local/searxng/.venv/bin/python" if service == "searxng" else "python"
                    probe = [python, "-c", "import os,urllib.request; assert os.getuid()!=0; "
                             f"print('uid',os.getuid(),'health',urllib.request.urlopen({url!r},timeout=3).status)"]
                for attempt in range(90):
                    result = subprocess.run(["docker", "exec", name, *probe], capture_output=True, text=True)
                    if result.returncode == 0:
                        print(service + ": " + result.stdout.strip(), flush=True)
                        break
                    if attempt == 89:
                        raise RuntimeError(service + " failed its offline non-root health check")
                    time.sleep(0.5)
            finally:
                command("docker", "rm", "-f", "-v", name)


if __name__ == "__main__":
    main()
