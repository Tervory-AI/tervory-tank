"""Custom Nation Archon search, reservation letter, and shopper page.

No database and no network. The mailer is a fake. SMTP is guarded.
"""

from __future__ import annotations

import asyncio
import csv
import json
import smtplib
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "rig"))
sys.path.insert(0, str(ROOT / "agents" / "_chassis"))

from rigbox.api import mount  # noqa: E402
from rigbox.page_route import mount_page  # noqa: E402
from rigbox.reserve import SmtpMailer  # noqa: E402
from rigbox.service import RecordingHandoff, Service, WebhookHandoff  # noqa: E402
from rigbox.store import MemoryStore  # noqa: E402

ARCHON = ROOT / "agents" / "rig" / "catalogues" / "archon"
STACCATO = ROOT / "agents" / "rig" / "catalogues" / "customnation"
EXAMPLE = ROOT / "agents" / "rig" / "catalogues" / "example"
PAGE = ROOT / "agents" / "rig" / "rigbox" / "page" / "cn"
TENANT = "44444444-4444-4444-8444-444444444444"
STACCATO_TENANT = "33333333-3333-4333-8333-333333333333"
EXAMPLE_TENANT = "11111111-1111-4111-8111-111111111111"
ORIGIN = "https://rig.tervory.com"
KEY = "rk_pub_archon"

SPREAD = [
    "ARCHON-TYPE-B",
    "ARCHON-TYPE-A",
    "ARCHON-TYPE-B-PORTED",
    "ARCHON-DOT-ACRO",
    "ARCHON-DOT-RMR",
    "ARCHON-DOT-RMS",
    "ARCHON-HOLSTER-TB",
    "ARCHON-LIGHT",
    "ARCHON-MAG-12",
    "ARCHON-MAG-15",
    "ARCHON-MAG-18",
    "ARCHON-RMR-SCREWS",
    "ARCHON-TB-135",
    "ARCHON-TB-THREADED",
    "ARCHON-TRIGGER-PERF",
]
PORTED_SPREAD = [
    "ARCHON-TYPE-B-PORTED",
    "ARCHON-TYPE-A",
    "ARCHON-TYPE-B",
    *SPREAD[3:],
]
PISTOLS = ["ARCHON-TYPE-B", "ARCHON-TYPE-A", "ARCHON-TYPE-B-PORTED"]
TYPE_A_PISTOLS = ["ARCHON-TYPE-A", "ARCHON-TYPE-B", "ARCHON-TYPE-B-PORTED"]
DOTS = ["ARCHON-DOT-RMR", "ARCHON-DOT-ACRO", "ARCHON-DOT-RMS"]
MAGS = ["ARCHON-MAG-15", "ARCHON-MAG-12", "ARCHON-MAG-18"]
CHEAP = [
    "ARCHON-DOT-ACRO",
    "ARCHON-DOT-RMR",
    "ARCHON-DOT-RMS",
    "ARCHON-HOLSTER-TB",
    "ARCHON-LIGHT",
    "ARCHON-MAG-12",
    "ARCHON-MAG-15",
    "ARCHON-MAG-18",
    "ARCHON-RMR-SCREWS",
    "ARCHON-TB-135",
    "ARCHON-TB-THREADED",
    "ARCHON-TRIGGER-PERF",
    "ARCHON-TYPE-B",
]
AVAILABLE = [
    "ARCHON-TYPE-B",
    "ARCHON-TYPE-B-PORTED",
    "ARCHON-DOT-RMR",
    "ARCHON-DOT-RMS",
    "ARCHON-HOLSTER-TB",
    "ARCHON-LIGHT",
    "ARCHON-MAG-12",
    "ARCHON-MAG-15",
    "ARCHON-RMR-SCREWS",
    "ARCHON-TB-135",
    "ARCHON-TB-THREADED",
    "ARCHON-TRIGGER-PERF",
]
IN_STOCK_ALL = [
    "ARCHON-DOT-RMR",
    "ARCHON-DOT-RMS",
    "ARCHON-HOLSTER-TB",
    "ARCHON-LIGHT",
    "ARCHON-MAG-12",
    "ARCHON-MAG-15",
    "ARCHON-RMR-SCREWS",
    "ARCHON-TB-135",
    "ARCHON-TB-THREADED",
    "ARCHON-TRIGGER-PERF",
    "ARCHON-TYPE-B",
    "ARCHON-TYPE-B-PORTED",
]
UNDER_10 = [
    "ARCHON-DOT-RMR",
    "ARCHON-DOT-RMS",
    "ARCHON-HOLSTER-TB",
    "ARCHON-LIGHT",
    "ARCHON-MAG-12",
    "ARCHON-MAG-15",
    "ARCHON-MAG-18",
    "ARCHON-RMR-SCREWS",
    "ARCHON-TB-135",
    "ARCHON-TB-THREADED",
    "ARCHON-TRIGGER-PERF",
]
OVER_20 = ["ARCHON-TYPE-A", "ARCHON-TYPE-B", "ARCHON-TYPE-B-PORTED"]
BARRELS = ["ARCHON-TB-THREADED", "ARCHON-TB-135"]

