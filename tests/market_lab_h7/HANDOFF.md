# Market Lab H7

The existing ML3 briefs read accepts an optional report_id; detail returns saved
text, citations, original signal confidence, verified stored-passage links and
recorded delivery history. Tenant checks apply to reports and document rows.
Deleted/foreign/unavailable passages never get an Open source link. Delivery
history starts with this deployment; historic sends are not reconstructed.
Calibration adds measured cohort means/hits/misses while retaining kind, feed,
frozen horizon and bins. No extra route, model call, paid service or setting.

Workspace routes: /market-lab/briefs/<report-id> and /market-lab/calibration.
The supporting /market-lab/briefs list supplies real report IDs. Existing Tank
read transport and Workspace tenant authentication are reused server-side.

Frames: wave-5 branch codex/figma-w5, file ZnphBOJU6657tohGLD3IzS;
brief desktop 566:395 / mobile 566:2140; calibration desktop 567:941 /
mobile 567:1726. These remain Proposed in the register, not newly approved.
Native frame assets are in workspace/public/market-lab/h7. Charts plot returned
bins only; periods remain separate and missing metrics are em dashes.
Dedicated brief confidence/history sections have no frame slots and remain
structured-read data pending those sections. No new visible labels invented.

Acceptance R44–R47 extends the existing sheet to 47 rows. Offline SQL/ASGI
fixtures test the real tenant reads and receipts. Node fixtures test server
loaders and production view rendering. Browser fixtures use actual components
at 1440/375 for ready/loading/empty/error, source navigation, cohort selection
and mobile menu; only the fixture replaces Clerk's organization switcher.
These are local fixture proofs, not founder/production/deployed acceptance.

Validated: SQL/ASGI H7 tests 2 passed; Node loader/view test 1 passed;
TypeScript noEmit passed; browser final axis-alignment run 1 passed (118.40s).
Four populated screenshots and proof.json in evidence/ are local fixture
captures. The browser covered all 16 page/state/width combinations; these four
files are the retained populated views. Axis midpoint/end labels are asserted
against their true grid positions, and empirical dots remain 8px native assets.
Mandatory precheck and hosted CI validation remain in progress. Local Semgrep timed out; the explicitly
permitted PRECHECK_SKIP_SEMGREP=1 is used for subsequent prechecks; CI must run
Semgrep. No production setting, mail recipient or live data was changed.
Deploy the Market Lab room, Tank and Workspace together for the additive
history table and detail contract. Founder approval, real saved brief links,
real outcomes and final CI confirmation remain required after deployment.

## Shared-box validation blocker

The mandatory precheck has not passed; no push or hosted CI run is claimed.
Lint, Gitleaks and OSV pass. Semgrep timed out and is skipped only under the
founder's explicit allowance. Broad runs were interrupted by SIGTERM (one
reached 87% without an assertion failure); another stopped at the existing
room_brains seal fixture's 30-second subprocess timeout. The same case failed
alone. Host load readings were approximately 149–165. No test deadline or
assertion was relaxed, and an unsuccessful fixture-startup experiment was
reverted. A local runner-only hook stops default-stop pgserver instances in a
finished function's own tmp_path after fixture teardown, avoiding retained
H7 database processes. This changes neither source nor tests and never touches
another checkout. Full precheck, per-gate pushes and final hosted CI remain
outstanding until validation can complete.


Final focused acceptance attempt: R44–R46 passed (3 passed); R47 failed before
page assertions because the isolated Next fixture stayed at `Compiling /`
through its existing startup deadline. A standalone retry with cpus=1,
RAYON_NUM_THREADS=1 and UV_THREADPOOL_SIZE=2 failed at the same startup stage
(403.20s). Those fixture-only resource limits are retained to avoid amplifying
shared-host load; no production setting changed. The earlier direct browser
run passed all page assertions (118.40s), and its screenshots are retained.
This is not a claim that all 47 acceptance tests currently pass. Final exact
CI lint and TypeScript noEmit, including pagination, passed. No deadline or
assertion was relaxed. No push occurred because precheck has not passed; final
hosted CI and deployed founder acceptance remain outstanding.
