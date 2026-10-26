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

## Founder must decide: revised public-page policy

The founder's update on 26 October defines a public page as one a person can open
without signing in or paying, with robots.txt advisory. It requires one truthful
Tervory user agent, host rate limiting, a site stop on CAPTCHA/403/block, and
continuation only through the client's own connection after the client acts.
This supersedes the original brief's robots policy. **That revised workflow is not
implemented by the HTML fix or demonstrated by these fixture screenshots.**

The unchanged file restriction permits `agents/_brain/browser.py` edits only to
the HTML return path. The remaining dependencies are outside that permitted path:

- The shared browser enforces `require_allowed` before navigation and on routed
  requests, including PDF reads; its policy lives in `agents/_brain/robots.py`.
  Removing only the watch-level robots check would still leave public reads blocked.
- The browser uses `TervoryBase/1.0`; Tiger's robots request uses
  `TervoryTiger/0.1`. A single identity needs the browser request setup changed.
- In `watch.py`, `client_connection` is only the source label on a `portal_item`
  receipt. The existing human handoff controls a held server browser session;
  it does not run through the client's own network connection. There is no client
  connection transport here to wire into a persistent per-site stop/resume flow.

The browser/access owner must supply that scoped public policy and genuine client
connection contract, or the lane must be expanded to implement them. No robot
policy bypass, automatic CAPTCHA action, anonymous retry around a block, or
stand-in client connection has been added. The existing implementation remains
unchanged pending that dependency; this draft must not be treated as completing
the revised public-page policy.
