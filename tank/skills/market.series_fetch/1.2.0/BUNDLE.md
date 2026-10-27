# Candidate runtime bundle

`market.series_fetch` 1.2.0 copies 1.1.0 into a new version. Versions 1.0.0,
1.1.0 and 1.1.1 are untouched. The skill entry point, pure series logic and
three synthetic listing/geography fixtures are unchanged from 1.1.0.

Tank ships `skills/`, without repository `agents/` or `tests/`. All 21 Python/SQL
files in this version's `feeds/` byte-match `agents/market_lab/feeds/`: the prior
20-file dependency closure plus `published.py`, now imported by live fetches.
The CLI, Postgres collector and page-only presentation helpers are not runtime
dependencies of this skill and are not bundled. No new provider, key, installed
dependency, production schema or Dockerfile change is needed.

`evals/cases.jsonl` retains the original three cases and adds county and Texas
listing counts, empty-input refusal, missing-engine refusal and unknown-adapter
refusal. The real Skala runner must pass all eight cases with no HTTP/model calls.

`evals/test_feeds.py` adds eight offline cases for every changed bundled module:

| Module | Regression evidence |
| --- | --- |
| `geo.py` | Both stored county-title patterns and complete state-name matching |
| `engines/ffl/sources.py` | All 14 readable publisher links; retained raw API URL; commodity metadata |
| `adapters.py` | Saved commodity rows retain copper/cotton names and published units |
| `fetch.py` | Published commodity/freight values, dates and units; pagination loop refusal |
| `published.py` (new dependency) | Published downloads, headings and date parsing; other hosts not fetched |
| `live.py` | Import/export fields; one request to a blocked host, then refusal |
| `runner.py` | Blocked result persisted with zero stored rows across repeated runs |

From the repository root, after installing `tank/requirements.txt` and
`tank/requirements-dev.txt`:

```bash
PYTHONPATH=tank python -m pytest -q tests/test_candidate_eval_runtime.py
```

This includes byte-for-byte bundle/fixture comparison, the unchanged legacy
evals, and the newest version in its own fresh interpreter. Each interpreter
receives only Tank's top-level modules and skills. Sockets are blocked; saved
publisher responses replace external providers only. Assertions check every
imported `feeds` module came from the selected package, preventing a cached
legacy bundle or repository import from concealing missing dependencies.
