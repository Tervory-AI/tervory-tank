"""Rig offline box: whole shopper journey with the network off."""
from __future__ import annotations

import socket
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "rig"))

from rig_offline_box_fixture import OfflineBox, demo_catalogue


@pytest.fixture
def no_network():
    resolve, connect, connect_ex = socket.getaddrinfo, socket.socket.connect, socket.socket.connect_ex

    def check(host):
        if host not in {"localhost", "127.0.0.1", "::1", b"localhost", b"127.0.0.1", b"::1"}:
            raise RuntimeError("offline box refused non-loopback network access")

    def resolve_local(host, *args, **kwargs):
        check(host)
        return resolve(host, *args, **kwargs)

    def connecting(original):
        def local(sock, address):
            if isinstance(address, tuple):
                check(address[0])
            return original(sock, address)
        return local

    with patch.object(socket, "getaddrinfo", resolve_local), patch.object(
        socket.socket, "connect", connecting(connect)
    ), patch.object(socket.socket, "connect_ex", connecting(connect_ex)):
        yield


def test_shopper_journey_passes_with_network_off(no_network):
    box = OfflineBox(demo_catalogue(), online=False)
    result = box.journey(
        query="LumaWorks",
        product_id="STI-P-9",
        question="Does it ship locally?",
        note="hold for pickup",
    )
    assert result["online"] is False
    assert result["search_count"] >= 1
    assert result["product"]["sku"] == "STI-P-9"
    assert result["ask"]["local_rung"] is True
    assert result["ask"]["model"] == "offline-local"
    assert result["ask"]["cost_usd"] == 0.0
    assert result["ask"]["network"] == "off"
    assert result["quote"]["queued"] is True
    assert result["pending_sync"] == 1
    # Network stays off: flush must not call out.
    with pytest.raises(RuntimeError):
        socket.getaddrinfo("example.com", 443)


def test_sync_queue_flushes_when_online(no_network):
    box = OfflineBox(demo_catalogue(), online=False)
    box.quote("STI-P-9", "offline note")
    assert len(box.queue) == 1
    sent = []
    box.online = True
    moved = box.queue.flush(sender=sent.append)
    assert len(moved) == 1 and len(box.queue) == 0 and sent
