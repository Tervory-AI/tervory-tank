"""SearXNG leaves through Ferry on the stack network.

No database and no network. Ferry is the service a person reads.
Ferry leaves through Tor. Brave is still unset.
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_searxng_sends_engine_traffic_through_ferry() -> None:
    settings = yaml.safe_load((ROOT / "searxng" / "settings.yml").read_text(encoding="utf-8"))
    outgoing = settings["outgoing"]
    assert outgoing["using_tor_proxy"] is True
    assert outgoing["proxies"] == {"all://": ["socks5h://Ferry:9050"]}
    assert outgoing["request_timeout"] > 6
    assert outgoing["max_request_timeout"] > 12
    assert outgoing["extra_proxy_timeout"] == 10
    assert isinstance(outgoing["extra_proxy_timeout"], int)
    assert "127.0.0.1" not in outgoing["proxies"]["all://"][0]


def test_ferry_is_an_internal_service_and_searxng_waits_for_it() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    services = compose["services"]
    assert "tor" not in services
    ferry = services["Ferry"]
    assert ferry["image"] == "ferry"
    assert ferry["build"] == "./tor"
    assert ferry["networks"] == ["default"]
    assert "ports" not in ferry
    assert "healthcheck" in ferry
    command = " ".join(ferry["healthcheck"]["test"])
    assert "check.torproject.org/api/ip" in command
    assert "IsTor" in command
    searxng = services["searxng"]
    assert searxng["depends_on"]["Ferry"]["condition"] == "service_healthy"
    assert "tervory-gw-base" in searxng["networks"]
    assert "tervory-gw-" not in " ".join(ferry["networks"])
    assert services["tank"]["environment"]["BRAVE_API_KEY"] == "${BRAVE_API_KEY:-}"
    for banned in ("tinyproxy", "squid", "privoxy", "3proxy", "dante"):
        assert banned not in services
    south_africa = yaml.safe_load((ROOT / "docker-compose.za.yml").read_text(encoding="utf-8"))
    assert "Ferry" not in south_africa["services"]
    assert "tor" not in south_africa["services"]
    assert "searxng" not in south_africa["services"]


def test_ferry_leaves_through_a_tor_client() -> None:
    torrc = (ROOT / "tor" / "torrc").read_text(encoding="utf-8")
    dockerfile = (ROOT / "tor" / "Dockerfile").read_text(encoding="utf-8")
    settings = [line.split("#", 1)[0].strip() for line in torrc.splitlines()]
    settings = [line for line in settings if line]
    assert "SocksPort 0.0.0.0:9050" in settings
    assert "ClientOnly 1" in settings
    assert "SocksPolicy accept6 [::1]/128" in settings
    assert "SocksPolicy reject *" in settings
    assert "SocksPolicy reject6 *" in settings
    assert not any(line.startswith("ORPort") or line.startswith("ExitRelay") for line in settings)
    assert "USER tor" in dockerfile
    assert "EXPOSE 9050" in dockerfile
