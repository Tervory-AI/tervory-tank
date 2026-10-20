"""Candidate provenance, exclusion, image payloads and room authentication."""
import importlib.util
import json
import sys
import secrets
from urllib.parse import urlsplit

from selectolax.parser import HTMLParser
from pathlib import Path
from zipfile import ZipFile

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents/tiger"))
sys.path.insert(0, str(ROOT / "agents/_chassis"))
_spec = importlib.util.spec_from_file_location('tiger_gold_sources', ROOT / 'agents/tiger/gold_sources.py')
gold = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gold)


def test_corpus_and_candidates():
    with ZipFile(gold.CORPUS) as archive:
        rows = json.loads(archive.read("manifest.json"))
    assert len(rows) == 51
    output = gold.candidates()
    eligible = [r for r in rows if r['split'] == 'build' and not r['conflict'] and not r['unreadable']]
    assert len(output) == len(eligible) * 2
    assert {r['skill_id'] for r in output} == {'tiger.price_extract', 'tiger.price_ocr'}
    for row in output:
        assert set(row) == {'skill_id', 'input', 'expected', 'label_source', 'region', 'public'}
        assert row['public'] is True and row['region'] == 'us-east'
        assert row['label_source'].startswith('auto:')
        if row['skill_id'].endswith('ocr'):
            import base64
            assert base64.b64decode(row['input']['png_base64']).startswith(b'\x89PNG')
            assert 'text' not in row['input']
    assert gold.candidates(1) == output[:1]
    assert gold.candidates(region='za') == []
    assert gold.candidates(region='invalid') == []
    assert gold.candidates(0) == []


@pytest.mark.parametrize('html,want', [
    ('<h1>Item</h1><p>$9.00</p><script type="application/ld+json">{"@type":"Product","offers":{"price":"9.00"}}</script>', '9.00'),
    ('<p>$9.00</p><meta itemprop="price" content="9">', '9.00'),
    ('<p>$8.00</p><meta itemprop="price" content="9">', None),
    ('<p hidden>$9.00</p><meta itemprop="price" content="9">', None),
    ('<p>$9.00 $8.00</p><meta itemprop="price" content="9">', None),
    ('<script type="application/ld+json">broken</script>', None),
])
def test_independent_agreement(html, want):
    assert gold.agreement(html) == want


@pytest.mark.asyncio
async def test_room_auth_and_limit(monkeypatch):
    monkeypatch.setitem(sys.modules, "gold_sources", gold)
    spec = importlib.util.spec_from_file_location('tiger_gold_app', ROOT / 'agents/tiger/app.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    key = secrets.token_hex(24)
    monkeypatch.setenv('TANK_KEY', key)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=mod.app), base_url='http://test') as client:
        for headers in ({}, {'X-Tank-Key': 'other-room-key'}, {'X-Tank-Key': 'workspace-key'},
                        {b'X-Tank-Key': b'\xff'}):
            assert (await client.get('/gold/candidates', headers=headers)).status_code == 401
        headers = {'X-Tank-Key': key}
        response = await client.get('/gold/candidates?limit=2', headers=headers)
        assert response.status_code == 200 and len(response.json()) == 2
        for limit in ('0', '-1', '201', 'no'):
            assert (await client.get('/gold/candidates?limit=' + limit, headers=headers)).status_code == 422
        monkeypatch.setenv('TANK_REGION', 'za')
        assert (await client.get('/gold/candidates', headers=headers)).json() == []
        monkeypatch.delenv('TANK_KEY')
        assert (await client.get('/gold/candidates', headers=headers)).status_code == 401


