# Wave 4 browser evidence

These are agent Chromium screenshots of the production static export, with local fonts and assets loaded and reduced motion enabled. They are not founder acceptance screenshots.

Source: [homepage register](../../figma/HOMEPAGE-REGISTER.md). Current homepage desktop/mobile: **59:164 / 63:197**. Rig product desktop/mobile: **56:127 / 56:798**.

The `homepage-*.png` and `rig-product-*.png` files show the two public pages at each saved width. Widths 390 and 1440 match the source frames; 320/375/430 and the tablet/breakpoint widths document responsive adaptation. Screenshots are actual HTML/CSS, with no image scaling of the page.

From `site/`, using the isolated preview on port 8947:

```sh
npm run build
TMPDIR=/dev/shm npm run check
/home/ammosync/trigger-crm-venv312/bin/python -m pytest ../tests/test_site_homepage.py -q
TMPDIR=/dev/shm PLAYWRIGHT_MODULE=/home/ammosync/tngo-review-20261027/node_modules/playwright/index.mjs BROWSER_EXECUTABLE=/opt/google/chrome/chrome node check-website-browser.mjs
TMPDIR=/dev/shm PLAYWRIGHT_MODULE=/home/ammosync/tngo-review-20261027/node_modules/playwright/index.mjs BROWSER_EXECUTABLE=/opt/google/chrome/chrome HOMEPAGE_URL=http://127.0.0.1:8947 SCREENSHOT_DIR=/dev/shm/wave4-homepage-interactions node check-homepage-browser.mjs
```

`check-website-browser.mjs` sweeps every integer width from **320 to 1440** on each public page (1,121 widths per page). It checks actual visible text ranges against their elements, Rig panels and viewport; page/control bounds; and the presence of all four homepage Optional tags. It allows the receipt table's intentional horizontal scroller and excludes screen-reader-only labels. It also checks Rig's seven stage selections at ten widths, keyboard navigation, example checkout, calculator input, local anchors and canonical URL. The JSON files record the completed sweep results.

`check-homepage-browser.mjs` checks all Engine/Rig states, toggles, receipt CSV/PDF, automatic/reduced-motion behavior, loaded images and both existing forms. Diagram geometry, all four Rig states, receipt tabs and toggle bounds are checked at **320, 375, 390, 430, 431, 600, 767, 768, 1000, 1199, 1200 and 1440**; form submissions run after that width matrix. Form checks use `/dev/shm/homepage-wave4-signups.jsonl`; no production signups are used. The Rig illustrations send no payment/order/model POSTs.
