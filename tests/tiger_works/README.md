# Tiger local proof

These screenshots are **local, fixture page** proof, as requested by the founder.
They do not claim a Clerk login, a live store check, or a deployed service.

The harness copies Workspace to a temporary directory and substitutes Clerk
there only. The dummy publishable and secret keys match `.github/workflows/ci.yml`.
The repository's authentication and middleware are unchanged. The real add-watch
server action calls the real tenant-scoped Tank proxy routes and Tiger handlers.
The test uses `MemoryStore` and invokes `run_check` in place of a scheduled job.
Chromium renders the saved HTML with network requests blocked; production browser
serialization, deterministic extraction, observation storage and alert logic run.
No model, paid service or live account is used.

The source is the existing saved Adafruit Raspberry Pi 4 product page at
`tests/tiger_alert_page/fixtures/live/www-adafruit-com--product-4296.html`.
Its original reading is USD 120.00, in stock. The harness changes the saved price
to USD 115.00 for the second and third checks. That change is a test mutation,
not a claim about the current price on Adafruit. Three readings create one alert.

| Step | Evidence |
| --- | --- |
| Empty watch list | [01-empty.png](proof/01-empty.png) |
| Form submitted; price enabled, stock disabled | [02-watch-added.png](proof/02-watch-added.png) |
| First reading: USD 120.00, in stock | [03-first-reading.png](proof/03-first-reading.png) |
| History: 120.00 → 115.00 → 115.00 | [04-history.png](proof/04-history.png) |
| One price alert: 120.00 → 115.00 | [05-alert.png](proof/05-alert.png) |
| Saved observations and alert | [observations.json](proof/observations.json) |

With Python dependencies from `tank/requirements.txt` and
`tank/requirements-dev.txt`, Node 22, Workspace npm dependencies and Chromium:

```sh
PYTHONPATH=tank READ1_CHROMIUM_EXECUTABLE=/usr/bin/chromium python -m pytest -q tests/test_tiger_works.py
PYTHONPATH=tank:tests READ1_CHROMIUM_EXECUTABLE=/usr/bin/chromium python tests/tiger_works/local_proof.py
```

The harness replaces its own screenshots and observations on each run. Set
`TIGER_PROOF_DIR` to an external output directory to leave committed proof intact.
It starts localhost services on free ports and removes the temporary Workspace
on exit. `workspace.log` is a local diagnostic file, not part of the proof bundle.

The founder deploys the branch when ready. Claude takes the signed-in live proof
in the founder's browser; this local harness does not perform that step.

## Independent review

`test_two_tenants_cannot_read_or_remove_each_others_saved_page_job` exercises the
actual authenticated Tank routes and Tiger handlers with two tenants watching the
same URL. Each tenant gets different fixture prices and its own alert. The test
checks watch/history/alert reads, cross-tenant deletion, conflicting body/query
tenant IDs, and rejection without the Workspace key. `MemoryStore` replaces only
the database; the deterministic reader and route implementations are real.

## Public-page policy

The founder explicitly extended the lane on 26 October to implement these three
changes in the shared browser program, run in each room's own container:

- Public HTML and PDF reads do not request or enforce robots.txt. URL/DNS safety,
  access controls and existing per-host throttling remain in place. Removing the
  robots gate does not permit signing in or opening a paywall through public reads.
- Browser contexts and direct document requests use
  `Tervory/1.0 (+https://tervory.com)`.
- CAPTCHA, HTTP 403 and other refusals stop automated requests to that host for
  the run. The stop is keyed by room, tenant and task ID, covers redirects and
  queued/subresource requests, and returns `blocked` with the URL. Tiger stores a
  blocked observation without a price or alert. The browser never ticks a CAPTCHA.

`tests/test_tiger_public_policy.py` covers these changes, including isolation of
stops between rooms, tenants and tasks, private-target rejection, and the absence
of raw HTML in ordinary/model results. An omitted task ID shares the room/tenant's
unscoped run. Stop state lives in that browser process; no persistent site-wide
pause or client-session transport is introduced. Existing `ACCESS_ROOM` policy and
client handoff code are retained.

## Founder must decide: client's own session

The founder explicitly excluded the client's-own-session path from this brief.
`client_connection` remains the source label on an existing `portal_item` receipt
in `watch.py`. Implementing a genuine client-network/session transport is a
separate decision; this change does not claim or simulate that path. Claude's
signed-in live proof remains a step after the founder deploys the branch.
