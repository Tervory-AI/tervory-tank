"""One real refresh per new feed into a disposable memory ledger, then cite it.

Run with PYTHONPATH=tank python tests/market_lab_feeds/prove_live.py.
No server, model, production database, credential or fixture is used.
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agents/market_lab"))
from core.evidence import answer, document
from core.jobs import perform_refresh
from core.ledger import MemoryLedger
from feeds.collect import EvidenceClient

OWNER = "00000000-0000-0000-0000-000000000001"
OTHER = "00000000-0000-0000-0000-000000000002"


async def main():
    # A full refresh also offers the existing FRED live reader. Keep this proof
    # restricted to the two new no-key APIs without examining setting values.
    if "FRED_API_KEY" in os.environ:
        raise RuntimeError("Run this isolated proof without the FRED_API_KEY setting")
    ledger = MemoryLedger()
    client = EvidenceClient(allowed_domains={"sec.gov", "data.ny.gov"})
    reports = []
    for source, question in [
        ("sec_edgar", "Recent SEC filings from Ruger"),
        ("port_nynj", "New York container imports in 2015"),
    ]:
        result = await perform_refresh(tenant_id=OWNER, engine="ffl", source=source,
                                       ledger=ledger, live=True, client=client)
        check = result["feeds"][0]
        report = {"source": source, "rows": check["rows"], "note": check["note"],
                  "checked_at": check["checked_at"]}
        reports.append(report)
        if check["note"] or not check["rows"]:
            print(json.dumps({"feeds": reports, "passed": False}, indent=2))
            raise SystemExit(1)
        saved = await document(ledger, OWNER, check["document_id"])
        response = await answer(ledger, OWNER, question)
        assert response["facts"], question
        assert await document(ledger, OTHER, check["document_id"]) is None
        assert not (await answer(ledger, OTHER, question))["facts"]
        fact = response["facts"][0]
        kind, index = fact["href"].split("#")[1].split("-")
        row = saved["events" if kind == "event" else "points"][int(index)]
        assert row["fetched_at"]
        report.update(downloads=saved["downloads"], question=question, answer=fact,
                      source_link=row.get("url", saved["url"]), row_fetched_at=row["fetched_at"],
                      first_period=min(r["date"] for r in saved["events"] + saved["points"]),
                      last_period=max(r["date"] for r in saved["events"] + saved["points"]),
                      tenant_isolation=True)
    print(json.dumps({"finished_at": datetime.now(timezone.utc).isoformat(),
                      "storage": "disposable MemoryLedger", "feeds": reports, "passed": True}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
