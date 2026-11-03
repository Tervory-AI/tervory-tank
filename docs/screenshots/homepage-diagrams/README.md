# Homepage Engine and Rig diagrams

Branch: `codex/homepage-diagrams`. Source: approved homepage [59:164](https://www.figma.com/design/bOSFzo7qMhHjJ6T5brXG1Y?node-id=59-164), mobile homepage `63:197`. The homepage stays dark.

Engine source diagrams: desktop `91:2830`, mobile `91:2935`. Rig source diagrams: desktop `127:2903`, mobile `127:3016`, matched variants `127:2535` and `127:2741`. Both get_design_context and get_screenshot were read, including the mobile page. The existing 27 local home assets and all 22 rendered image slots are retained.

The Engine uses five connected rounded shapes, visual price chips, paired lanes, a connected cache path, savings bars and the batch-rate graphic. Its approved selection/automatic progression highlights the shape itself; the duplicate tabs and inspector are removed. Rig keeps the connected product/accessory shapes and market rail, with four stages and four optional switches. The founder’s 3 November 13:06 PT cart ruling replaces the quote/payment ending. Add to cart resets the illustration and issues no request.

## Visual comparison

Open [comparison.html](comparison.html) for source and rendered **sections** side by side at 1440px and 375px. The source mobile frame is 390px; the implementation screenshots are taken at the requested 375px. Original images and focused diagram screenshots are included alongside full section captures.

| View | Approved Figma | Implementation |
| --- | --- | --- |
| Engine desktop | [source](figma-engine-section-desktop.png) | [1440px](browser/engine-section-1440.png) |
| Engine mobile | [source](figma-engine-section-mobile.png) | [375px](browser/engine-section-375.png) |
| Rig desktop | [source](figma-rig-section-desktop.png) | [1440px](browser/rig-section-1440.png) |
| Rig mobile | [source](figma-rig-section-mobile.png) | [375px](browser/rig-section-375.png) |

Side-by-side PNGs: [Engine 1440](comparison-engine-1440.png), [Engine 375](comparison-engine-375.png), [Rig 1440](comparison-rig-1440.png), [Rig 375](comparison-rig-375.png).

Final results: build PASS; public/store checks PASS; homepage regressions 3 passed; [browser validation](validation.json) PASS at all six widths with zero JavaScript errors.

## Differences retained to satisfy the brief

- The founder explicitly removes Figma’s Engine options and inspector. Only the diagram shapes remain in that part of the section; the section’s existing support/mechanism text stays.
- Figma uses 9–13px detail labels in several places. Diagram text is at least 14px here. Shapes grow naturally, model chips stack at 320px, and the mobile cache path stacks instead of squeezing words.
- Larger mobile accessory labels may wrap within the card; each word stays intact. Mobile market labels use the approved short price-only labels. More vertical space separates labels from the market marker.
- The source has a quote/payment ending. The implementation instead uses the founder’s cart wording and removes the payment option.
- Source and implementation are not pixel-identical because these explicit requirements supersede the older frame. Section copy and unrelated homepage sections are otherwise unchanged.

## Verification

From `/workspace/codex-homepage-diagrams/site`:
```sh
npm ci --ignore-scripts
npm run build
TMPDIR=/dev/shm npm run check
TMPDIR=/dev/shm PLAYWRIGHT_MODULE=/workspace/codex-homepage-diagrams/.browser-tools/node_modules/playwright/index.mjs BROWSER_EXECUTABLE=/opt/google/chrome/chrome HOMEPAGE_URL=http://127.0.0.1:8927 SCREENSHOT_DIR=/workspace/codex-homepage-diagrams/docs/screenshots/homepage-diagrams/browser node check-homepage-browser.mjs
```

The browser check covers 320, 375, 390, 430, 768 and 1440px; diagram text bounds and 14px minimum; whole-word wrapping; Engine shape visibility/order; all four Rig states; market-label overlap; cart reset; no horizontal page scrolling; loaded local images; keyboard selection; reduced-motion/automatic progression; receipt CSV/PDF; and both signup forms against an isolated review store. Illustration controls must issue zero POST requests.

Homepage regression tests run with the existing Python test environment:
```sh
/workspace/codex-radix-r4-py312/bin/python -m pytest tests/test_site_homepage.py -q
```

System Python has no pytest; the existing environment passes the three regression tests. An initial build exposed a missing comma in the copy ledger; that was corrected. Browser checks exposed a 320px market-label overflow, and visual review exposed overlapping seller labels; both were corrected before the final evidence run.

No production code outside these homepage components/styles/copy/checks is changed. No deployment, real order, payment or model call occurs in this task. Founder-phone acceptance at tervory.com remains the final check after merge and deployment.

## Removed wording

Removed duplicate Engine inspector paragraphs (the approved mechanism descriptions below the diagram remain):
- “The engine auto-checks the cheapest available frontier model.”
- “A shadow run is launched alongside with the goal to prove a lighter and cheaper model can provide the same quality of answers or learn from them.”
- “As the engine is learning it caches answers, recognises repeat or similar prompts and then runs using internal code as opposed to another frontier model.”
- “Over a short period your savings grow exponentially as your usage increases and the engine learns your business.”
- “What no AI company highlights is their bulk / batch rates which can drive down costs by 50% before the first prompt is then sent.”

Removed inspector examples:
- “e.g. DeepSeek $2/1M picked over Anthropic $15/1M”
- “e.g. lighter model $0.80/1M vs frontier $2/1M, same answer”
- “e.g. a repeat prompt answered from cache at $0”
- “e.g. $40 saved in month 1 → $1,280 in month 8”
- “e.g. $2.00/1M → $1.00/1M, back within 24 hours”

Removed the duplicate numbered Engine tab labels, inspector title/kicker and “Example” label. The diagram shapes retain their own existing stage labels and numbers.

Removed from the Rig illustration:
- “Get A Quote”
- “Accept & pay”
- “Payment capture on Accept”
- “Quote ready · everything that fits, at a price that beats or matches the market”
- “Quote: Product + 3 accessories that fit · e.g. $151”
- “Rig makes sure your site beats or matches them” (the obsolete intermediate caption)
- “Beats the best market price by e.g. $1”
- “e.g. $9 above the best market price”
- “Listed price · 3 accessories that fit, paired”

Only the two new strings explicitly supplied by the founder were introduced: “Add to cart” and “In the cart · everything that fits, at a price that beats or matches the market”. Other copy-ledger additions transcribe existing Figma state labels, including mobile seller prices.