# Each case is the query, the honest state, and the exact product ids in order.
GOLDEN = [
    ("Archon Type B", "exact", SPREAD, "ARCHON-TYPE-B", True, ""),
    ("archon type b", "exact", SPREAD, "ARCHON-TYPE-B", True, ""),
    ("type b ported", "exact", PORTED_SPREAD, "ARCHON-TYPE-B-PORTED", True, ""),
    ("Type B Ported", "exact", PORTED_SPREAD, "ARCHON-TYPE-B-PORTED", True, ""),
    ("FDE type b", "exact", SPREAD, "ARCHON-TYPE-B", True, ""),
    ("fde type b", "exact", SPREAD, "ARCHON-TYPE-B", True, ""),
    ("Type B FDE", "exact", SPREAD, "ARCHON-TYPE-B", True, ""),
    ("Type B and RMR", "exact", SPREAD, "ARCHON-TYPE-B", True, ""),
    ("RMR and Type B", "exact", SPREAD, "ARCHON-TYPE-B", True, ""),
    ("threaded type b", "exact", BARRELS, "ARCHON-TB-THREADED", True, ""),
    ("Archon Type B 9mm", "exact", SPREAD, "ARCHON-TYPE-B", True, ""),
    ("optic for type b", "exact", DOTS, "ARCHON-DOT-RMR", True, ""),
    ("acro in stock", "exact", ["ARCHON-DOT-ACRO", "ARCHON-DOT-RMR"], "ARCHON-DOT-ACRO", True, "out of stock"),
    ("pistol under R25 000", "exact", ["ARCHON-TYPE-B"], "ARCHON-TYPE-B", True, ""),
    ("glok 19", "not_stocked", [], "", False, "Glock"),
    ("glock", "not_stocked", [], "", False, "Glock"),
    ("Sig P320", "not_stocked", [], "", False, "Sig"),
    ("archn typ b", "exact", SPREAD, "ARCHON-TYPE-B", True, ""),
    ("15 round mag", "exact", ["ARCHON-MAG-15"], "ARCHON-MAG-15", True, ""),
    ("15 round magazine", "exact", ["ARCHON-MAG-15"], "ARCHON-MAG-15", True, ""),
    ("12 round mag", "exact", ["ARCHON-MAG-12"], "ARCHON-MAG-12", True, ""),
    ("18 round mag", "exact", ["ARCHON-MAG-18"], "ARCHON-MAG-18", True, ""),
    ("performance trigger", "exact", ["ARCHON-TRIGGER-PERF"], "ARCHON-TRIGGER-PERF", True, ""),
    ("rmr red dot", "exact", ["ARCHON-DOT-RMR"], "ARCHON-DOT-RMR", True, ""),
    ("what red dots fit the type b", "exact", DOTS, "ARCHON-DOT-RMR", True, ""),
    ("red dot", "exact", DOTS, "ARCHON-DOT-RMR", True, ""),
    ("under R25 000", "exact", CHEAP, "", True, ""),
    ("under R 25 000", "exact", CHEAP, "", True, ""),
    ("below R10000", "exact", UNDER_10, "", True, ""),
    ("over R20000", "exact", OVER_20, "", True, ""),
    ("in stock type b", "exact", AVAILABLE, "ARCHON-TYPE-B", True, ""),
    ("in stock only", "exact", IN_STOCK_ALL, "", True, ""),
    ("Archon Type C", "closest", PISTOLS, "ARCHON-TYPE-B", False, "Type C"),
    ("Archon Type D", "closest", PISTOLS, "ARCHON-TYPE-B", False, "Type D"),
    ("type c", "closest", PISTOLS, "ARCHON-TYPE-B", False, "type c"),
    ("Glock 19", "not_stocked", [], "", False, "Glock"),
    ("glock 19", "not_stocked", [], "", False, "Glock"),
    ("hello", "nothing", [], "", True, "Nothing matches"),
    ("the", "nothing", [], "", True, "Nothing matches"),
    ("xq-77 laser grip", "nothing", [], "", True, "Nothing matches"),
    ("asdfghjkl", "nothing", [], "", True, "Nothing matches"),
    ("pistol", "exact", PISTOLS, "ARCHON-TYPE-B", True, ""),
    ("black", "exact", PISTOLS, "ARCHON-TYPE-B", True, ""),
    ("Archon Type A", "exact", TYPE_A_PISTOLS, "ARCHON-TYPE-A", True, ""),
    ("type a", "exact", TYPE_A_PISTOLS, "ARCHON-TYPE-A", True, ""),
    ("acro", "exact", ["ARCHON-DOT-ACRO"], "ARCHON-DOT-ACRO", True, ""),
    ("optic", "exact", DOTS, "ARCHON-DOT-RMR", True, ""),
    ("sight", "exact", DOTS, "ARCHON-DOT-RMR", True, ""),
    ("trigger", "exact", ["ARCHON-TRIGGER-PERF"], "ARCHON-TRIGGER-PERF", True, ""),
    ("trigger for type b", "exact", ["ARCHON-TRIGGER-PERF"], "ARCHON-TRIGGER-PERF", True, ""),
    ("Type B pink", "closest", PISTOLS, "ARCHON-TYPE-B", False, "Pink isn't a colour"),
    ("Type B OD green", "closest", PISTOLS, "ARCHON-TYPE-B", False, "OD green isn't a colour"),
    ("type b magazine", "exact", MAGS, "ARCHON-MAG-15", True, ""),
    ("type b light", "exact", ["ARCHON-LIGHT"], "ARCHON-LIGHT", True, ""),
    ("type b barrel", "exact", BARRELS, "ARCHON-TB-THREADED", True, ""),
    ("type b rmr", "exact", ["ARCHON-DOT-RMR", "ARCHON-RMR-SCREWS"], "ARCHON-DOT-RMR", True, ""),
    ("type b trigger", "exact", ["ARCHON-TRIGGER-PERF"], "ARCHON-TRIGGER-PERF", True, ""),
    ("magazine", "exact", MAGS, "ARCHON-MAG-15", True, ""),
    ("holster", "exact", ["ARCHON-HOLSTER-TB"], "ARCHON-HOLSTER-TB", True, ""),
    ("light", "exact", ["ARCHON-LIGHT"], "ARCHON-LIGHT", True, ""),
    ("barrel", "exact", BARRELS, "ARCHON-TB-THREADED", True, ""),
    ("suppressor ready", "exact", ["ARCHON-TYPE-B", "ARCHON-TB-THREADED"], "ARCHON-TYPE-B", True, ""),
    ("ported", "exact", ["ARCHON-TYPE-B-PORTED"], "ARCHON-TYPE-B-PORTED", True, ""),
    ("rmr mounting screw", "exact", ["ARCHON-RMR-SCREWS"], "ARCHON-RMR-SCREWS", True, ""),
    ("fde", "exact", PISTOLS, "ARCHON-TYPE-B", True, ""),
]


