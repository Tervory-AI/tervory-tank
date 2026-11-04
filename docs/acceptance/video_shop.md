# video-shop acceptance

Internal name only; the founder supplies the product name. No model provider or
paid service is added. Each processing result contains a code receipt, source
SHA-256, vision method, sampled-frame count and reference-image diagnostics.

## Automated evidence

Run with the repository's Python test dependencies and FFmpeg on PATH:

```sh
TMPDIR="$PWD/.tmp" python3 -m pytest -q tests/test_video_shop.py tests/test_video_shop_overlay.py tests/acceptance/test_video_shop.py tests/test_rig_cart.py
```

`tests/acceptance/test_video_shop.py` loads the sample video, catalogue CSV and
catalogue photo in `tests/fixtures/video_shop`. It uses the real Rig catalogue
import, search, authentication, product, cart and commerce adapter code. Only
store HTTP is simulated; no live catalogue, order, payment or model call occurs.

| Check | Evidence |
| --- | --- |
| Upload video and match against this store's catalogue | POST admin upload; frame and transcript evidence at 0 seconds, frame evidence at 5 seconds |
| Store review before publication | Shopper gets 404 for draft; admin edits moment to 1–7 seconds and approves |
| Durable edits and conflict handling | Reopened repository retains edits; stale revision fails |
| Tenant and origin isolation | Other store key gets 404; unapproved origin gets 403; missing key gets 401 |
| Current catalogue | Inactive products disappear from public timeline |
| Product detail and add | Overlay uses Rig product route, obtains Rig session, adds existing SKU |
| Store-owned checkout | Real Rig commerce adapter creates product 1, quantity 1, total USD 10.00 in the offline WooCommerce store and returns that store's checkout URL |
| Guarded links | HTTPS only, no credentials or custom ports, all DNS addresses public, pinned IP connection, no redirects, bounded download |
| No model spend | Saved receipt has `route=code` and `model_calls=0` |

Browser behavior at 375px and 1440px is covered by:

```sh
node tests/video_shop_overlay.test.cjs
```

Requires an installed Playwright package and Chromium. `PLAYWRIGHT_MODULE` and
`CHROMIUM_PATH` may select existing installations. The browser test mocks HTTP,
plays the sample MP4, seeks into and out of the product moment, opens detail,
adds once, checks pause/list/jump and disabled store-cart behavior, checks product text is rendered safely, and destroys the embed.

## Hosted CI evidence

The first final-head full run, [41867395324](https://github.com/Tervory-AI/tervory-tank/actions/runs/41867395324),
passed lint, Workspace, savings-page, command acceptance and seven Python shards.
It exposed missing FFmpeg/ffprobe in the hosted Python runners; the workflow now
provisions those tools rather than skipping the video tests. Local validation of
that repair and the transport checks passed 100 tests. Download transport tests
assert pinned TCP addresses, original-host TLS certificate verification, original
HTTP Host and refusal of redirects. No scanner suppression was added.

That manual dispatch intentionally runs a full repository security audit, unlike
the PR's baseline comparison. It also reported existing history/fixture Gitleaks
findings, existing dependency advisories and unrelated Semgrep findings. The
branch changes no dependency pins. The original transport's HTTPSConnection audit
notice was removed by using the existing httpcore dependency's verified TLS
transport with a pinned network backend. Security policy and allowlists remain
unchanged. Normal PR security validation remains required when Claude opens the
single PR. An unchanged Rig landing screenshot equality test also failed once in
that full run (`landing-tervory-375`); no Rig landing files are changed here.

## Runtime composition and limits

`agents/video_shop/Dockerfile`, built with `agents/` as context, provides FFmpeg
and the `video_shop.video_asgi:app` entry point. It composes the existing Rig host,
retains its schema, tenant authentication and cart configuration, and stores video
reviews and media in `DATA_DIR/video-shop` on the persistent volume. Existing Rig
DB, Tank and commerce configuration is reused. No live deployment is performed.
Alternatively mount `video_room.mount(rig_app, durable_path)` in an existing host
that has FFmpeg. This does not change existing service or regional configuration.

Processing is bounded: 32 MiB upload/download, ten minutes, five-second sample
windows, 120 frames and 100 catalogue images per video. Catalogue images are
fetched automatically over guarded HTTPS; inaccessible images are recorded and
explicit reference uploads may replace them. Image comparison is conservative
RGB frame distance, useful for close visual matches. It is not a general object
recognizer: different angles, occlusion and small products may need manual edits.
Transcript segments are supplied with the video; automatic speech recognition
is not enabled. No Tank model fallback is enabled. Any future fallback must use
Tank's existing routing and preserve its receipts.

Cart availability and checkout platforms follow Rig's existing store settings;
the room does not enable cart mode for a live store. Media must be browser-playable
MP4 or WebM for the embed. Unsupported codecs are rejected by FFmpeg or fail playback.
Back up the SQLite review database and its tenant media directories together.
Run one room replica per durable directory; scale processing via the existing
job system before increasing concurrent ingest demand.

## Design and live acceptance

The Proposed register landed in the parallel `/workspace/codex-figma-video`
checkout at design commit `be87b92e` on branch `codex/figma-window-agent` while
this implementation was underway. The embed now uses its functional headings,
View product, Add to cart, store-cart acknowledgement/error, Keep watching and
payment wording. Product occurrences list every approved time range and jump to
the first. Pausing preserves the active moment. Open store cart is disabled
unless the host supplies an authorized HTTPS `storeCartUrl`; `checkout()` remains
available for the host to use Rig's existing checkout integration.

Upload/link processing now requires `rights_confirmed: true`; the permission
confirmation and server timestamp are saved with the video. The backend rejects
processing without it. Existing start/end/product/approved fields support the
register's Keep match / Remove match / Save review flow. The room does not copy
or modify the parallel design branch's files. The embed adapts the matched-player
component, tokens and copy; the full 48 proposed screens remain design work.

After review and deployment, the founder/Claude can use an approved store fixture
and existing cart configuration to repeat upload → review → play → add → store
checkout. A real store/cart check and final Figma screen comparison remain live
acceptance; offline evidence does not assert that a production order was created.
