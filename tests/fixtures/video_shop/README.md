# Offline store fixture

`sample.mp4` is a generated ten-second drawing of a red cup on white. It contains
no third-party material or audio. `cup.ppm` is its first frame, used as the store's
catalogue photo. `catalogue.csv` uses Rig's normal importer and maps SKU `stock`
to the existing offline WooCommerce adapter fixture's product 1.

Regenerate from the repository root (requires FFmpeg):

```sh
ffmpeg -v error -f lavfi -i 'color=c=white:s=96x96:d=10:r=2,drawbox=x=24:y=24:w=40:h=48:color=red:t=fill,drawbox=x=64:y=32:w=16:h=28:color=red:t=5' -pix_fmt yuv420p -y tests/fixtures/video_shop/sample.mp4
ffmpeg -v error -i tests/fixtures/video_shop/sample.mp4 -frames:v 1 -y tests/fixtures/video_shop/cup.ppm
```

Acceptance supplies a timestamped transcript saying “Red cup” in seconds 0–5.
Vision independently finds the cup in seconds 5–10, without transcript evidence.
