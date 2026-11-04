# video-shop

Internal room for store-owned videos and catalogues. Compose `video_room.mount(rig_app,
Path(DATA_DIR) / 'video-shop')` onto an initialized Rig host. Requires FFmpeg on
the host; no paid services, new model routes or credentials. Durable data must be
on the host's data volume. This change does not alter deployment configuration.

Admin routes reuse Rig admin keys. `POST /v1/rig/video-shop/admin/videos` accepts
exactly one of `video_base64` or a public HTTPS `url`, optional timestamped `transcript` segments (`start`, `end`, `text`),
and `references` mapping catalogue SKUs to base64 image bytes. Images must belong
to the same store catalogue; upload catalogue images alongside the video. FFmpeg
samples every five seconds (maximum ten minutes, 32 MiB), compares normalized
frames to references, and reuses Rig's catalogue search on transcript segments.
Simple image distance is conservative candidate generation, not general object
recognition. All suggestions require store approval. Silent/unclear videos can
produce an empty draft. No model is called; each result saves a code receipt.

GET the admin video route to reopen a draft. PUT it with `revision` and `moments`
to replace/edit/approve suggestions. Every moment has `start`, `end`,
`product_id` (catalogue SKU), and boolean `approved`. Stale edits conflict.

No founder-facing product name is assigned. Screen wording follows the future
`docs/figma/video-shop/REGISTER.md`; no register existed at implementation time.
