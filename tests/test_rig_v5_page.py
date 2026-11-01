"""Rig v5 shopper page (approved Figma, two skins) and the engine pieces it reads.

No database, no network. The mailer is a fake and SMTP is guarded.
"""

from __future__ import annotations

async def load_catalogue(service, folder):
    from rig_fixture_loader import load_catalogue as load
    return await load(service, folder)


import csv
import json
import re
import smtplib
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "rig"))
sys.path.insert(0, str(ROOT / "agents" / "_chassis"))

from rigbox.api import mount  # noqa: E402
from rigbox.page_route import mount_page  # noqa: E402
from rigbox.service import Service, WebhookHandoff  # noqa: E402
from rigbox.store import MemoryStore  # noqa: E402

ARCHON = ROOT / "tests" / "fixtures" / "rig_catalogues" / "archon"
V5 = ROOT / "agents" / "rig" / "rigbox" / "page" / "v5"
TENANT = "44444444-4444-4444-8444-444444444444"
ORIGIN = "https://rig.tervory.com"
KEY = "rk_pub_archon"
HEAD = {"X-Rig-Key": KEY, "Origin": ORIGIN}


class Mail:
    def __init__(self) -> None:
        self.letters: list[dict[str, str]] = []

    async def send(self, letter: dict[str, str]) -> None:
        self.letters.append(letter)


def _client(mail: Mail | None = None) -> TestClient:
    import asyncio

    service = Service(MemoryStore(), handoff=WebhookHandoff(None, mail))
    report = asyncio.run(load_catalogue(service, ARCHON))
    assert report["products"]["added"] == 15
    assert report["market"] == {"rows": report["market"]["rows"], "rejected": []}
    app = FastAPI()
    app.state.rig = service
    mount(app)
    mount_page(app)
    return TestClient(app)


def _guard_smtp(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_args, **_kwargs):
        raise AssertionError("a test tried to open SMTP")

    monkeypatch.setattr(smtplib, "SMTP", refuse)
    monkeypatch.setattr(smtplib, "SMTP_SSL", refuse)


def test_v5_page_serves_both_skins_without_a_fixture_key() -> None:
    client = _client()
    rig = client.get("/v5")
    assert rig.status_code == 200
    assert 'data-skin="rig"' in rig.text
    assert json.dumps(KEY) not in rig.text
    assert "__RIG_" not in rig.text
    cn = client.get("/v5/cn")
    assert 'data-skin="cn"' in cn.text
    assert 'data-skin="cn"' in client.get("/v5?skin=cn").text
    # An unknown skin falls back to the Tervory default. Nothing from the query is echoed.
    odd = client.get('/v5?skin="><script>')
    assert 'data-skin="rig"' in odd.text
    assert "<script>alert" not in odd.text


def test_root_serves_v5_product_surface() -> None:
    """GET / is the built Rig product (v5), not the classic blank shell."""
    client = _client()
    home = client.get("/")
    assert home.status_code == 200
    assert 'data-skin="rig"' in home.text
    assert "What are you building?" in home.text
    assert "Archon Type B" not in home.text
    assert "Demo · fixture catalogues" not in home.text
    assert "live distributor keys are off" not in home.text
    assert "Demo · keys off" not in home.text
    assert "demo-banner" not in home.text
    assert "pill-sample" not in home.text
    assert "Archon catalogue" not in home.text
    assert json.dumps(KEY) not in home.text
    assert "__RIG_" not in home.text
    assert client.get("/v5").status_code == 200
    assert 'data-skin="cn"' in client.get("/v5/cn").text


def test_v5_assets_and_traversal() -> None:
    client = _client()
    for name, media in (
        ("rig.css", "text/css"),
        ("rig.js", "text/javascript"),
        ("media/type-b-flr.svg", "image/svg+xml"),
        ("media/blueprint-left.svg", "image/svg+xml"),
    ):
        response = client.get(f"/page/v5/{name}")
        assert response.status_code == 200, name
        assert response.headers["content-type"].startswith(media)
    assert client.get("/page/v5/sample-suppliers.json").status_code == 404
    assert client.get("/page/v5/index.html").status_code == 404
    assert client.get("/page/v5/../page_route.py").status_code == 404
    assert client.get("/page/v5/%2e%2e/cn/cn.js").status_code == 404
    assert client.get("/page/v5/media/nothing.svg").status_code == 404


def test_v5_shopper_words() -> None:
    text = "\n".join((V5 / name).read_text(encoding="utf-8") for name in ("index.html", "rig.js"))
    assert "Get A Quote" in text
    assert not re.search(r"reserv", text, re.IGNORECASE)
    assert "Market prices" in text
    assert "Sample prices" not in text
    assert "Demo · keys off" not in text
    assert "live distributor keys are off" not in text
    assert "sample prices" not in text
    assert "sample" in (V5 / "sample-suppliers.json").read_text(encoding="utf-8")
    # No web images: every image the page loads is under /page/v5/media.
    for url in re.findall(r"(?:src=|url\()[\"']?([^\"')\s>]+)", text):
        if url.startswith(("data:", "${", "/page/v5/media/")) or url == "/page/v5/rig.js":
            continue
        raise AssertionError(f"unexpected image source {url}")
    css = (V5 / "rig.css").read_text(encoding="utf-8")
    for url in re.findall(r"url\(\"?([^\")]+)", css):
        assert url.startswith(("data:", "/page/v5/media/")), url