class Mail:
    def __init__(self) -> None:
        self.letters: list[dict[str, str]] = []

    async def send(self, letter: dict[str, str]) -> None:
        self.letters.append(letter)


class Http:
    def __init__(self) -> None:
        self.posts: list[tuple[str, dict]] = []

    async def post(self, url: str, json: dict) -> None:
        self.posts.append((url, json))


def _sheet() -> tuple[dict[str, dict], dict[str, set[str]]]:
    products: dict[str, dict] = {}
    with (ARCHON / "products.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            products[row["sku"]] = row
    notes: dict[str, set[str]] = {}
    with (ARCHON / "fits.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            notes.setdefault(row["part_sku"], set()).add(row["note"])
    return products, notes


async def _archon(handoff=None) -> Service:
    service = Service(MemoryStore(), handoff=handoff or RecordingHandoff())
    report = await service.load_folder(ARCHON)
    assert report["products"]["rejected"] == []
    assert report["products"]["added"] == 15
    assert report["fits"]["rejected"] == []
    return service


def _guard_smtp(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_args, **_kwargs):
        raise AssertionError("a test tried to open SMTP")

    monkeypatch.setattr(smtplib, "SMTP", refuse)
    monkeypatch.setattr(smtplib, "SMTP_SSL", refuse)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "honest", "ids", "focus", "exact", "message"),
    GOLDEN,
    ids=[case[0] if case[0].strip() else "blank" for case in GOLDEN],
)
async def test_archon_golden_queries(query, honest, ids, focus, exact, message) -> None:
    service = await _archon()
    body = await service.search(TENANT, query, 24)
    assert body["honest"] == honest
    assert body["ids"] == ids
    assert body.get("focus_id") == focus
    assert body["exact_match"] is exact
    if message:
        assert message in str(body.get("message") or "")
    if honest == "closest":
        assert "TYPE-C" not in "".join(body["ids"])
        assert "TYPE-D" not in "".join(body["ids"])
        assert all("Glock" not in item["name"] for item in body["results"])