def test_bundle_only_contains_allowlisted_hosts_and_no_token_meta():
    allowed = set(json.loads(gold.CORPUS.with_name("allowed-hosts.json").read_text()))
    assert allowed == {
        "demo.spreecommerce.org", "demo.mage-os.org", "demo.solidus.io",
        "scrapeme.live", "webscraper.io", "books.toscrape.com", "example.test",
    }
    with ZipFile(gold.CORPUS) as archive:
        rows = json.loads(archive.read("manifest.json"))
        assert {urlsplit(row["url"]).hostname for row in rows} == allowed
        assert set(archive.namelist()) == {"manifest.json"} | {
            row["id"] + suffix for row in rows for suffix in (".html", ".png")
        }
        for row in rows:
            tree = HTMLParser(archive.read(row["id"] + ".html"))
            for meta in tree.css("meta"):
                assert meta.attributes.get("itemprop")
                attrs = json.dumps(meta.attributes).lower()
                assert "csrf" not in attrs and "token" not in attrs


def test_bundle_rebuild_removes_non_itemprop_meta(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("tiger_bundle", ROOT / "tests/build_tiger_gold_bundle.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    source = tmp_path / "source"
    (source / "gold/shots").mkdir(parents=True)
    rows = []
    token = secrets.token_hex(24)
    for name, host in [("demo", "example.test"), ("retailer", "retailer.invalid")]:
        rows.append({"id": name, "url": f"https://{host}/item", "html": name + ".html"})
        (source / (name + ".html")).write_text(
            f'<meta name="csrf-token" content="{token}">'
            f'<meta name="anti-csrftoken" content="{token}">'
            '<meta name="description" content="remove">'
            '<meta itemprop="price" content="9"><p>$9</p>'
        )
        (source / "gold/shots" / (name + ".png")).write_bytes(b"\x89PNG\r\n\x1a\n")
    (source / "gold/pages.jsonl").write_text("\n".join(json.dumps(row) for row in rows))
    dest = tmp_path / "public-pages.zip"
    dest.with_name("allowed-hosts.json").write_text('["example.test"]')
    monkeypatch.setattr(builder, "SOURCE", source)
    monkeypatch.setattr(builder, "DEST", dest)
    builder.build()
    first = dest.read_bytes()
    builder.build()
    assert dest.read_bytes() == first
    with ZipFile(dest) as archive:
        assert json.loads(archive.read("manifest.json")) == rows[:1]
        assert set(archive.namelist()) == {"manifest.json", "demo.html", "demo.png"}
        html = archive.read("demo.html").decode()
        assert token not in html
        assert "csrf" not in html and "token" not in html
        assert HTMLParser(html).css_first('meta[itemprop="price"]').attributes["content"] == "9"


@pytest.mark.asyncio
async def test_optional_snapshot_file_is_never_exported(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "gold_sources", gold)
    spec = importlib.util.spec_from_file_location('tiger_snapshot_app', ROOT / 'agents/tiger/app.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("TANK_REGION", "us-east")
    key = secrets.token_hex(24)
    monkeypatch.setenv("TANK_KEY", key)
    (tmp_path / "gold").mkdir()
    (tmp_path / "gold/public_snapshots.json").write_text(json.dumps([{
        "public": True, "robots_allowed": True, "terms_allowed": True,
        "challenge": False, "authenticated": False, "region": "us-east",
        "url": "https://example.test/client-watch",
        "html": '<p>$9.00</p><meta itemprop="price" content="9">',
    }]))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=mod.app), base_url='http://test') as client:
        response = await client.get('/gold/candidates', headers={'X-Tank-Key': key})
    assert response.status_code == 200
    assert response.json() == gold.candidates()
    assert not hasattr(gold, "snapshot_candidates")


def test_microdata_text_and_currency_disagreement():
    assert gold.agreement('<p itemprop="price">$9.00</p>') == '9.00'
    assert gold.agreement('<p>£9.00</p><meta itemprop="price" content="9"><meta itemprop="priceCurrency" content="USD">') is None


def test_image_ships_corpus_and_region():
    dockerfile = (ROOT / 'agents/tiger/Dockerfile').read_text()
    assert 'COPY tiger/gold_sources.py /app/gold_sources.py' in dockerfile
    assert 'COPY tiger/gold /app/gold' in dockerfile
    assert 'TANK_REGION: ${TANK_REGION:-us-east}' in (ROOT / 'agents/tiger/docker-compose.yml').read_text()
