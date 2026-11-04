# video-shop

Internal room for store-owned videos and catalogues. Compose `video_room.mount(rig_app,
Path(DATA_DIR) / 'video-shop')` onto an initialized Rig host. The provided Dockerfile supplies FFmpeg; mounting on another host requires FFmpeg there; no paid services, new model routes or credentials. Durable data must be
on the host's data volume. This change does not alter deployment configuration.

Admin routes reuse Rig admin keys. `POST /v1/rig/video-shop/admin/videos` accepts
exactly one of `video_base64` or a public HTTPS `url`, optional timestamped `transcript` segments (`start`, `end`, `text`),
a required `rights_confirmed: true`, and `references` mapping catalogue SKUs to base64 image bytes. Images must belong
to the same store catalogue. Catalogue image URLs are fetched automatically over
guarded HTTPS (up to 100); explicit references replace inaccessible photos. FFmpeg
samples every five seconds (maximum ten minutes, 32 MiB), compares normalized
frames to references, and reuses Rig's catalogue search on transcript segments.
Simple image distance is conservative candidate generation, not general object
recognition. All suggestions require store approval. Silent/unclear videos can
produce an empty draft. No model is called; each result saves a code receipt.

GET the admin video route to reopen a draft. PUT it with `revision` and `moments`
to replace/edit/approve suggestions. Every moment has `start`, `end`,
`product_id` (catalogue SKU), and boolean `approved`. Stale edits conflict.

No founder-facing product name is assigned. Screen wording follows the Proposed
`docs/figma/video-shop/REGISTER.md` from the parallel design checkout, commit
be87b92e.

## Overlay

Load `/v1/rig/video-shop/widget.js` from the Rig host, then call
`VideoShop.mount(element, {rigBase: 'https://rig-host.example', key: publishableKey,
videoId, storeCartUrl, labels: {add: 'Add to cart'}})`.
The key must be a Rig publishable key restricted to the store's origin. Never
embed an admin key. The player fetches authenticated media as a local blob and
revokes it on `destroy()`. Approved moments alone reach the browser. Seeks update
products; inactive/deleted catalogue products are omitted on the next load.

Product detail uses `/v1/rig/products/{sku}`. Adds and checkout use Rig's existing
`/cart/session`, `/cart/add`, and `/cart/checkout`; no separate checkout or payment
service exists here. Listen for `video-shop:cart` to update the store UI and
`video-shop:state` for loading/error states. Labels follow the Proposed register (design commit be87b92e) and remain
overridable. Open store cart stays disabled unless the store supplies its own
HTTPS cart URL. The returned `checkout()` method uses Rig’s existing checkout
route and returns its store-owned checkout URL for the host integration. Call the returned `destroy()` on unmount.

The deployable entry point is `video_shop.video_asgi:app`. Build with `agents/`
as context using this room’s Dockerfile. It composes the existing Rig host and
uses its existing database, keys and cart settings. Persist `DATA_DIR/video-shop`.
Admin GET `/admin/videos` lists recent videos; GET `/admin/videos/{id}/media`
allows private draft playback during review. See `docs/acceptance/video_shop.md`
for limits and the offline acceptance recipe.
