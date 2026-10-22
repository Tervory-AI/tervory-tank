"""Forge network policy, parser isolation, and source-address boundaries."""
import json
import struct
from pathlib import Path

import httpx
import pytest
import yaml

from agents.rig.forge import egress, service
from agents.rig.forge.inputs import embedded_mesh

ROOT = Path(__file__).resolve().parents[1]


def test_compose_only_brain_controls_forge_and_only_proxy_has_egress():
    data = yaml.safe_load((ROOT / "agents/rig/docker-compose.yml").read_text())
    services = data["services"]
    assert {name for name,spec in services.items() if "forge-control" in spec["networks"]} == {"rig-forge","rig-brain"}
    assert services["rig-forge"]["networks"] == ["forge-control","forge-egress"]
    assert {name for name,spec in services.items() if "HF_JOBS_TOKEN" in spec.get("environment",{})} == {"rig-forge"}
    for name in ("rig-forge","rig-forge-egress"):
        assert not any("TANK" in k for k in services[name]["environment"])
        assert not services[name].get("ports") and not services[name].get("labels")
    assert data["networks"]["forge-control"]["internal"]
    assert data["networks"]["forge-egress"]["internal"]


def test_exact_hosts_ports_and_public_ip_policy(monkeypatch):
    monkeypatch.setenv("R2_ACCOUNT_ID","a"*32)
    assert egress.target("CONNECT huggingface.co:443 HTTP/1.1") == "huggingface.co"
    assert egress.target("CONNECT "+"a"*32+".r2.cloudflarestorage.com:443 HTTP/1.1").endswith(".r2.cloudflarestorage.com")
    for destination in ("HUGGINGFACE.CO:443", "huggingface.co:80", "huggingface.co.evil:443", "user@huggingface.co:443",
                        "127.0.0.1:443", "other.r2.cloudflarestorage.com:443", "[::1]:443"):
        with pytest.raises(ValueError):egress.target("CONNECT "+destination+" HTTP/1.1")
    for address in ("127.0.0.1","10.0.0.1","169.254.169.254","::1","::ffff:127.0.0.1","224.0.0.1"):
        assert not egress.public(address)


@pytest.mark.asyncio
async def test_forge_trusts_peer_address_not_forwarded_headers(monkeypatch):
    async def addresses():return {"10.0.0.2"}
    monkeypatch.setattr(service,"brain_addresses",addresses)
    for host,status in (("10.0.0.2",200),("10.0.0.9",401)):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=service.app,client=(host,123)),base_url="http://forge") as client:
            assert (await client.get("/health",headers={"X-Forwarded-For":"10.0.0.2"})).status_code == status


def test_external_obj_and_glb_resources_are_rejected(tmp_path):
    obj = tmp_path / "asset.obj"
    obj.write_text("mtllib ../../another-tenant/material.mtl\n")
    with pytest.raises(ValueError,match="external"):
        embedded_mesh(obj)
    document=json.dumps({"asset":{"version":"2.0"},"images":[{"uri":"../../another-tenant/image.png"}]}).encode()
    document+=b" "*((-len(document))%4)
    glb=tmp_path/"asset.glb"
    glb.write_bytes(struct.pack("<5I",0x46546c67,2,20+len(document),len(document),0x4e4f534a)+document)
    with pytest.raises(ValueError,match="external"):
        embedded_mesh(glb)
