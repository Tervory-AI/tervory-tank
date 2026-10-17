# Radix page

Route: /radix. Figma: https://www.figma.com/design/ksi7ctRwEnN8wbip1yfuhL?node-id=75-92

The page provides Overview, Findings, Reports, and the approved Sources popup
(API keys, Files, Source links, MCP connections; mobile accordions).
It reuses the standard headerLinks navigation and original reversed logo.
Only the body scrolls at normal viewport heights. A short viewport allows the
anchored menu to scroll so keyboard users can still reach every item.

Scan results and uploads are not connected to Workspace yet. The page says so.
Examples are explicitly labelled in the screen and downloaded Markdown. They
never represent tenant results. No network client, credential input, persistent
browser storage, scan submission, or host configuration is present.

A future connection must use authenticated, tenant-scoped server endpoints.
This page does not implement RX-3 or RX-4 and cannot enable outbound scans.
No hostname is proposed by this page.

## Checks

The existing CI checks the full Next build. The page-specific GitHub Actions
workflow bundles the actual view, navigation and CSS into a disposable harness
and checks them in Chromium. The harness does not bypass production middleware
or add a public preview route. It produces desktop/mobile screenshots as an
Actions artifact. No builds or installations are needed on the founder's laptop.

Design frames: desktop 75:92, mobile 75:142, example report 75:172,
Sources 75:215 / 75:260 / 75:305 / 75:350, mobile Sources 75:395.