@pytest.mark.asyncio
async def test_empty_and_whitespace_are_empty() -> None:
    service = await _archon()
    for query in ("", "   ", "\n"):
        body = await service.search(TENANT, query, 24)
        assert body == {
            "results": [],
            "ids": [],
            "exact_match": True,
            "honest": "empty",
            "focus_id": "",
            "groups": [],
        }


@pytest.mark.asyncio
async def test_filters_stock_price_category_and_sort() -> None:
    service = await _archon()
    stocked = await service.search(TENANT, "Archon Type B", 24, {"in_stock": True})
    assert stocked["ids"] == AVAILABLE
    priced = await service.search(TENANT, "", 24, {"max_price_inclusive": 25000})
    assert "ARCHON-TYPE-B" in priced["ids"]
    assert "ARCHON-TYPE-A" not in priced["ids"]
    assert "ARCHON-TYPE-B-PORTED" not in priced["ids"]
    sights = await service.search(TENANT, "Archon Type B", 24, {"category": "Sights"})
    assert sights["ids"] == DOTS
    assert sights["focus_id"] == "ARCHON-DOT-RMR"
    high = await service.search(TENANT, "pistol", 24, {"sort": "price_desc"})
    assert high["ids"] == ["ARCHON-TYPE-B-PORTED", "ARCHON-TYPE-A", "ARCHON-TYPE-B"]
    low = await service.search(TENANT, "pistol", 24, {"sort": "price_asc"})
    assert low["ids"] == ["ARCHON-TYPE-B", "ARCHON-TYPE-A", "ARCHON-TYPE-B-PORTED"]
    inclusive = await service.search(TENANT, "", 24, {"min_price": 24990})
    assert "ARCHON-TYPE-B" in inclusive["ids"]
    assert "ARCHON-MAG-15" not in inclusive["ids"]


@pytest.mark.asyncio
async def test_prices_fits_and_the_out_of_stock_alternative() -> None:
    service = await _archon()
    body = await service.search(TENANT, "Archon Type B", 24)
    by_id = {item["id"]: item for item in body["results"]}
    assert [by_id[sku]["compare"]["delta"] for sku in ("ARCHON-TYPE-B", "ARCHON-TYPE-A", "ARCHON-TYPE-B-PORTED")] == [0, 2000, 3500]
    assert [by_id[sku]["compare"]["delta"] for sku in ("ARCHON-DOT-RMS", "ARCHON-DOT-RMR", "ARCHON-DOT-ACRO")] == [0, 2500, 5000]
    assert by_id["ARCHON-DOT-RMR"]["fit"]["badge"] == "Fits your RMR cut"
    assert by_id["ARCHON-DOT-RMS"]["fit"]["badge"] == "Needs RMS cut"
    assert by_id["ARCHON-DOT-ACRO"]["fit"]["badge"] == "Needs ACRO cut"
    assert by_id["ARCHON-DOT-ACRO"]["alternative"]["id"] == "ARCHON-DOT-RMR"
    assert by_id["ARCHON-LIGHT"]["fit"] is None
    assert by_id["ARCHON-HOLSTER-TB"]["fit"] is None
    assert by_id["ARCHON-TYPE-B"]["price"]["amount"] == 24990
    assert by_id["ARCHON-TYPE-B"]["availability"]["status"] == "in_stock"
    assert by_id["ARCHON-TYPE-B"]["availability"]["label"] == "Demo stock"
    assert by_id["ARCHON-TYPE-B"]["price_label"] == "Demo price"
    assert by_id["ARCHON-TYPE-A"]["availability"]["status"] == "on_order"
    assert by_id["ARCHON-TYPE-B-PORTED"]["availability"]["qty"] == 1
    assert len(body["groups"]) == 8


