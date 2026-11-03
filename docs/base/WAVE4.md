# Base wave 4 prerequisites

F12: missing approved Base audit frame and exported specification in docs/figma.
Required frame: founder audit page, including empty, running, completed and failed
states; measured evidence, source/date, receipt and downloadable results. This is
a frame requirement, not approval of layout or visible wording. No audit page or
UI copy is added by wave 4.

F5: the named enthec/webappanalyzer fingerprint dataset is GPL-3.0, not MIT.
Upstream: https://github.com/enthec/webappanalyzer/blob/main/CONTRIBUTING.md
Base already vendors independently authored MIT OpenTechalyzer fingerprints at
commit a3d30e479c91c06732ef88867d69b7feef8f3f35, with original source and license in
base.site_signals/1.0.1/data. Detection reads fetched site HTML and headers without
additional requests. The explicitly requested MIT WebAppAnalyzer source remains
unavailable; it is not silently substituted or relicensed. Reviews remain absent.

No Google Places, paid feeds or carrier lookup is added. Engine SOT and compliance
flags remain empty. The phone candidate requires Skala approval before runtime
selection; wave 4 does not change lifecycle state or approved versions.