def test_v5_media_is_wrapped_owner_media() -> None:
    for path in (V5 / "media").glob("*.svg"):
        text = path.read_text(encoding="utf-8")
        assert text.startswith("<svg"), path.name
        assert "data:image/webp;base64," in text, path.name
        assert "http://" not in text.replace("http://www.w3.org", ""), path.name
        assert "https://" not in text, path.name


def test_sample_suppliers_match_the_catalogue() -> None:
    offers = json.loads((V5 / "sample-suppliers.json").read_text(encoding="utf-8"))
    assert offers["sample"] is True
    rows = list(csv.DictReader((ARCHON / "products.csv").open(encoding="utf-8")))
    assert {row["sku"] for row in rows} == set(offers["offers"])
    for row in rows:
        stock = json.loads(row["attributes"])["stock"]["status"]
        listed = offers["offers"][row["sku"]]
        assert [o["supplier"] for o in listed] == ["A", "B", "C"]
        live = [o["price"] for o in listed if o["status"] in ("in_stock", "low_stock")]
        if stock in ("in_stock", "low_stock"):
            # The build price is the catalogue price, so the best in-stock offer must equal it.
            assert min(live) == float(row["price"]), row["sku"]
        else:
            assert live == [], row["sku"]


def test_search_gives_the_pistol_and_approved_fits_for_the_page() -> None:
    client = _client()
    body = client.get("/v1/rig/search", params={"q": "Archon Type B, red dot, flat trigger"}, headers=HEAD).json()
    assert body["honest"] == "exact"
    assert body["focus_id"] == "ARCHON-TYPE-B"
    exact = [row["id"] for row in body["results"] if "Exact match" in row["badges"]]
    assert exact == ["ARCHON-TYPE-B", "ARCHON-DOT-RMR", "ARCHON-TRIGGER-PERF"]
    spread = client.get("/v1/rig/search", params={"q": "Archon Type B", "limit": 24}, headers=HEAD).json()
    fits = sorted(row["id"] for row in spread["results"] if (row.get("fit") or {}).get("fits") is True)
    assert "ARCHON-DOT-ACRO" not in fits and "ARCHON-DOT-RMS" not in fits
    assert {"ARCHON-DOT-RMR", "ARCHON-TRIGGER-PERF", "ARCHON-TB-THREADED", "ARCHON-MAG-15"} <= set(fits)


def test_out_of_catalogue_is_i_dont_know() -> None:
    client = _client()
    body = client.get("/v1/rig/search", params={"q": "Glock 19 compensator"}, headers=HEAD).json()
    assert body["results"] == []
    assert body["honest"] == "not_stocked"


def test_compare_gives_market_spread_only_for_the_picked_items() -> None:
    client = _client()
    body = client.post("/v1/rig/compare", json={"product_ids": ["ARCHON-DOT-RMR"]}, headers=HEAD).json()
    assert body["retailer"] == "Custom Nation"
    [line] = body["lines"]
    market = line["market"]
    assert market["indicative"] is True
    assert market["low"] <= market["amount"] <= market["high"]
    assert market["sources"] >= 3
    sources = {row["source"] for row in csv.DictReader((ARCHON / "market.csv").open(encoding="utf-8"))}
    assert all(source.startswith("Sample retailer") for source in sources)


def test_get_a_quote_for_a_build_goes_to_the_shop(monkeypatch: pytest.MonkeyPatch) -> None:
    _guard_smtp(monkeypatch)
    mail = Mail()
    client = _client(mail)
    setup = {
        "tier": "build",
        "label": "Rig build",
        "parts": [
            {"role": "pistol", "product": {"id": "ARCHON-TYPE-B"}, "choice": ""},
            {"role": "optic", "product": {"id": "ARCHON-DOT-RMR"}, "choice": ""},
            {"role": "trigger", "product": {"id": "ARCHON-TRIGGER-PERF"}, "choice": ""},
        ],
    }
    contact = {"name": "Ada Buyer", "email": "ada@example.com"}
    saved = client.post("/v1/rig/quote", json={"setup": setup, "contact": contact}, headers=HEAD)
    assert saved.status_code == 200, saved.text
    assert saved.json()["delivered"] is True
    [letter] = mail.letters
    assert letter["to"] == "sales@customnation.co.za"
    assert letter["subject"].startswith("Quote request:")
    # An out-of-stock line is refused, the page never sends one.
    setup["parts"].append({"role": "optic", "product": {"id": "ARCHON-DOT-ACRO"}, "choice": ""})
    refused = client.post("/v1/rig/quote", json={"setup": setup, "contact": contact}, headers=HEAD)
    assert refused.status_code == 422
    assert len(mail.letters) == 1
