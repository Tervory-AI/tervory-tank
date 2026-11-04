# L1 equivalence evidence

`golden.json` contains all 578 full calls observed while running the 171 tests in
`tests/test_rig_cn_archon.py` and `tests/test_rig_archon_search_memory.py` on the
unchanged `origin/main` snapshot `a870ade14bce0b15fb1fb88fbf80d868029f253f`.
The baseline was executed in a detached local checkout, with external sockets
and DNS blocked. It was repeated independently; both baseline files matched
byte for byte. The migrated branch produced the same bytes on its first run.

`golden_plugin.py` records complete search/detail responses, reservation payloads,
errors, stored quote payloads and handoff letters. Request UUIDs are deterministic
per test in both executions. Public outputs and letter text are not normalized;
only supplemental stored-row `created_at` metadata is omitted. Existing fixture
names, IDs, contacts, prices and historical demo flags are retained verbatim in
this offline evidence, never introduced into runtime.

`test_complete_search_detail_and_reservation_golden` reruns those same test files
with the plugin in an isolated subprocess and compares canonical JSON bytes.
The surrounding L1 tests cover a literal-schema/fixture equality check, real
Postgres migration preservation/idempotence, an independent lamp/shade store,
plain ranking without vocabulary, fixed validation limits, regex and template
rejection, and logging with no vocabulary contents.

Runtime source imports `guided_search.py`; `cn.py` was moved with `git mv` and is
gone. `vocabulary.py` supplies only validation and context isolation, with no
catalogue defaults. The migration runs through existing startup schema handling
only after the founder merges and deploys. No SQL was run on a live database.

Gate 2 checkpoint: `ba52fa80b3b1e1cfe451c5490e644438b651db76`.
L1 does not edit cart files, `fulfilment.py` or `quotes/service.py`.
Final verification, exact SQL and per-file lines are recorded in PR #628.
