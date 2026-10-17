"""SearXNG leaves through a Tor client on the stack network.

No database and no network. Proves the proxy is socks5h to the Tor
container, Tor is not published on the host, and Brave is still unset.
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_searxng_sends_engine_traffic_through_tor() -> None:
    settings = yaml.safe_load((ROOT / "searxng" / "settings.yml").read_text(encoding="utf-8"))
    outgoing = settings["outgoing"]
    assert outgoing["using_tor_proxy"] is True
    assert outgoing["proxies"] == {"all://": ["socks5h://tor:9050"]}
    assert outgoing["request_timeout"] > 6
    assert outgoing["max_request_timeout"] > 12
    assert outgoing["extra_proxy_timeout"] >= 10
    assert "127.0.0.1" not in outgoing["proxies"]["all://"][0]


def test_tor_is_an_internal_client_and_searxng_waits_for_it() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    services = compose["services"]
    tor = services["tor"]
    assert tor["build"] == "./tor"
    assert tor["networks"] == ["default"]
    assert "ports" not in tor
    assert "healthcheck" in tor
    command = " ".join(tor["healthcheck"]["test"])
    assert "check.torproject.org/api/ip" in command
    assert "IsTor" in command
    searxng = services["searxng"]
    assert searxng["depends_on"]["tor"]["condition"] == "service_healthy"
    assert "tervory-gw-base" in searxng["networks"]
    assert "tervory-gw-" not in " ".join(tor["networks"])
    assert services["tank"]["environment"]["BRAVE_API_KEY"] == "${BRAVE_API_KEY:-}"
    for banned in ("tinyproxy", "squid", "privoxy", "3proxy", "dante"):
        assert banned not in services
    south_africa = yaml.safe_load((ROOT / "docker-compose.za.yml").read_text(encoding="utf-8"))
    assert "tor" not in south_africa["services"]
    assert "searxng" not in south_africa["services"]


def test_tor_config_is_a_client_with_a_private_socks_policy() -> None:
    torrc = (ROOT / "tor" / "torrc").read_text(encoding="utf-8")
    dockerfile = (ROOT / "tor" / "Dockerfile").read_text(encoding="utf-8")
    settings = [line.split("#", 1)[0].strip() for line in torrc.splitlines()]
    settings = [line for line in settings if line]
    assert "SocksPort 0.0.0.0:9050" in settings
    assert "ClientOnly 1" in settings
    assert "SocksPolicy reject *" in settings
    assert not any(line.startswith("ORPort") or line.startswith("ExitRelay") for line in settings)
    assert "USER tor" in dockerfile
    assert "EXPOSE 9050" in dockerfile
