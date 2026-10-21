# MARKET-DOCS-1: feed Market Lab industry and history documents

> Written 21 Oct 2026. Founder: "I have NO way to feed Market Lab with industry and history documents to improve its memory."

**Files you may change:**
- `agents/market_lab/` (ingest, memory);
- `workspace/app/market-lab/` (the upload screen only);
- `tank/` (route registration only);
- tests.

Uses the storage from BUCKET-1.

1. **Upload:** on Market Lab's page (and in the window: "add these to Market Lab"), drop files: PDF, Word, Excel, CSV, web links. A plain list shows each document with its status: reading, learned, failed with the reason.
2. **Store:** the original goes into Market Lab's own bucket (`tervory-market-lab`).
3. **Learn:** the text is read, split into passages and written to **Market Lab's own memory**. Every passage keeps its source: file, page, date. Tables become structured series where possible, with unit and currency, and pass through the bad-batch guard (#207) before they are used.
4. **Use:** Market Lab recalls these passages in research and cites them (file and page) in its answers and receipts.
5. **Forget:** removing a document removes its passages and series.

## Done when
CI green. Tests:
- an uploaded PDF becomes passages with sources;
- a research answer cites the uploaded file and page;
- a table becomes a series that goes through the guard;
- removing the file removes its passages.

Screenshots at 375px and 1440px.