@pytest.mark.asyncio
async def test_nothing_is_fabricated() -> None:
    products, notes = _sheet()
    service = await _archon()
    queries = [case[0] for case in GOLDEN] + ["", "Archon", "magazine", "optic"]
    seen: set[str] = set()
    for query in queries:
        body = await service.search(TENANT, query, 24)
        for item in body["results"]:
            assert item["id"] in products, item["id"]
            sheet = products[item["id"]]
            assert item["name"] == sheet["name"]
            assert item["price"]["amount"] == int(Decimal(sheet["price"]))
            assert item["price"]["currency"] == sheet["currency"]
            attrs = json.loads(sheet["attributes"])
            assert item["price_label"] == attrs.get("price_label")
            assert item["availability"]["status"] == attrs["stock"]["status"]
            verified = attrs.get("verified") or []
            assert isinstance(verified, list)
            for spec in verified:
                source = str(spec.get("source") or "")
                assert source.startswith("https://"), (item["id"], spec.get("name"))
                assert spec.get("name") and "value" in spec
            assert ((item.get("attributes") or {}).get("verified") or []) == verified
            fit = item["fit"]
            if fit is None:
                assert item["id"] not in notes
            else:
                assert fit["note"] in notes[item["id"]]
            seen.add(item["id"])
    assert seen == set(products)


@pytest.mark.asyncio
async def test_list_product_graph_and_setups_share_one_price() -> None:
    service = await _archon()
    found = await service.search(TENANT, "Archon Type B", 24)
    listed = {item["id"]: item for item in found["results"]}
    for sku in ("ARCHON-TYPE-B", "ARCHON-DOT-RMR", "ARCHON-DOT-ACRO", "ARCHON-MAG-15"):
        detail = await service.product(TENANT, sku)
        graph = await service.graph(TENANT, sku)
        setups = await service.setups(TENANT, sku)
        assert detail["price"] == listed[sku]["price"]
        assert detail["availability"] == listed[sku]["availability"]
        assert detail["options"] == listed[sku]["options"]
        assert graph["centre"]["price"] == listed[sku]["price"]
        assert graph["centre"]["availability"] == listed[sku]["availability"]
        centre_part = setups["setups"][0]["parts"][0]["product"]
        assert centre_part["id"] == sku
        assert centre_part["price"] == listed[sku]["price"]
        assert centre_part["options"] == listed[sku]["options"]


@pytest.mark.asyncio
async def test_reservation_letter_is_parsed_and_never_mailed(monkeypatch: pytest.MonkeyPatch) -> None:
    _guard_smtp(monkeypatch)
    mail = Mail()
    service = await _archon(WebhookHandoff(None, mail))
    setup = {
        "label": "Your Type B build",
        "parts": [
            {
                "product": {"id": "ARCHON-TYPE-B", "name": "Hacked", "price": {"amount": 1, "currency": "USD"}},
                "choice": "Black/Black · 4.3 standard · RMR",
            },
            {"product": {"id": "ARCHON-TRIGGER-PERF"}, "choice": "Performance"},
            {"product": {"id": "ARCHON-DOT-RMR"}, "choice": "RMR"},
            {"product": {"id": "ARCHON-RMR-SCREWS"}, "choice": ""},
            {"product": {"id": "ARCHON-MAG-15"}, "choice": "15 rounds"},
        ],
    }
    quoted = await service.quote(
        TENANT,
        {"setup": setup, "contact": {"name": "Ada Buyer", "email": "ada@example.com", "phone": "+27 68 000 0000"}},
    )
    assert quoted["delivered"] is True
    assert len(mail.letters) == 1
    letter = mail.letters[0]
    reference = quoted["request_id"]
    assert letter["to"] == "sales@customnation.co.za"
    assert letter["reference"] == reference
    assert letter["subject"] == f"Reservation: Archon Type B - {reference}"
    text = letter["text"]
    assert "Customer-Name: Ada Buyer" in text
    assert "Customer-Email: ada@example.com" in text
    assert "Customer-Phone: +27 68 000 0000" in text
    assert "Item-Code: ARCHON-TYPE-B" in text
    assert "Item-Code: ARCHON-TRIGGER-PERF" in text
    assert "Item-Code: ARCHON-DOT-RMR" in text
    assert "Item-Code: ARCHON-RMR-SCREWS" in text
    assert "Item-Code: ARCHON-MAG-15" in text
    assert "Item-Amount: 24990" in text
    assert "Item-Amount: 1\n" not in text
    assert "Item-Price-Label: Demo price" in text
    assert "Total-Amount: 39050" in text
    assert "Total-Label: Demo price" in text
    assert "confirms stock and paperwork" in text
    assert "Custom Nation confirms stock" in text
    assert "Item-Stock: in_stock" in text
    assert "Hacked" not in text
    assert letter["reply_to"] == "ada@example.com"


