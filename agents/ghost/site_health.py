"""One-way signed health files. The observer accepts no Enforce input."""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import time
from pathlib import Path

import httpx

HEALTH_URLS = {"tervory.com": "https://tervory.com/"}
HEALTH_DIR = Path("/health")
OUTPUT_DIR = Path("/data")
SECRET_ENV = "AUTUMBRA_HEALTH_SECRET"


def canonical(result: dict) -> bytes:
    return json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def observer_site() -> str | None:
    site = os.environ.get("SITE_NAME", "").strip()
    return site if site in HEALTH_URLS else None


def health_configured(site: str | None = None) -> bool:
    configured_site = observer_site()
    return (bool(os.environ.get(SECRET_ENV, "").strip()) and HEALTH_DIR.is_dir()
            and configured_site is not None and (site is None or site == configured_site))


def read_health(site: str) -> bool:
    """Accept only a fresh, authenticated success for the fixed URL."""
    try:
        secret = os.environ.get(SECRET_ENV, "")
        if not secret or site not in HEALTH_URLS:
            return False
        path = HEALTH_DIR / (site + ".json")
        if path.stat().st_size > 4096:
            return False
        envelope = json.loads(path.read_text())
        result = envelope["result"]
        expected = hmac.new(secret.encode(), canonical(result), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, envelope["signature"]):
            return False
        age = time.time() - result["checked_at"]
        return (set(result) == {"site", "url", "ok", "status", "ms", "checked_at"}
                and result["site"] == site and result["url"] == HEALTH_URLS[site]
                and result["ok"] is True and type(result["status"]) is int
                and 200 <= result["status"] < 400
                and math.isfinite(result["ms"]) and result["ms"] >= 0
                and 0 <= age <= 30)
    except (OSError, ValueError, KeyError, TypeError, OverflowError):
        return False


def observe_once(client: httpx.Client, site: str) -> dict:
    url = HEALTH_URLS[site]
    started = time.monotonic()
    status = None
    try:
        # Streaming discards the body; redirects and cookie persistence are disabled.
        client.cookies.clear()
        with client.stream("GET", url) as response:
            status = response.status_code
    except httpx.HTTPError:
        pass
    finally:
        client.cookies.clear()
    return {"site": site, "url": url, "ok": status is not None and 200 <= status < 400,
            "status": status, "ms": round((time.monotonic() - started) * 1000, 3),
            "checked_at": time.time()}


def main() -> None:
    secret = os.environ.get(SECRET_ENV, "")
    site = observer_site()
    if not secret.strip() or site is None:
        print("Health observer is not configured.", flush=True)
        while True:
            time.sleep(15)
    output_dir = OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    transport = httpx.HTTPTransport(proxy="http://health-egress-proxy:8080")
    with httpx.Client(transport=transport, trust_env=False, timeout=5,
                      follow_redirects=False) as client:
        while True:
            result = observe_once(client, site)
            signature = hmac.new(secret.encode(), canonical(result), hashlib.sha256).hexdigest()
            path = output_dir / (site + ".json")
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps({"result": result, "signature": signature}))
            temporary.replace(path)
            time.sleep(15)


if __name__ == "__main__":
    main()
