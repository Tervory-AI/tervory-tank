# video-shop acceptance

Internal name only; the founder supplies the product name. No model provider or
paid service is added. Each draft contains a local CPU receipt, weight checksums, the generated
transcript, source SHA-256, frame count and catalogue-image diagnostics.

## Automated evidence

Run with the repository's Python test dependencies and FFmpeg on PATH:

```sh
TMPDIR="$PWD/.tmp" python3 -m pytest -q tests/test_video_shop.py tests/test_video_shop_overlay.py tests/acceptance/test_video_shop.py tests/test_rig_cart.py
```

`tests/acceptance/test_video_shop.py` loads the sample video, catalogue CSV and
catalogue photo in `tests/fixtures/video_shop`. It uses the real Rig catalogue
import, search, authentication, product, cart and commerce adapter code. The `stub` cases inject explicit analysis doubles for fast API/storage tests.
The `cpu` cases run the real pinned speech and embedding engines, with only store
HTTP simulated. No live catalogue, order, payment or provider call occurs.

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
| No provider spend | Saved receipt has `route=local_cpu`, `device=cpu`, `provider_calls=0` and exact weight checksums |
| Automatic speech | Upload contains no transcript; locally recognized “red cup” appears in timestamped private draft segments |
| Image embeddings | Real OpenCLIP cosine match exceeds the recorded threshold; second sample matches without speech |
| Offline execution | CPU cases run with sockets and external DNS disabled, using staged checksummed assets |

Browser behavior at 375px and 1440px is covered by:

```sh
node tests/video_shop_overlay.test.cjs
```

Requires an installed Playwright package and Chromium. `PLAYWRIGHT_MODULE` and
`CHROMIUM_PATH` may select existing installations. The browser test mocks HTTP,
plays the sample MP4, seeks into and out of the product moment, opens detail,
adds once, checks pause/list/jump and disabled store-cart behavior, checks product text is rendered safely, and destroys the embed.

## Real CPU acceptance

The dedicated `.github/workflows/video-shop.yml` installs the hashed CPU runtime,
stages public immutable model assets, then disables sockets and external DNS for
the tests. Run the same checks locally on a Linux x86_64 Python 3.12 build host:

```sh
mkdir -p "$PWD/.tmp"
export TMPDIR="$PWD/.tmp"
python3 -m venv .tmp/video-shop-venv
.tmp/video-shop-venv/bin/python -m pip install --require-hashes -r agents/video_shop/requirements.lock -r agents/video_shop/requirements-test.lock
.tmp/video-shop-venv/bin/python agents/video_shop/prepare_models.py .tmp/models
VIDEO_SHOP_TEST_MODELS="$PWD/.tmp/models" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 OMP_NUM_THREADS=1 .tmp/video-shop-venv/bin/python -m pytest -q tests/test_video_shop.py tests/test_video_shop_models.py tests/test_video_shop_overlay.py tests/acceptance/test_video_shop.py --disable-socket --allow-unix-socket
```

FFmpeg and curl must already be installed on that build host. Weights are staged
once (about 680 MB); network is unnecessary during inference. The ordinary suite
runs explicit analysis doubles and skips the real CPU parameters unless
`VIDEO_SHOP_TEST_MODELS` points to staged assets. The dedicated CI job sets this
value, so its real cases cannot skip. No founder laptop installation is needed.

PR #693's differential security check passed on its initial head; the unrelated
whole-repository manual audit is not the PR gate. The room's Docker base and all
Python installs now use a digest and hashed locks for the install-pins check.
No scanner suppression or security policy change is added.

## Runtime composition and limits

`agents/video_shop/Dockerfile`, built with `agents/` as context, provides FFmpeg, pinned local CPU engines and baked-in verified weights,
and the `video_shop.video_asgi:app` entry point. It composes the existing Rig host,
retains its schema, tenant authentication and cart configuration, and stores video
reviews and media in `DATA_DIR/video-shop` on the persistent volume. Existing Rig
DB, Tank and commerce configuration is reused. No live deployment is performed.
Alternatively mount `video_room.mount(rig_app, durable_path)` in an existing host
that has FFmpeg. This does not change existing service or regional configuration.

Processing is bounded: 32 MiB upload/download, ten minutes, five-second sample
windows, 120 frames and 100 catalogue images per video. Catalogue images are
fetched automatically over guarded HTTPS; inaccessible images are recorded and
explicit reference uploads may replace them. Image matching uses OpenCLIP
ViT-B-32-quickgelu embeddings with cosine threshold 0.85. Full-frame samples can
miss small, occluded or briefly visible products, and similar catalogue variants
can match together; the threshold is candidate generation, not proof of identity.
Speech uses faster-whisper tiny CPU/int8 and may misrecognize names or languages.
Both sources are combined into unapproved review windows. Store review remains
required. There is no provider fallback. One serialized CPU worker protects room
memory; cancellation waits for in-flight inference before removing temporary PCM.
PCM is deleted after analysis. Private transcripts stay out of the public timeline.
The synchronous ingest endpoint allows up to 30 minutes for bounded local CPU work;
large uploads may require a longer reverse-proxy timeout. The models add roughly
1 GB of working memory plus Python/runtime overhead; provision and measure on the
actual room host before deployment. Catalogue analysis is capped at 100 images,
with skipped/failing images identified in the receipt. The first image per SKU
is used; multiple angles and detection crops are future improvements.

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