@pytest.mark.asyncio
async def test_webhook_still_wins_and_missing_mail_does_not_send(monkeypatch: pytest.MonkeyPatch) -> None:
    _guard_smtp(monkeypatch)
    mail = Mail()
    http = Http()
    service = Service(MemoryStore(), handoff=WebhookHandoff(http, mail))
    await service.load_folder(EXAMPLE)
    await service.quote(
        EXAMPLE_TENANT,
        {"product_id": "EXAMPLE-RIFLE-01", "contact": {"name": "Ada Buyer", "email": "ada@example.com"}},
    )
    assert http.posts and http.posts[0][0] == "https://example.com/hooks/rig"
    assert mail.letters == []
    quiet = await _archon(WebhookHandoff(None, None))
    saved = await quiet.quote(
        TENANT,
        {"product_id": "ARCHON-TYPE-B", "contact": {"name": "Ada Buyer", "email": "ada@example.com"}},
    )
    assert saved["delivered"] is False
    assert saved["request_id"].startswith("req_")


def test_smtp_from_env_is_off_without_a_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SMTP_HOST", raising=False)
    assert SmtpMailer.from_env() is None


def test_smtp_send_is_blocked_by_the_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    _guard_smtp(monkeypatch)
    mailer = SmtpMailer("127.0.0.1", 587, "", "", "from@example.com")
    with pytest.raises(AssertionError, match="SMTP"):
        asyncio.run(mailer.send({"to": "sales@customnation.co.za", "subject": "x", "text": "y"}))


@pytest.mark.asyncio
async def test_staccato_search_is_unchanged() -> None:
    service = Service(MemoryStore())
    await service.load_folder(STACCATO)
    await service.load_folder(ARCHON)
    assert await service.search(STACCATO_TENANT, "Glock 19", 12) == {"results": []}
    assert await service.search(STACCATO_TENANT, "", 12) == {"results": []}
    found = await service.search(STACCATO_TENANT, "Staccato C2", 12)
    assert found["exact_match"] is True
    compact = next(item for item in found["results"] if item["id"] == "STI-C2-9")
    assert list(compact) == ["id", "name", "brand", "category", "image", "price", "attributes"]
    assert compact["price"]["amount"] == 58999


@pytest.mark.asyncio
async def test_ask_muzzle_velocity_is_i_dont_know() -> None:
    class Quiet:
        async def complete(self, tenant_id: str, task_type: str, messages: list) -> str:
            raise AssertionError("the model must not be asked")

    service = Service(MemoryStore(), Quiet())
    await service.load_folder(ARCHON)
    body = await service.ask(
        TENANT,
        "ARCHON-TYPE-B",
        "What muzzle velocity does the Type B get with 147 gr ammo?",
    )
    assert body["answer"] == "I don't know"
    assert body["cites"] == []


def test_cn_page_reads_the_shop_settings_and_blocks_traversal() -> None:
    app = FastAPI()
    mount_page(app)
    client = TestClient(app)
    page = client.get("/cn")
    assert page.status_code == 200
    assert "sales@customnation.co.za" in page.text
    assert "+27 68 637 3249" in page.text
    assert "__CN_EMAIL__" not in page.text
    assert "__CN_KEY__" not in page.text
    assert "rk_pub_archon" in page.text
    home = client.get("/")
    assert "Custom Nation" not in home.text
    script = client.get("/page/cn/cn.js")
    assert script.status_code == 200
    assert "sales@customnation.co.za" not in script.text
    assert "confirm stock and paperwork" in script.text
    assert "does not send alerts" in script.text
    css = (PAGE / "cn.css").read_text(encoding="utf-8")
    assert "#E80008" not in css
    assert "#e4d2b0" in css
    logo = client.get("/page/cn/cn-logo.png")
    assert logo.status_code == 200
    assert client.get("/page/cn/../../catalogues/archon/publish.json").status_code == 404
    visual = client.get("/page/cn/visual.js")
    assert visual.status_code == 200
    assert "CNVisual" in visual.text


