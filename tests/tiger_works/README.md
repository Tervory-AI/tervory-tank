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
