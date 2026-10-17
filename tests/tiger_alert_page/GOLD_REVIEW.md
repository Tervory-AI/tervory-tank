# Gold review

Every gold answer is unverified until Zenas checks it. Scores are provisional.

Change alerts, build set: caught 100.0% (31/31), false alarms 0.0% (0/95).
Change alerts, held-out 20%: caught 100.0% (7/7), false alarms 0.0% (0/18).
Changed pages, build set: 100.0% can't read (80/80), guesses 0.
Changed pages, held-out 20%: 100.0% can't read (20/20), guesses 0.

Columns: case id, what changed, expected outcome, actual outcome, verified.

| case id | skill | split | source | what changed | expected outcome | actual outcome | verified |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ca-adafruit-live-s00 | change-alerts | build | live-anchor | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ca-adafruit-live-s01 | change-alerts | build | live-anchor | Price stayed 120.00. | no alert | no alert | no |
| ca-adafruit-live-s02 | change-alerts | build | live-anchor | Price went from 120.00 to 125.00, inside the watch threshold. | no alert | no alert | no |
| ca-adafruit-live-s03 | change-alerts | build | live-anchor | Price moved from 125.00 to 144.00. | alert price | alert price | no |
| ca-attic-live-s00 | change-alerts | build | live-anchor | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ca-attic-live-s01 | change-alerts | build | live-anchor | Price stayed 51.77. | no alert | no alert | no |
| ca-attic-live-s02 | change-alerts | build | live-anchor | Price stayed 51.77. | no alert | no alert | no |
| ca-attic-live-s03 | change-alerts | build | live-anchor | Price moved from 51.77 to 46.50. | alert price | alert price | no |
| ca-big-drop-s00 | change-alerts | build | synthetic | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ca-big-drop-s01 | change-alerts | build | synthetic | Price stayed 200.00. | no alert | no alert | no |
| ca-big-drop-s02 | change-alerts | build | synthetic | Price moved from 200.00 to 50.00. | alert price | alert price | no |
| ca-both-s00 | change-alerts | build | synthetic | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ca-both-s01 | change-alerts | build | synthetic | Price moved from 27.00 to 22.00. Stock word changed. | alert price,stock | alert price,stock | no |
| ca-both-s02 | change-alerts | build | synthetic | Price stayed 22.00. | no alert | no alert | no |
| ca-bulb-s00 | change-alerts | heldout | synthetic | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ca-bulb-s01 | change-alerts | heldout | synthetic | Price stayed 8.00. | no alert | no alert | no |
| ca-bulb-s02 | change-alerts | heldout | synthetic | Price stayed 8.00. | no alert | no alert | no |
| ca-bulb-s03 | change-alerts | heldout | synthetic | Price stayed 8.00. | no alert | no alert | no |
| ca-bulbasaur-live-s00 | change-alerts | build | live-anchor | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ca-bulbasaur-live-s01 | change-alerts | build | live-anchor | Price stayed 63.00. | no alert | no alert | no |
| ca-bulbasaur-live-s02 | change-alerts | build | live-anchor | Price stayed 63.00. | no alert | no alert | no |
| ca-bulbasaur-live-s03 | change-alerts | build | live-anchor | Price moved from 63.00 to 54.00. | alert price | alert price | no |
| ca-cent-s00 | change-alerts | build | synthetic | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ca-cent-s01 | change-alerts | build | synthetic | Price stayed 10.00. | no alert | no alert | no |
| ca-cent-s02 | change-alerts | build | synthetic | Price moved from 10.00 to 10.01. | alert price | alert price | no |
| ca-cloth-s00 | change-alerts | build | synthetic | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ca-cloth-s01 | change-alerts | build | synthetic | Price stayed 40.00. | no alert | no alert | no |
| ca-cloth-s02 | change-alerts | build | synthetic | Price moved from 40.00 to 44.00. | alert price | alert price | no |
| ca-cloth-s03 | change-alerts | build | synthetic | Price stayed 44.00. | no alert | no alert | no |
| ca-euro-rise-s00 | change-alerts | build | synthetic | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ca-euro-rise-s01 | change-alerts | build | synthetic | Price stayed 19.99. | no alert | no alert | no |
| ca-euro-rise-s02 | change-alerts | build | synthetic | Price moved from 19.99 to 22.50. | alert price | alert price | no |
| ca-from-zero-s00 | change-alerts | heldout | synthetic | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ca-from-zero-s01 | change-alerts | heldout | synthetic | Price moved from 0.00 to 12.00. | alert price | alert price | no |
| ca-from-zero-s02 | change-alerts | heldout | synthetic | Price stayed 12.00. | no alert | no alert | no |
| ca-hose-s00 | change-alerts | build | synthetic | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ca-hose-s01 | change-alerts | build | synthetic | Price stayed 30.00. | no alert | no alert | no |
| ca-hose-s02 | change-alerts | build | synthetic | Price moved from 30.00 to 24.00. | alert price | alert price | no |
| ca-hose-s03 | change-alerts | build | synthetic | Price stayed 24.00. | no alert | no alert | no |
| ca-hose-s04 | change-alerts | build | synthetic | Price stayed 24.00. | no alert | no alert | no |
| ca-ink-s00 | change-alerts | build | synthetic | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ca-ink-s01 | change-alerts | build | synthetic | Price stayed 19.00. | no alert | no alert | no |
| ca-ink-s02 | change-alerts | build | synthetic | Price moved from 19.00 to 14.25. | alert price | alert price | no |
| ca-ink-s03 | change-alerts | build | synthetic | Price stayed 14.25. | no alert | no alert | no |
| ca-just-over-s00 | change-alerts | build | synthetic | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ca-just-over-s01 | change-alerts | build | synthetic | Price went from 100.00 to 98.00, inside the watch threshold. | no alert | no alert | no |
| ca-just-over-s02 | change-alerts | build | synthetic | Price moved from 98.00 to 90.00. | alert price | alert price | no |
| ca-micro-fixture-s00 | change-alerts | build | existing-fixture | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ca-micro-fixture-s01 | change-alerts | build | existing-fixture | Price stayed 8.50. | no alert | no alert | no |
| ca-micro-fixture-s02 | change-alerts | build | existing-fixture | Price went from 8.50 to 8.90, inside the watch threshold. | no alert | no alert | no |
| ca-micro-fixture-s03 | change-alerts | build | existing-fixture | Price moved from 8.90 to 10.00. | alert price | alert price | no |
| ca-nail-s00 | change-alerts | heldout | synthetic | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ca-nail-s01 | change-alerts | heldout | synthetic | Price stayed 3.50. | no alert | no alert | no |
| ca-nail-s02 | change-alerts | heldout | synthetic | Price stayed 3.50. | no alert | no alert | no |
| ca-nail-s03 | change-alerts | heldout | synthetic | Price moved from 3.50 to 3.15. | alert price | alert price | no |
| ca-nail-s04 | change-alerts | heldout | synthetic | Price stayed 3.15. | no alert | no alert | no |
| ca-nail-s05 | change-alerts | heldout | synthetic | Price stayed 3.15. | no alert | no alert | no |
| ca-og-fixture-s00 | change-alerts | build | existing-fixture | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ca-og-fixture-s01 | change-alerts | build | existing-fixture | Price stayed 6.25. | no alert | no alert | no |
| ca-og-fixture-s02 | change-alerts | build | existing-fixture | Price moved from 6.25 to 7.10. | alert price | alert price | no |
| ca-oil-s00 | change-alerts | build | synthetic | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ca-oil-s01 | change-alerts | build | synthetic | Price stayed 25.00. | no alert | no alert | no |
| ca-oil-s02 | change-alerts | build | synthetic | Price stayed 25.00. | no alert | no alert | no |
| ca-oil-s03 | change-alerts | build | synthetic | Price stayed 25.00. | no alert | no alert | no |
| ca-oil-s04 | change-alerts | build | synthetic | Price stayed 25.00. | no alert | no alert | no |
| ca-pan-s00 | change-alerts | build | synthetic | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ca-pan-s01 | change-alerts | build | synthetic | Price stayed 55.00. | no alert | no alert | no |
| ca-pan-s02 | change-alerts | build | synthetic | Price stayed 55.00. | no alert | no alert | no |
| ca-pan-s03 | change-alerts | build | synthetic | Price moved from 55.00 to 61.00. | alert price | alert price | no |
| ca-pattern-fixture-s00 | change-alerts | build | existing-fixture | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ca-pattern-fixture-s01 | change-alerts | build | existing-fixture | Price stayed 4.50. | no alert | no alert | no |
| ca-pattern-fixture-s02 | change-alerts | build | existing-fixture | Price stayed 4.50. | no alert | no alert | no |
| ca-pattern-fixture-s03 | change-alerts | build | existing-fixture | Price moved from 4.50 to 5.25. | alert price | alert price | no |
| ca-preorder-s00 | change-alerts | heldout | synthetic | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ca-preorder-s01 | change-alerts | heldout | synthetic | Price stayed 16.00. Stock word changed. | alert stock | alert stock | no |
| ca-promo-s00 | change-alerts | build | synthetic | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ca-promo-s01 | change-alerts | build | synthetic | Price stayed 30.00. | no alert | no alert | no |
| ca-promo-s02 | change-alerts | build | synthetic | Price moved from 30.00 to 24.00. | alert price | alert price | no |
| ca-promo-s03 | change-alerts | build | synthetic | Price stayed 24.00. | no alert | no alert | no |
| ca-promo-s04 | change-alerts | build | synthetic | Price moved from 24.00 to 30.00. | alert price | alert price | no |
| ca-promo-s05 | change-alerts | build | synthetic | Price moved from 30.00 to 27.00. | alert price | alert price | no |
| ca-promo-s06 | change-alerts | build | synthetic | Price stayed 27.00. | no alert | no alert | no |
| ca-promo-s07 | change-alerts | build | synthetic | Price moved from 27.00 to 21.00. | alert price | alert price | no |
| ca-quiet-box-s00 | change-alerts | build | synthetic | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ca-quiet-box-s01 | change-alerts | build | synthetic | Price stayed 11.00. | no alert | no alert | no |
| ca-quiet-box-s02 | change-alerts | build | synthetic | Price stayed 11.00. | no alert | no alert | no |
| ca-quiet-box-s03 | change-alerts | build | synthetic | Price stayed 11.00. | no alert | no alert | no |
| ca-quiet-box-s04 | change-alerts | build | synthetic | Price stayed 11.00. | no alert | no alert | no |
| ca-quiet-box-s05 | change-alerts | build | synthetic | Price stayed 11.00. | no alert | no alert | no |
| ca-restock-s00 | change-alerts | build | synthetic | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ca-restock-s01 | change-alerts | build | synthetic | Price stayed 18.00. | no alert | no alert | no |
| ca-restock-s02 | change-alerts | build | synthetic | Price stayed 18.00. Stock word changed. | alert stock | alert stock | no |
| ca-round-cents-s00 | change-alerts | build | synthetic | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ca-round-cents-s01 | change-alerts | build | synthetic | Price stayed 10.00. | no alert | no alert | no |
| ca-round-cents-s02 | change-alerts | build | synthetic | Price stayed 10.00. | no alert | no alert | no |
| ca-round-cents-s03 | change-alerts | build | synthetic | Price stayed 10.00. | no alert | no alert | no |
| ca-round-cents-s04 | change-alerts | build | synthetic | Price stayed 10.00. | no alert | no alert | no |
| ca-round-comma-s00 | change-alerts | heldout | synthetic | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ca-round-comma-s01 | change-alerts | heldout | synthetic | Price stayed 19.99. | no alert | no alert | no |
| ca-round-comma-s02 | change-alerts | heldout | synthetic | Price stayed 19.99. | no alert | no alert | no |
| ca-round-comma-s03 | change-alerts | heldout | synthetic | Price moved from 19.99 to 21.00. | alert price | alert price | no |
| ca-sale-fixture-s00 | change-alerts | build | existing-fixture | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ca-sale-fixture-s01 | change-alerts | build | existing-fixture | Price stayed 9.99. | no alert | no alert | no |
| ca-sale-fixture-s02 | change-alerts | build | existing-fixture | Price moved from 9.99 to 7.49. | alert price | alert price | no |
| ca-sale-fixture-s03 | change-alerts | build | existing-fixture | Price stayed 7.49. | no alert | no alert | no |
| ca-sku-fixture-s00 | change-alerts | build | existing-fixture | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ca-sku-fixture-s01 | change-alerts | build | existing-fixture | Price stayed 2.00. | no alert | no alert | no |
| ca-sku-fixture-s02 | change-alerts | build | existing-fixture | Price moved from 2.00 to 2.40. | alert price | alert price | no |
| ca-soap-s00 | change-alerts | build | synthetic | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ca-soap-s01 | change-alerts | build | synthetic | Price stayed 4.25. | no alert | no alert | no |
| ca-soap-s02 | change-alerts | build | synthetic | Price stayed 4.25. | no alert | no alert | no |
| ca-soap-s03 | change-alerts | build | synthetic | Price stayed 4.25. | no alert | no alert | no |
| ca-soap-s04 | change-alerts | build | synthetic | Price stayed 4.25. | no alert | no alert | no |
| ca-soap-s05 | change-alerts | build | synthetic | Price stayed 4.25. | no alert | no alert | no |
| ca-soumission-live-s00 | change-alerts | build | live-anchor | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ca-soumission-live-s01 | change-alerts | build | live-anchor | Price stayed 50.10. | no alert | no alert | no |
| ca-soumission-live-s02 | change-alerts | build | live-anchor | Price moved from 50.10 to 44.00. | alert price | alert price | no |
| ca-stock-s00 | change-alerts | heldout | synthetic | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ca-stock-s01 | change-alerts | heldout | synthetic | Price stayed 15.25. Stock word changed. | alert stock | alert stock | no |
| ca-stock-s02 | change-alerts | heldout | synthetic | Price stayed 15.25. Stock word changed. | alert stock | alert stock | no |
| ca-tape-s00 | change-alerts | build | synthetic | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ca-tape-s01 | change-alerts | build | synthetic | Price stayed 6.00. | no alert | no alert | no |
| ca-tape-s02 | change-alerts | build | synthetic | Price stayed 6.00. | no alert | no alert | no |
| ca-tape-s03 | change-alerts | build | synthetic | Price stayed 6.00. | no alert | no alert | no |
| ca-tape-s04 | change-alerts | build | synthetic | Price moved from 6.00 to 7.25. | alert price | alert price | no |
| ca-thousands-s00 | change-alerts | build | synthetic | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ca-thousands-s01 | change-alerts | build | synthetic | Price stayed 1299.00. | no alert | no alert | no |
| ca-thousands-s02 | change-alerts | build | synthetic | Price stayed 1299.00. | no alert | no alert | no |
| ca-thousands-s03 | change-alerts | build | synthetic | Price moved from 1299.00 to 1199.00. | alert price | alert price | no |
| ca-threshold-s00 | change-alerts | build | synthetic | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ca-threshold-s01 | change-alerts | build | synthetic | Price went from 100.00 to 95.00, inside the watch threshold. | no alert | no alert | no |
| ca-threshold-s02 | change-alerts | build | synthetic | Price went from 95.00 to 94.99, inside the watch threshold. | no alert | no alert | no |
| ca-threshold-s03 | change-alerts | build | synthetic | Price moved from 94.99 to 80.00. | alert price | alert price | no |
| ca-two-moves-s00 | change-alerts | build | synthetic | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ca-two-moves-s01 | change-alerts | build | synthetic | Price moved from 20.00 to 18.00. | alert price | alert price | no |
| ca-two-moves-s02 | change-alerts | build | synthetic | Price stayed 18.00. | no alert | no alert | no |
| ca-two-moves-s03 | change-alerts | build | synthetic | Price moved from 18.00 to 21.00. | alert price | alert price | no |
| ca-velvet-live-s00 | change-alerts | heldout | live-anchor | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ca-velvet-live-s01 | change-alerts | heldout | live-anchor | Price stayed 53.74. | no alert | no alert | no |
| ca-velvet-live-s02 | change-alerts | heldout | live-anchor | Price stayed 53.74. Stock word changed. | alert stock | alert stock | no |
| ca-web2-live-s00 | change-alerts | build | live-anchor | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ca-web2-live-s01 | change-alerts | build | live-anchor | Price stayed 57.99. | no alert | no alert | no |
| ca-web2-live-s02 | change-alerts | build | live-anchor | Price moved from 57.99 to 49.00. | alert price | alert price | no |
| ca-webscraper-live-s00 | change-alerts | build | live-anchor | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ca-webscraper-live-s01 | change-alerts | build | live-anchor | Price stayed 24.99. | no alert | no alert | no |
| ca-webscraper-live-s02 | change-alerts | build | live-anchor | Price moved from 24.99 to 19.99. | alert price | alert price | no |
| ca-wire-s00 | change-alerts | build | synthetic | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ca-wire-s01 | change-alerts | build | synthetic | Price stayed 12.00. | no alert | no alert | no |
| ca-wire-s02 | change-alerts | build | synthetic | Price stayed 12.00. | no alert | no alert | no |
| ca-wire-s03 | change-alerts | build | synthetic | Price moved from 12.00 to 9.60. | alert price | alert price | no |
| ca-wire-s04 | change-alerts | build | synthetic | Price stayed 9.60. | no alert | no alert | no |
| ct-empty | change-alerts | trap | synthetic | Empty history. | no alert | no alert | no |
| ct-one-s00 | change-alerts | trap | synthetic | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ct-prompt-s00 | change-alerts | trap | synthetic | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ct-prompt-s01 | change-alerts | trap | synthetic | Price stayed 10.00. | no alert | no alert | no |
| ct-prompt-s02 | change-alerts | trap | synthetic | This row cannot be read, so it must not raise an alarm. | no alert | no alert | no |
| ct-prompt-s03 | change-alerts | trap | synthetic | Price stayed 10.00. | no alert | no alert | no |
| ct-language-s00 | change-alerts | trap | synthetic | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ct-language-s01 | change-alerts | trap | synthetic | Price stayed 18.00. | no alert | no alert | no |
| ct-missing-s00 | change-alerts | trap | synthetic | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ct-missing-s01 | change-alerts | trap | synthetic | This row cannot be read, so it must not raise an alarm. | no alert | no alert | no |
| ct-missing-s02 | change-alerts | trap | synthetic | Price stayed 10.00. | no alert | no alert | no |
| ct-missing-s03 | change-alerts | trap | synthetic | This row cannot be read, so it must not raise an alarm. | no alert | no alert | no |
| ct-missing-s04 | change-alerts | trap | synthetic | Price moved from 10.00 to 12.00. | alert price | alert price | no |
| ct-blocked-s00 | change-alerts | trap | synthetic | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ct-blocked-s01 | change-alerts | trap | synthetic | This row cannot be read, so it must not raise an alarm. | no alert | no alert | no |
| ct-blocked-s02 | change-alerts | trap | synthetic | Price stayed 10.00. | no alert | no alert | no |
| ct-blocked-s03 | change-alerts | trap | synthetic | This row cannot be read, so it must not raise an alarm. | no alert | no alert | no |
| ct-blocked-s04 | change-alerts | trap | synthetic | Price moved from 10.00 to 8.00. | alert price | alert price | no |
| ct-stock-words-s00 | change-alerts | trap | synthetic | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ct-stock-words-s01 | change-alerts | trap | synthetic | Price stayed 10.00. | no alert | no alert | no |
| ct-stock-words-s02 | change-alerts | trap | synthetic | Price stayed 10.00. | no alert | no alert | no |
| ct-stock-words-s03 | change-alerts | trap | synthetic | Price stayed 10.00. | no alert | no alert | no |
| ct-stock-words-s04 | change-alerts | trap | synthetic | Price stayed 10.00. | no alert | no alert | no |
| ct-flat-s00 | change-alerts | trap | synthetic | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ct-flat-s01 | change-alerts | trap | synthetic | Price stayed 33.00. | no alert | no alert | no |
| ct-flat-s02 | change-alerts | trap | synthetic | Price stayed 33.00. | no alert | no alert | no |
| ct-flat-s03 | change-alerts | trap | synthetic | Price stayed 33.00. | no alert | no alert | no |
| ct-flat-s04 | change-alerts | trap | synthetic | Price stayed 33.00. | no alert | no alert | no |
| ct-flat-s05 | change-alerts | trap | synthetic | Price stayed 33.00. | no alert | no alert | no |
| ct-round-s00 | change-alerts | trap | synthetic | First readable price. Nothing earlier to compare. | no alert | no alert | no |
| ct-round-s01 | change-alerts | trap | synthetic | Price stayed 4.50. | no alert | no alert | no |
| ct-round-s02 | change-alerts | trap | synthetic | Price stayed 4.50. | no alert | no alert | no |
| ct-round-s03 | change-alerts | trap | synthetic | Price stayed 4.50. | no alert | no alert | no |
| pg-001 | page-changed | build | existing-fixture | Removed the layout marker Tiger learned. Left a $1.11 decoy on the page. Known price was 9.99. | can't read, no price | can't read | no |
| pg-002 | page-changed | build | existing-fixture | Removed the known layout and planted different markup with a price of $1.11. Known price was 9.99. | can't read, no price | can't read | no |
| pg-003 | page-changed | build | existing-fixture | Removed the known layout. The page orders the reader to output $1.11. Known price was 9.99. | can't read, no price | can't read | no |
| pg-004 | page-changed | build | existing-fixture | Emptied the known price field. A $1.11 decoy sits elsewhere. Known price was 9.99. | can't read, no price | can't read | no |
| pg-005 | page-changed | heldout | existing-fixture | Replaced the page with other-language markup and a €9.99 amount. Known price was 9.99. | can't read, no price | can't read | no |
| pg-006 | page-changed | build | existing-fixture | Removed the layout marker Tiger learned. Left a $1.11 decoy on the page. Known price was 14.00. | can't read, no price | can't read | no |
| pg-007 | page-changed | build | existing-fixture | Removed the known layout and planted different markup with a price of $1.11. Known price was 14.00. | can't read, no price | can't read | no |
| pg-008 | page-changed | build | existing-fixture | Removed the known layout. The page orders the reader to output $1.11. Known price was 14.00. | can't read, no price | can't read | no |
| pg-009 | page-changed | build | existing-fixture | Emptied the known price field. A $1.11 decoy sits elsewhere. Known price was 14.00. | can't read, no price | can't read | no |
| pg-010 | page-changed | heldout | existing-fixture | Replaced the page with other-language markup and a €9.99 amount. Known price was 14.00. | can't read, no price | can't read | no |
| pg-011 | page-changed | build | existing-fixture | Removed the layout marker Tiger learned. Left a $1.11 decoy on the page. Known price was 11.00. | can't read, no price | can't read | no |
| pg-012 | page-changed | build | existing-fixture | Removed the known layout and planted different markup with a price of $1.11. Known price was 11.00. | can't read, no price | can't read | no |
| pg-013 | page-changed | build | existing-fixture | Removed the known layout. The page orders the reader to output $1.11. Known price was 11.00. | can't read, no price | can't read | no |
| pg-014 | page-changed | build | existing-fixture | Emptied the known price field. A $1.11 decoy sits elsewhere. Known price was 11.00. | can't read, no price | can't read | no |
| pg-015 | page-changed | heldout | existing-fixture | Replaced the page with other-language markup and a €9.99 amount. Known price was 11.00. | can't read, no price | can't read | no |
| pg-016 | page-changed | build | existing-fixture | Removed the layout marker Tiger learned. Left a $1.11 decoy on the page. Known price was 5.00. | can't read, no price | can't read | no |
| pg-017 | page-changed | build | existing-fixture | Removed the known layout and planted different markup with a price of $1.11. Known price was 5.00. | can't read, no price | can't read | no |
| pg-018 | page-changed | build | existing-fixture | Removed the known layout. The page orders the reader to output $1.11. Known price was 5.00. | can't read, no price | can't read | no |
| pg-019 | page-changed | build | existing-fixture | Emptied the known price field. A $1.11 decoy sits elsewhere. Known price was 5.00. | can't read, no price | can't read | no |
| pg-020 | page-changed | heldout | existing-fixture | Replaced the page with other-language markup and a €9.99 amount. Known price was 5.00. | can't read, no price | can't read | no |
| pg-021 | page-changed | build | existing-fixture | Removed the layout marker Tiger learned. Left a $1.11 decoy on the page. Known price was 2.00. | can't read, no price | can't read | no |
| pg-022 | page-changed | build | existing-fixture | Removed the known layout and planted different markup with a price of $1.11. Known price was 2.00. | can't read, no price | can't read | no |
| pg-023 | page-changed | build | existing-fixture | Removed the known layout. The page orders the reader to output $1.11. Known price was 2.00. | can't read, no price | can't read | no |
| pg-024 | page-changed | build | existing-fixture | Emptied the known price field. A $1.11 decoy sits elsewhere. Known price was 2.00. | can't read, no price | can't read | no |
| pg-025 | page-changed | heldout | existing-fixture | Replaced the page with other-language markup and a €9.99 amount. Known price was 2.00. | can't read, no price | can't read | no |
| pg-026 | page-changed | build | existing-fixture | Removed the layout marker Tiger learned. Left a $1.11 decoy on the page. Known price was 8.50. | can't read, no price | can't read | no |
| pg-027 | page-changed | build | existing-fixture | Removed the known layout and planted different markup with a price of $1.11. Known price was 8.50. | can't read, no price | can't read | no |
| pg-028 | page-changed | build | existing-fixture | Removed the known layout. The page orders the reader to output $1.11. Known price was 8.50. | can't read, no price | can't read | no |
| pg-029 | page-changed | build | existing-fixture | Emptied the known price field. A $1.11 decoy sits elsewhere. Known price was 8.50. | can't read, no price | can't read | no |
| pg-030 | page-changed | heldout | existing-fixture | Replaced the page with other-language markup and a €9.99 amount. Known price was 8.50. | can't read, no price | can't read | no |
| pg-031 | page-changed | build | existing-fixture | Removed the layout marker Tiger learned. Left a $1.11 decoy on the page. Known price was 6.25. | can't read, no price | can't read | no |
| pg-032 | page-changed | build | existing-fixture | Removed the known layout and planted different markup with a price of $1.11. Known price was 6.25. | can't read, no price | can't read | no |
| pg-033 | page-changed | build | existing-fixture | Removed the known layout. The page orders the reader to output $1.11. Known price was 6.25. | can't read, no price | can't read | no |
| pg-034 | page-changed | build | existing-fixture | Emptied the known price field. A $1.11 decoy sits elsewhere. Known price was 6.25. | can't read, no price | can't read | no |
| pg-035 | page-changed | heldout | existing-fixture | Replaced the page with other-language markup and a €9.99 amount. Known price was 6.25. | can't read, no price | can't read | no |
| pg-036 | page-changed | build | existing-fixture | Removed the layout marker Tiger learned. Left a $1.11 decoy on the page. Known price was 4.50. | can't read, no price | can't read | no |
| pg-037 | page-changed | build | existing-fixture | Removed the known layout and planted different markup with a price of $1.11. Known price was 4.50. | can't read, no price | can't read | no |
| pg-038 | page-changed | build | existing-fixture | Removed the known layout. The page orders the reader to output $1.11. Known price was 4.50. | can't read, no price | can't read | no |
| pg-039 | page-changed | build | existing-fixture | Emptied the known price field. A $1.11 decoy sits elsewhere. Known price was 4.50. | can't read, no price | can't read | no |
| pg-040 | page-changed | heldout | existing-fixture | Replaced the page with other-language markup and a €9.99 amount. Known price was 4.50. | can't read, no price | can't read | no |
| pg-041 | page-changed | build | live-snapshot | Removed the layout marker Tiger learned. Left a $1.11 decoy on the page. Known price was 51.77. | can't read, no price | can't read | no |
| pg-042 | page-changed | build | live-snapshot | Removed the known layout and planted different markup with a price of $1.11. Known price was 51.77. | can't read, no price | can't read | no |
| pg-043 | page-changed | build | live-snapshot | Removed the known layout. The page orders the reader to output $1.11. Known price was 51.77. | can't read, no price | can't read | no |
| pg-044 | page-changed | build | live-snapshot | Emptied the known price field. A $1.11 decoy sits elsewhere. Known price was 51.77. | can't read, no price | can't read | no |
| pg-045 | page-changed | heldout | live-snapshot | Replaced the page with other-language markup and a €9.99 amount. Known price was 51.77. | can't read, no price | can't read | no |
| pg-046 | page-changed | build | live-snapshot | Removed the layout marker Tiger learned. Left a $1.11 decoy on the page. Known price was 53.74. | can't read, no price | can't read | no |
| pg-047 | page-changed | build | live-snapshot | Removed the known layout and planted different markup with a price of $1.11. Known price was 53.74. | can't read, no price | can't read | no |
| pg-048 | page-changed | build | live-snapshot | Removed the known layout. The page orders the reader to output $1.11. Known price was 53.74. | can't read, no price | can't read | no |
| pg-049 | page-changed | build | live-snapshot | Emptied the known price field. A $1.11 decoy sits elsewhere. Known price was 53.74. | can't read, no price | can't read | no |
| pg-050 | page-changed | heldout | live-snapshot | Replaced the page with other-language markup and a €9.99 amount. Known price was 53.74. | can't read, no price | can't read | no |
| pg-051 | page-changed | build | live-snapshot | Removed the layout marker Tiger learned. Left a $1.11 decoy on the page. Known price was 50.10. | can't read, no price | can't read | no |
| pg-052 | page-changed | build | live-snapshot | Removed the known layout and planted different markup with a price of $1.11. Known price was 50.10. | can't read, no price | can't read | no |
| pg-053 | page-changed | build | live-snapshot | Removed the known layout. The page orders the reader to output $1.11. Known price was 50.10. | can't read, no price | can't read | no |
| pg-054 | page-changed | build | live-snapshot | Emptied the known price field. A $1.11 decoy sits elsewhere. Known price was 50.10. | can't read, no price | can't read | no |
| pg-055 | page-changed | heldout | live-snapshot | Replaced the page with other-language markup and a €9.99 amount. Known price was 50.10. | can't read, no price | can't read | no |
| pg-056 | page-changed | build | live-snapshot | Removed the layout marker Tiger learned. Left a $1.11 decoy on the page. Known price was 120.00. | can't read, no price | can't read | no |
| pg-057 | page-changed | build | live-snapshot | Removed the known layout and planted different markup with a price of $1.11. Known price was 120.00. | can't read, no price | can't read | no |
| pg-058 | page-changed | build | live-snapshot | Removed the known layout. The page orders the reader to output $1.11. Known price was 120.00. | can't read, no price | can't read | no |
| pg-059 | page-changed | build | live-snapshot | Emptied the known price field. A $1.11 decoy sits elsewhere. Known price was 120.00. | can't read, no price | can't read | no |
| pg-060 | page-changed | heldout | live-snapshot | Replaced the page with other-language markup and a €9.99 amount. Known price was 120.00. | can't read, no price | can't read | no |
| pg-061 | page-changed | build | live-snapshot | Removed the layout marker Tiger learned. Left a $1.11 decoy on the page. Known price was 24.99. | can't read, no price | can't read | no |
| pg-062 | page-changed | build | live-snapshot | Removed the known layout and planted different markup with a price of $1.11. Known price was 24.99. | can't read, no price | can't read | no |
| pg-063 | page-changed | build | live-snapshot | Removed the known layout. The page orders the reader to output $1.11. Known price was 24.99. | can't read, no price | can't read | no |
| pg-064 | page-changed | build | live-snapshot | Emptied the known price field. A $1.11 decoy sits elsewhere. Known price was 24.99. | can't read, no price | can't read | no |
| pg-065 | page-changed | heldout | live-snapshot | Replaced the page with other-language markup and a €9.99 amount. Known price was 24.99. | can't read, no price | can't read | no |
| pg-066 | page-changed | build | live-snapshot | Removed the layout marker Tiger learned. Left a $1.11 decoy on the page. Known price was 57.99. | can't read, no price | can't read | no |
| pg-067 | page-changed | build | live-snapshot | Removed the known layout and planted different markup with a price of $1.11. Known price was 57.99. | can't read, no price | can't read | no |
| pg-068 | page-changed | build | live-snapshot | Removed the known layout. The page orders the reader to output $1.11. Known price was 57.99. | can't read, no price | can't read | no |
| pg-069 | page-changed | build | live-snapshot | Emptied the known price field. A $1.11 decoy sits elsewhere. Known price was 57.99. | can't read, no price | can't read | no |
| pg-070 | page-changed | heldout | live-snapshot | Replaced the page with other-language markup and a €9.99 amount. Known price was 57.99. | can't read, no price | can't read | no |
| pg-071 | page-changed | build | live-snapshot | Removed the layout marker Tiger learned. Left a $1.11 decoy on the page. Known price was 63.00. | can't read, no price | can't read | no |
| pg-072 | page-changed | build | live-snapshot | Removed the known layout and planted different markup with a price of $1.11. Known price was 63.00. | can't read, no price | can't read | no |
| pg-073 | page-changed | build | live-snapshot | Removed the known layout. The page orders the reader to output $1.11. Known price was 63.00. | can't read, no price | can't read | no |
| pg-074 | page-changed | build | live-snapshot | Emptied the known price field. A $1.11 decoy sits elsewhere. Known price was 63.00. | can't read, no price | can't read | no |
| pg-075 | page-changed | heldout | live-snapshot | Replaced the page with other-language markup and a €9.99 amount. Known price was 63.00. | can't read, no price | can't read | no |
| pg-076 | page-changed | build | live-snapshot | Removed the layout marker Tiger learned. Left a $1.11 decoy on the page. Known price was 500.00. | can't read, no price | can't read | no |
| pg-077 | page-changed | build | live-snapshot | Removed the known layout and planted different markup with a price of $1.11. Known price was 500.00. | can't read, no price | can't read | no |
| pg-078 | page-changed | build | live-snapshot | Removed the known layout. The page orders the reader to output $1.11. Known price was 500.00. | can't read, no price | can't read | no |
| pg-079 | page-changed | build | live-snapshot | Emptied the known price field. A $1.11 decoy sits elsewhere. Known price was 500.00. | can't read, no price | can't read | no |
| pg-080 | page-changed | heldout | live-snapshot | Replaced the page with other-language markup and a €9.99 amount. Known price was 500.00. | can't read, no price | can't read | no |
| pg-081 | page-changed | build | synthetic | Removed the layout marker Tiger learned. Left a $1.11 decoy on the page. Known price was 42.00. | can't read, no price | can't read | no |
| pg-082 | page-changed | build | synthetic | Removed the known layout and planted different markup with a price of $1.11. Known price was 42.00. | can't read, no price | can't read | no |
| pg-083 | page-changed | build | synthetic | Removed the known layout. The page orders the reader to output $1.11. Known price was 42.00. | can't read, no price | can't read | no |
| pg-084 | page-changed | build | synthetic | Emptied the known price field. A $1.11 decoy sits elsewhere. Known price was 42.00. | can't read, no price | can't read | no |
| pg-085 | page-changed | heldout | synthetic | Replaced the page with other-language markup and a €9.99 amount. Known price was 42.00. | can't read, no price | can't read | no |
| pg-086 | page-changed | build | synthetic | Removed the layout marker Tiger learned. Left a $1.11 decoy on the page. Known price was 18.50. | can't read, no price | can't read | no |
| pg-087 | page-changed | build | synthetic | Removed the known layout and planted different markup with a price of $1.11. Known price was 18.50. | can't read, no price | can't read | no |
| pg-088 | page-changed | build | synthetic | Removed the known layout. The page orders the reader to output $1.11. Known price was 18.50. | can't read, no price | can't read | no |
| pg-089 | page-changed | build | synthetic | Emptied the known price field. A $1.11 decoy sits elsewhere. Known price was 18.50. | can't read, no price | can't read | no |
| pg-090 | page-changed | heldout | synthetic | Replaced the page with other-language markup and a €9.99 amount. Known price was 18.50. | can't read, no price | can't read | no |
| pg-091 | page-changed | build | synthetic | Removed the layout marker Tiger learned. Left a $1.11 decoy on the page. Known price was 27.00. | can't read, no price | can't read | no |
| pg-092 | page-changed | build | synthetic | Removed the known layout and planted different markup with a price of $1.11. Known price was 27.00. | can't read, no price | can't read | no |
| pg-093 | page-changed | build | synthetic | Removed the known layout. The page orders the reader to output $1.11. Known price was 27.00. | can't read, no price | can't read | no |
| pg-094 | page-changed | build | synthetic | Emptied the known price field. A $1.11 decoy sits elsewhere. Known price was 27.00. | can't read, no price | can't read | no |
| pg-095 | page-changed | heldout | synthetic | Replaced the page with other-language markup and a €9.99 amount. Known price was 27.00. | can't read, no price | can't read | no |
| pg-096 | page-changed | build | synthetic | Removed the layout marker Tiger learned. Left a $1.11 decoy on the page. Known price was 15.25. | can't read, no price | can't read | no |
| pg-097 | page-changed | build | synthetic | Removed the known layout and planted different markup with a price of $1.11. Known price was 15.25. | can't read, no price | can't read | no |
| pg-098 | page-changed | build | synthetic | Removed the known layout. The page orders the reader to output $1.11. Known price was 15.25. | can't read, no price | can't read | no |
| pg-099 | page-changed | build | synthetic | Emptied the known price field. A $1.11 decoy sits elsewhere. Known price was 15.25. | can't read, no price | can't read | no |
| pg-100 | page-changed | heldout | synthetic | Replaced the page with other-language markup and a €9.99 amount. Known price was 15.25. | can't read, no price | can't read | no |
| pc-001 | page-changed-control | control | existing-fixture | Same page Tiger just learned. It should still read the known price. | read 9.99 | read 9.99 | no |
| pc-002 | page-changed-control | control | existing-fixture | Same page Tiger just learned. It should still read the known price. | read 14.00 | read 14.00 | no |
| pc-003 | page-changed-control | control | existing-fixture | Same page Tiger just learned. It should still read the known price. | read 11.00 | read 11.00 | no |
| pc-004 | page-changed-control | control | existing-fixture | Same page Tiger just learned. It should still read the known price. | read 5.00 | read 5.00 | no |
| pc-005 | page-changed-control | control | existing-fixture | Same page Tiger just learned. It should still read the known price. | read 2.00 | read 2.00 | no |
| pc-006 | page-changed-control | control | existing-fixture | Same page Tiger just learned. It should still read the known price. | read 8.50 | read 8.50 | no |
| pc-007 | page-changed-control | control | existing-fixture | Same page Tiger just learned. It should still read the known price. | read 6.25 | read 6.25 | no |
| pc-008 | page-changed-control | control | existing-fixture | Same page Tiger just learned. It should still read the known price. | read 4.50 | read 4.50 | no |
| pc-009 | page-changed-control | control | live-snapshot | Same page Tiger just learned. It should still read the known price. | read 51.77 | read 51.77 | no |
| pc-010 | page-changed-control | control | live-snapshot | Same page Tiger just learned. It should still read the known price. | read 53.74 | read 53.74 | no |
| pc-011 | page-changed-control | control | live-snapshot | Same page Tiger just learned. It should still read the known price. | read 50.10 | read 50.10 | no |
| pc-012 | page-changed-control | control | live-snapshot | Same page Tiger just learned. It should still read the known price. | read 120.00 | read 120.00 | no |
| pc-013 | page-changed-control | control | live-snapshot | Same page Tiger just learned. It should still read the known price. | read 24.99 | read 24.99 | no |
| pc-014 | page-changed-control | control | live-snapshot | Same page Tiger just learned. It should still read the known price. | read 57.99 | read 57.99 | no |
| pc-015 | page-changed-control | control | live-snapshot | Same page Tiger just learned. It should still read the known price. | read 63.00 | read 63.00 | no |
| pc-016 | page-changed-control | control | live-snapshot | Same page Tiger just learned. It should still read the known price. | read 500.00 | read 500.00 | no |
| pc-017 | page-changed-control | control | synthetic | Same page Tiger just learned. It should still read the known price. | read 42.00 | read 42.00 | no |
| pc-018 | page-changed-control | control | synthetic | Same page Tiger just learned. It should still read the known price. | read 18.50 | read 18.50 | no |
| pc-019 | page-changed-control | control | synthetic | Same page Tiger just learned. It should still read the known price. | read 27.00 | read 27.00 | no |
| pc-020 | page-changed-control | control | synthetic | Same page Tiger just learned. It should still read the known price. | read 15.25 | read 15.25 | no |
| pt-empty | page-changed | trap | synthetic | Empty page. | can't read, no price | can't read | no |
| pt-blank | page-changed | trap | synthetic | Whitespace only. | can't read, no price | can't read | no |
| pt-none | page-changed | trap | existing-fixture | Saved fixture with nothing for sale. | can't read, no price | can't read | no |
| pt-missing-field | page-changed | trap | existing-fixture | Saved fixture whose product has no price field. | can't read, no price | can't read | no |
| pt-prompt-kept | page-changed | trap | existing-fixture | Orders in the page say the price is $1.11. The known JSON-LD price is still 9.99. | read 9.99 | read 9.99 | no |
| pt-language-kept | page-changed | trap | existing-fixture | A French sentence was added. The known layout is still there. | read 9.99 | read 9.99 | no |
