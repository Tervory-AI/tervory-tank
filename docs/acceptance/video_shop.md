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

Browser behavior at 390px and 1440px is covered by:

```sh
node tests/video_shop_overlay.test.cjs
```

Requires an installed Playwright package and Chromium. `PLAYWRIGHT_MODULE` and
`CHROMIUM_PATH` may select existing installations. The browser test mocks HTTP,
plays the sample MP4, seeks into and out of the product moment, opens detail,
adds once, checks product text is rendered safely, and destroys the embed.

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
MP4 for the embed. Unsupported codecs are rejected by FFmpeg or fail playback.
Back up the SQLite review database and its tenant media directories together.
Run one room replica per durable directory; scale processing via the existing
job system before increasing concurrent ingest demand.

## Design and live acceptance

`docs/figma/video-shop/REGISTER.md` was absent in the implementation checkout and
on the fetched main branch. Overlay labels are replaceable through embed options;
admin screens can consume the saved upload/review contracts as frames land.
No unrelated Figma register or guessed product name was introduced.

After review and deployment, the founder/Claude can use an approved store fixture
and existing cart configuration to repeat upload → review → play → add → store
checkout. A real store/cart check and final Figma screen comparison remain live
acceptance; offline evidence does not assert that a production order was created.