def test_search_route_accepts_archon_filters() -> None:
    async def prepare():
        return await _archon()

    service = asyncio.run(prepare())
    app = FastAPI()
    app.state.rig = service
    mount(app)
    client = TestClient(app)
    response = client.get(
        "/v1/rig/search",
        params={"q": "Archon Type B", "limit": 24, "in_stock": "true", "max_price": 30000},
        headers={"X-Rig-Key": KEY, "Origin": ORIGIN},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ids"] == AVAILABLE
    assert body["focus_id"] == "ARCHON-TYPE-B"


@pytest.mark.asyncio
async def test_staccato_letter_queries_match_main_wording() -> None:
    service = Service(MemoryStore())
    await service.load_folder(STACCATO)
    expected = {
        "staccato c": "No exact match for c.",
        "staccato x": "No exact match for x.",
        "Staccato c 4": "No exact match for c 4.",
        "staccato z": "No exact match for z.",
    }
    for query, message in expected.items():
        body = await service.search(STACCATO_TENANT, query, 12)
        assert body.get("message") == message
        assert body["exact_match"] is False
        assert "staccato c," not in str(body.get("message") or "")
    exact = await service.search(STACCATO_TENANT, "Staccato C2", 12)
    assert exact["exact_match"] is True
    assert exact.get("message") in (None, "")
    pistol = await service.search(STACCATO_TENANT, "Staccato P", 12)
    assert pistol["exact_match"] is True
    assert any(item["id"] == "STI-P-9" for item in pistol["results"])
    for query in ("type b", "type c", "holster c", "red dot b"):
        body = await service.search(STACCATO_TENANT, query, 12)
        assert body["exact_match"] is True, query
        assert "No exact match" not in str(body.get("message") or "")
        assert body["results"]


@pytest.mark.asyncio
async def test_a_shop_with_email_and_no_mailer_matches_main(monkeypatch: pytest.MonkeyPatch) -> None:
    _guard_smtp(monkeypatch)
    service = Service(MemoryStore(), handoff=WebhookHandoff(None, None))
    await service.load_folder(STACCATO)
    quoted = await service.quote(
        STACCATO_TENANT,
        {"product_id": "STI-C2-9", "contact": {"name": "Ada Buyer", "email": "ada@example.com"}},
    )
    assert quoted == {"request_id": quoted["request_id"]}
    assert "delivered" not in quoted
    saved = await service.store.quotes_for(STACCATO_TENANT)
    assert saved[0]["sent_at"] == "sent"
    example = Service(MemoryStore(), handoff=WebhookHandoff(Http(), Mail()))
    await example.load_folder(EXAMPLE)
    other = await example.quote(
        EXAMPLE_TENANT,
        {"product_id": "EXAMPLE-RIFLE-01", "contact": {"name": "Ada Buyer", "email": "ada@example.com"}},
    )
    assert set(other) == {"request_id"}


@pytest.mark.asyncio
async def test_letter_uses_the_retailer_name_and_readable_choices(monkeypatch: pytest.MonkeyPatch) -> None:
    _guard_smtp(monkeypatch)
    from rigbox.reserve import reservation_letter

    letter = reservation_letter(
        "req_demo",
        {"product": {"id": "X", "name": "Item", "price": {"amount": 1, "currency": "ZAR"}, "attributes": {}}},
        {"name": "Ada", "email": "ada@example.com"},
        {"name": "Example Shop", "email": "buyer@example.com"},
    )
    assert "Example Shop confirms stock" in letter["text"]
    assert "Custom Nation" not in letter["text"]
    mail = Mail()
    service = await _archon(WebhookHandoff(None, mail))
    await service.quote(
        TENANT,
        {
            "setup": {
                "parts": [
                    {"product": {"id": "ARCHON-TYPE-B"}, "choice": "Black/Black · barrel-1228 · RMR"},
                    {"product": {"id": "ARCHON-DOT-RMR"}, "choice": "RMR"},
                ]
            },
            "contact": {"name": "Ada Buyer", "email": "ada@example.com"},
        },
    )
    text = mail.letters[0]["text"]
    assert "1/2-28 RH" in text
    assert "barrel-1228" not in text
    assert "Item-Stock:" in text
    with pytest.raises(Exception) as unfit:
        await service.quote(
            TENANT,
            {
                "setup": {
                    "parts": [
                        {"product": {"id": "ARCHON-TYPE-B"}, "choice": "Black/Black · 4.3\" standard · RMR"},
                        {"product": {"id": "ARCHON-DOT-RMS"}, "choice": ""},
                    ]
                },
                "contact": {"name": "Ada Buyer", "email": "ada@example.com"},
            },
        )
    assert unfit.value.status == 422  # type: ignore[attr-defined]
    with pytest.raises(Exception) as missing:
        await service.quote(
            TENANT,
            {"product_id": "ARCHON-DOT-ACRO", "contact": {"name": "Ada Buyer", "email": "ada@example.com"}},
        )
    assert missing.value.status == 422  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_parts_query_lists_every_part_and_verified_sources_are_cited() -> None:
    products, _notes = _sheet()
    service = await _archon()
    for query in ("part", "parts"):
        body = await service.search(TENANT, query, 24)
        ids = set(body["ids"])
        assert "ARCHON-RMR-SCREWS" in ids
        assert "ARCHON-TB-THREADED" in ids
        assert "ARCHON-MAG-15" in ids
        assert "ARCHON-TYPE-B" not in ids
        assert ids == {sku for sku, row in products.items() if row["category"] != "Pistols"}
    detail = await service.product(TENANT, "ARCHON-TYPE-B")
    verified = detail["attributes"]["verified"]
    assert any(spec["name"] == "in_box" and "lock" in str(spec["value"]) for spec in verified)
    assert all(str(spec["source"]).startswith("https://archonfirearms.com") for spec in verified)
    type_a = await service.product(TENANT, "ARCHON-TYPE-A")
    assert type_a["demo_item"] is False
    ported = await service.product(TENANT, "ARCHON-TYPE-B-PORTED")
    assert ported["demo_item"] is False
    assert "not listed" not in json.dumps(ported["attributes"]).lower()


def test_reservation_route_is_limited_per_ip() -> None:
    service = asyncio.run(_archon())
    app = FastAPI()
    app.state.rig = service
    mount(app)
    client = TestClient(app)
    headers = {"X-Rig-Key": KEY, "Origin": ORIGIN}
    payload = {
        "product_id": "ARCHON-TYPE-B",
        "contact": {"name": "Ada Buyer", "email": "ada@example.com"},
    }
    statuses = [
        client.post("/v1/rig/quote", json=payload, headers=headers).status_code
        for _ in range(6)
    ]
    assert statuses[:5] == [200, 200, 200, 200, 200]
    assert statuses[5] == 429


def test_staccato_quotes_are_not_rate_limited() -> None:
    async def prepare():
        service = Service(MemoryStore(), handoff=WebhookHandoff(None, None))
        await service.load_folder(STACCATO)
        return service

    service = asyncio.run(prepare())
    app = FastAPI()
    app.state.rig = service
    mount(app)
    client = TestClient(app)
    headers = {"X-Rig-Key": "rk_pub_customnation", "Origin": ORIGIN}
    payload = {
        "product_id": "STI-C2-9",
        "contact": {"name": "Ada Buyer", "email": "ada@example.com"},
    }
    statuses = [
        client.post("/v1/rig/quote", json=payload, headers=headers).status_code
        for _ in range(6)
    ]
    assert statuses == [200, 200, 200, 200, 200, 200]
    body = client.post("/v1/rig/quote", json=payload, headers=headers).json()
    assert set(body) == {"request_id"}


def test_forwarded_for_counts_only_from_a_private_peer() -> None:
    from rigbox.api import _client_ip

    class Client:
        def __init__(self, host: str) -> None:
            self.host = host

    class Request:
        def __init__(self, host: str, forwarded: str) -> None:
            self.client = Client(host)
            self.headers = {"x-forwarded-for": forwarded}

    assert _client_ip(Request("10.0.0.8", "203.0.113.9, 10.0.0.8")) == "203.0.113.9"
    assert _client_ip(Request("172.18.0.2", "198.51.100.4")) == "198.51.100.4"
    assert _client_ip(Request("203.0.113.8", "198.51.100.4")) == "203.0.113.8"
    assert _client_ip(Request("testclient", "198.51.100.4")) == "testclient"


@pytest.mark.asyncio
async def test_a_short_choice_is_not_a_longer_option(monkeypatch: pytest.MonkeyPatch) -> None:
    _guard_smtp(monkeypatch)
    service = await _archon(WebhookHandoff(None, Mail()))
    with pytest.raises(Exception) as caught:
        await service.quote(
            TENANT,
            {
                "setup": {
                    "parts": [
                        {"product": {"id": "ARCHON-TYPE-B"}, "choice": "Bla"},
                    ]
                },
                "contact": {"name": "Ada Buyer", "email": "ada@example.com"},
            },
        )
    assert caught.value.status == 422  # type: ignore[attr-defined]
    assert "Bla" in str(caught.value)
