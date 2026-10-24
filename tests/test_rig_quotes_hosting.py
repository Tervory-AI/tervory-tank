"""The public bundle is immutable, verified and contains no sample catalogue."""

import gzip
import hashlib
import json
from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents" / "rig"))
from rigbox.quotes.hosting import mount  # noqa: E402


def test_packaged_bundle_and_configured_test_page(monkeypatch):
    monkeypatch.delenv("RIG_WIDGET_DIR", raising=False)
    monkeypatch.delenv("RIG_WIDGET_PUBLISHABLE_KEY", raising=False)
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
        assert page.headers["Content-Security-Policy"] == "frame-ancestors 'none'"
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
    name = "tervory-rig." + "0" * 64 + ".umd.js"
    (tmp_path / name).write_text("altered artifact")
    (tmp_path / "manifest.json").write_text(json.dumps({"file": name}))
    app = FastAPI()
    mount(app)
    with TestClient(app) as client:
        assert client.get("/widget/assets/" + name).status_code == 503
        assert client.get("/widget/manifest.json").status_code == 503
        assert client.get("/widget/assets/manifest.json").status_code == 404
