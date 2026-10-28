"""Offline Docassemble API contract using real Mako and DOCX template rendering.

No daemon, database, credentials or network. All API credential strings are
setting names, not secrets. The legacy oracle is never imported by the stub.
"""
from __future__ import annotations

import importlib.util
from io import BytesIO
import json
from pathlib import Path
import sys
from unittest.mock import patch

import httpx
from docxtpl import DocxTemplate

from agents.zenas.core import drafting, service
from agents.zenas.core.docassemble import DocassembleClient

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "agents/zenas/docassemble/package"
spec = importlib.util.spec_from_file_location("zenas_docassemble_test_package", PACKAGE / "__init__.py",
                                             submodule_search_locations=[str(PACKAGE)])
package = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = package
spec.loader.exec_module(package)
sys.modules[spec.name + ".legacy"] = drafting
assembly = importlib.import_module(spec.name + ".assembly")


class API:
    def __init__(self, region):
        self.region = region
        self.requests = []
        self.sessions = {}
        self.files = {}

    def handle(self, request):
        self.requests.append(request)
        assert request.url.host == "docassemble"
        assert request.headers["X-API-Key"] == "DOCASSEMBLE_API_KEY"
        assert "DOCASSEMBLE_API_KEY" not in str(request.url)
        assert "DOCASSEMBLE_SESSION_SECRET" not in str(request.url)
        if request.method == "GET" and request.url.path == "/api/session/new":
            interview = request.url.params["i"]
            session = "offline-session-" + str(len(self.sessions) + 1)
            self.sessions[session] = interview
            return httpx.Response(200, json={"i": interview, "session": session, "encrypted": True,
                                             "secret": "DOCASSEMBLE_SESSION_SECRET"})
        if request.method == "POST" and request.url.path == "/api/session":
            data = json.loads(request.content)
            assert data["raw"] == 0
            assert data["i"] == self.sessions[data["session"]]
            assert data["secret"] == "DOCASSEMBLE_SESSION_SECRET"
            assert set(data["variables"]) == {"request"}
            payload = data["variables"]["request"]
            template = data["i"].rsplit("/", 1)[1].removesuffix(".yml")
            jurisdiction = "za" if self.region == "za" else "us"
            with patch.dict("os.environ", {"TANK_REGION": self.region}):
                if payload["mode"] == "assemble":
                    result = assembly.prepare(payload, jurisdiction, template)
                else:
                    result = assembly.finish(payload, jurisdiction, template)
                    document = DocxTemplate(PACKAGE / "data/templates/document.docx")
                    document.render({"result": result}, autoescape=True)
                    output = BytesIO()
                    document.save(output)
                    number = len(self.files) + 1
                    self.files[number] = output.getvalue()
                    result = {"text": result["text"], "file_number": number}
            return httpx.Response(200, json=result)
        if request.method == "GET" and request.url.path.startswith("/api/file/"):
            assert request.url.params["extension"] == "docx"
            number = int(request.url.path.rsplit("/", 1)[1])
            return httpx.Response(200, content=self.files[number],
                                  headers={"Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"})
        raise AssertionError("Unexpected Docassemble API operation")


def install(monkeypatch):
    monkeypatch.setenv("DOCASSEMBLE_API_KEY", "DOCASSEMBLE_API_KEY")
    monkeypatch.setenv("DOCASSEMBLE_URL", "http://docassemble")
    apis = []

    def factory(region):
        api = API(region)
        apis.append(api)
        return DocassembleClient(region, transport=httpx.MockTransport(api.handle))

    monkeypatch.setattr(service, "DocassembleClient", factory)
    return apis
