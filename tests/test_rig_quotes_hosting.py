"""The public bundle is immutable, verified and contains no sample catalogue."""

import gzip
import hashlib
import json
from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents" / "rig"))
from rigbox.quotes import hosting  # noqa: E402
from rigbox.quotes.hosting import TEST_PAGE_CSP, mount  # noqa: E402


def test_packaged_bundle_and_configured_test_page(monkeypatch):
    monkeypatch.delenv("RIG_WIDGET_DIR", raising=False)
    monkeypatch.delenv("RIG_WIDGET_PUBLISHABLE_KEY", raising=False)
    hosting._verified_asset.cache_clear()
    app = FastAPI()
    mount(app)
    with TestClient(app) as client:
        manifest = client.get("/widget/manifest.json")
        assert manifest.status_code == 200
        name = manifest.json()["file"]
        response = client.get("/widget/assets/" + name)
        assert response.status_code == 200
        assert hashlib.sha256(response.content).hexdigest() in name
        assert len(gzip.compress(response.content)) < 150 * 1024
        assert "immutable" in response.headers["Cache-Control"]
        assert response.headers["Access-Control-Allow-Origin"] == "*"
        assert "mock_not_bundled" in response.text
        assert client.get("/widget/test").status_code == 503
        monkeypatch.setenv("RIG_WIDGET_PUBLISHABLE_KEY", "rk_pub_sample")
        page = client.get("/widget/test")
        assert page.status_code == 200 and 'theme="custom-nation"' in page.text
        assert 'api-base=""' in page.text and 'api-base="mock"' not in page.text
        assert name in page.text and page.headers["Cache-Control"] == "no-store"
        assert page.headers["Content-Security-Policy"] == TEST_PAGE_CSP
        assert "frame-ancestors 'none'" in TEST_PAGE_CSP
        assert "default-src 'none'" in TEST_PAGE_CSP
        assert "script-src 'self'" in TEST_PAGE_CSP
        assert list((Path(__file__).resolve().parents[1] / "agents/rig/rigbox/quotes/widget").glob("*.umd.js"))[0].name == name
        assert len(list((Path(__file__).resolve().parents[1] / "agents/rig/rigbox/quotes/widget").glob("*.umd.js"))) == 1
        assert 'fonts="/widget/fonts/custom-nation.css"' in page.text
        css = client.get("/widget/fonts/custom-nation.css")
        assert css.status_code == 200 and "Barlow Condensed" in css.text
        font = client.get("/widget/fonts/barlow-condensed-latin-600-normal.woff2")
        assert font.status_code == 200 and font.content.startswith(b"wOF2")
        assert client.get("/widget/fonts/hosting.py").status_code == 404


def test_corruption_and_unknown_paths_fail_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("RIG_WIDGET_DIR", str(tmp_path))
    hosting._verified_asset.cache_clear()
    name = "tervory-rig." + "0" * 64 + ".umd.js"
    (tmp_path / name).write_text("altered artifact")
    (tmp_path / "manifest.json").write_text(json.dumps({"file": name}))
    app = FastAPI()
    mount(app)
    with TestClient(app) as client:
        assert client.get("/widget/assets/" + name).status_code == 503
        assert client.get("/widget/manifest.json").status_code == 503
        assert client.get("/widget/assets/manifest.json").status_code == 404


def test_asset_verification_is_cached(monkeypatch, tmp_path):
    """Second read of the same bundle must not re-hash or re-gzip."""
    hosting._verified_asset.cache_clear()
    body = b"console.log('rig-widget-cache-test');"
    digest = hashlib.sha256(body).hexdigest()
    name = f"tervory-rig.{digest}.umd.js"
    path = tmp_path / name
    path.write_bytes(body)
    monkeypatch.setenv("RIG_WIDGET_DIR", str(tmp_path))

    calls = {"sha": 0, "gzip": 0}
    real_sha = hashlib.sha256
    real_gzip = gzip.compress

    def counting_sha(data=b"", *, usedforsecurity=True):
        # hashlib.sha256(data) returns a HASH; we wrap the constructor.
        h = real_sha(data)
        if data:
            calls["sha"] += 1
        return h

    class ShaFactory:
        def __call__(self, data=b"", *, usedforsecurity=True):
            obj = real_sha(data)
            if data:
                calls["sha"] += 1
            return obj

    def counting_gzip(data, **kwargs):
        calls["gzip"] += 1
        return real_gzip(data, **kwargs)

    monkeypatch.setattr(hosting.hashlib, "sha256", ShaFactory())
    monkeypatch.setattr(hosting.gzip, "compress", counting_gzip)

    first = hosting.asset(name)
    second = hosting.asset(name)
    assert first == second == body
    assert calls["sha"] == 1
    assert calls["gzip"] == 1
