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

`speech.mp4` adds synthetic speech from FFmpeg's open-source Flite `slt` voice:
“This is a red cup. The red cup is on the table.” No transcript is supplied to the
room. The second five-second window contains the cup without spoken evidence.
Regenerate the spoken fixture (FFmpeg build must include Flite):

```sh
ffmpeg -v error -threads 1 -filter_threads 1 -i tests/fixtures/video_shop/sample.mp4 -f lavfi -i "flite=text='This is a red cup. The red cup is on the table.':voice=slt" -map 0:v -map 1:a -c:v copy -c:a aac -af apad -t 10 -y tests/fixtures/video_shop/speech.mp4
```

The drawing and script are original test material. The synthesized voice uses the
CMU Flite permissive license; see the room's third-party notices. Both silent and
spoken fixtures remain ten seconds so the overlay playback tests stay stable.
