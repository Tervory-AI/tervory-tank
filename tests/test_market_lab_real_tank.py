"""Real Tank startup/auth/client, real room routes, real local Postgres.

No Tank module, method, dependency or HTTP client is replaced. The subprocess
imports tank/main.py exactly as its deployed uvicorn entry point does.
"""
import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

import asyncpg
import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents/market_lab"))
from fixture_proof.server import TENANT, database_url, free_port, services
from fixture_proof.boot_tank import verify_imported_cases


def test_real_tank_routes_to_real_room_and_postgres(tmp_path):
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("requires a local *_test Postgres database")
    from urllib.parse import urlsplit
    target = urlsplit(os.environ["DATABASE_URL"])
    if target.hostname not in {"127.0.0.1", "localhost"} or not target.path.endswith("_test"):
        pytest.skip("requires an explicitly selected local test database")
    database_url()
    other = str(uuid.uuid4())
    with (tmp_path / "services.log").open("w+") as log:
        try:
            with services(free_port(), log=log, history=True) as env, httpx.Client(base_url=env["TANK_URL"], trust_env=False, timeout=40) as client:
                def request(operation, *, tenant=TENANT, **payload):
                    return client.post(f"/v1/market-lab/{operation}", json={"tenant_id": tenant, **payload}, headers={"x-tank-key": env["TANK_API_KEY"]})

                assert client.get("/health").json()["ok"] is True  # Tank's actual pool.
                asyncio.run(verify_imported_cases())  # The full Gold lifespan completed.
                assert client.post("/v1/market-lab/overview", json={"tenant_id": TENANT}).status_code == 401
                assert client.post("/v1/market-lab/overview", json={"tenant_id": TENANT}, headers={"x-tank-key": env["TANK_KEY_MARKET_LAB"]}).status_code == 403
                assert request("unknown").status_code == 404
                assert request("overview", fixtures=True).status_code == 422
                response = request("overview")
                assert response.status_code == 200, response.text
                assert response.json()["on_count"] == 14
                assert response.headers["cache-control"] == "private, no-store"
                assert request("overview", tenant=other).json()["on_count"] == 0
                listings = request("ask", question="How many listings are there in Texas?")
                assert listings.status_code == 200 and listings.json()["facts"]
                brief = request("ask", question="What are the latest population figures for California?")
                assert brief.status_code == 200 and brief.json()["facts"]
                assert request("ask", question=" ").status_code == 422
                unrelated = json.loads((ROOT / "tests/fixtures/market_lab_questions.json").read_text())["unrelated"]
                for question in unrelated:
                    response = request("ask", question=question)
                    assert response.status_code == 200
                    assert response.json() == {"content": "No stored data matches this question", "facts": [], "sources": []}, question
                assert request("ask", tenant=other, question="population").json()["facts"] == []
                for fact in brief.json()["facts"]:
                    ident = fact["href"].split("/")[-1].split("?")[0]
                    row = int(fact["href"].split("#point-")[1])
                    source = request("document", document_id=ident, row=row)
                    assert source.status_code == 200
                    point = next(point for point in source.json()["points"] if point["index"] == row)
                    assert point["display_title"] in fact["text"]
                    assert point["date_label"] in fact["text"]
                    assert point["value"] in fact["text"].replace(",", "")
                    assert request("document", tenant=other, document_id=ident).status_code == 404
                port = request("ask", question="What is the latest container volume?").json()
                assert len(port["facts"]) == 1 and "14,474" in port["facts"][0]["text"]
                ident = port["facts"][0]["href"].split("/")[-1].split("?")[0]
                first = request("document", document_id=ident).json()
                second = request("document", document_id=ident, offset=50).json()
                assert first["page_size"] == 50 and first["point_count"] == 67
                assert len(first["points"]) == 50 and len(second["points"]) == 17
                assert first["points"][0]["display_value"] == "14,474"
                assert first["points"][0]["date"] == "2026-01-01"
                assert second["points"][-1]["date"] == "1960-01-01"
                assert request("document", document_id=ident, offset=0).json() == first
                assert request("document", document_id=ident, row=0).json() == second
                assert request("document", tenant=other, document_id=ident, row=0).status_code == 404
                for _ in range(2):
                    refreshed = request("refresh", tenant=other)
                    assert refreshed.status_code == 200 and refreshed.json() == {"status": "queued"}
                assert request("overview", tenant=other).json()["refresh_status"] == "queued"

                async def check_queue():
                    conn = await asyncpg.connect(database_url())
                    try:
                        rows = await conn.fetch("SELECT status, input FROM agent_market_lab.jobs WHERE tenant_id=$1 AND kind='refresh'", uuid.UUID(other))
                        assert len(rows) == 1  # Repeated requests deduplicate for this tenant.
                        assert rows[0]["status"] == "queued"
                        assert json.loads(rows[0]["input"]) == {"engine": "ffl"}
                    finally:
                        await conn.close()
                asyncio.run(check_queue())
        except Exception:
            log.seek(0)
            # Service logs have access logs disabled; generated keys never printed.
            print(log.read())
            raise
