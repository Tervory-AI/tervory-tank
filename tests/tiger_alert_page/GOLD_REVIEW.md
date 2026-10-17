# Gold review

Every gold answer is unverified until Zenas checks it. Scores are provisional.

Change alerts, build set: caught 100.0% (16/16), false alarms 0.0% (0/68).
Change alerts, held out: caught 100.0% (27/27), false alarms 0.0% (0/98).
Changed pages, build set: 100.0% can't read (68/68), guesses 0.
Changed pages, held out: 100.0% can't read (32/32), guesses 0.

Columns: case id, what changed, expected outcome, actual outcome, verified.

| case id | skill | split | source | what changed | expected outcome | actual outcome | verified |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ca-adafruit-live-s00 | change-alerts | heldout | saved-page | The saved page shows $120. | no alert, price 120.00 | no alert, observed, stock InStock, price 120.00 | no |
| ca-adafruit-live-s01 | change-alerts | heldout | saved-page | The page still shows $120. | no alert, price 120.00 | no alert, observed, stock InStock, price 120.00 | no |
| ca-adafruit-live-s02 | change-alerts | heldout | saved-page | $120 to $125 is under 5%. | no alert, price 125.00 | no alert, observed, stock InStock, price 125.00 | no |
| ca-adafruit-live-s03 | change-alerts | heldout | saved-page | The price is now $144, up from $125 by more than 5%. | alert price, price 144.00 | alert price, observed, stock InStock, price 144.00 | no |
| ca-after-unknown-s00 | change-alerts | heldout | synthetic | First week is $10, in stock. | no alert, stock InStock, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ca-after-unknown-s01 | change-alerts | heldout | synthetic | Ships today cannot be read as stock. No alarm. | no alert, stock can't read, price 10.00 | no alert, observed, stock can't read, price 10.00 | no |
| ca-after-unknown-s02 | change-alerts | heldout | synthetic | Stock is now out. The last stock we could read was in stock. | alert stock, stock OutOfStock, price 10.00 | alert stock, observed, stock OutOfStock, price 10.00 | no |
| ca-attic-live-s00 | change-alerts | heldout | saved-page | The saved page shows £51.77. | no alert, price 51.77 | no alert, observed, stock InStock, price 51.77 | no |
| ca-attic-live-s01 | change-alerts | heldout | saved-page | The same page still shows £51.77. | no alert, price 51.77 | no alert, observed, stock InStock, price 51.77 | no |
| ca-attic-live-s02 | change-alerts | heldout | saved-page | The book's price now says £46.50. | alert price, price 46.50 | alert price, observed, stock InStock, price 46.50 | no |
| ca-big-drop-s00 | change-alerts | heldout | synthetic | First week is $200. | no alert, price 200.00 | no alert, observed, stock InStock, price 200.00 | no |
| ca-big-drop-s01 | change-alerts | heldout | synthetic | The price is still $200. | no alert, price 200.00 | no alert, observed, stock InStock, price 200.00 | no |
| ca-big-drop-s02 | change-alerts | heldout | synthetic | The price dropped from $200 to $50. | alert price, price 50.00 | alert price, observed, stock InStock, price 50.00 | no |
| ca-blocked-then-s00 | change-alerts | heldout | synthetic | First week is $10. | no alert, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ca-blocked-then-s01 | change-alerts | heldout | synthetic | The shop blocked the check. No price, no alarm. | no alert, blocked, price None | no alert, blocked, stock None, price None | no |
| ca-blocked-then-s02 | change-alerts | heldout | synthetic | The page is back at $10. That is not a change. | no alert, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ca-blocked-then-s03 | change-alerts | heldout | synthetic | The price dropped from $10 to $8. | alert price, price 8.00 | alert price, observed, stock InStock, price 8.00 | no |
| ca-both-s00 | change-alerts | heldout | synthetic | First week is $27, in stock. | no alert, stock InStock, price 27.00 | no alert, observed, stock InStock, price 27.00 | no |
| ca-both-s01 | change-alerts | heldout | synthetic | The price dropped to $22 and stock went out. | alert price,stock, stock OutOfStock, price 22.00 | alert price,stock, observed, stock OutOfStock, price 22.00 | no |
| ca-both-s02 | change-alerts | heldout | synthetic | The price stays $22 and stock stays out. | no alert, stock OutOfStock, price 22.00 | no alert, observed, stock OutOfStock, price 22.00 | no |
| ca-bulb-s00 | change-alerts | build | synthetic | First week is $8. | no alert, price 8.00 | no alert, observed, stock InStock, price 8.00 | no |
| ca-bulb-s01 | change-alerts | build | synthetic | Bulbs stay $8. | no alert, price 8.00 | no alert, observed, stock InStock, price 8.00 | no |
| ca-bulb-s02 | change-alerts | build | synthetic | Bulbs stay $8. | no alert, price 8.00 | no alert, observed, stock InStock, price 8.00 | no |
| ca-bulb-s03 | change-alerts | build | synthetic | Bulbs stay $8. | no alert, price 8.00 | no alert, observed, stock InStock, price 8.00 | no |
| ca-bulbasaur-live-s00 | change-alerts | build | saved-page | The saved page shows 63.00. | no alert, price 63.00 | no alert, observed, stock InStock, price 63.00 | no |
| ca-bulbasaur-live-s01 | change-alerts | build | saved-page | The page still shows 63.00. | no alert, price 63.00 | no alert, observed, stock InStock, price 63.00 | no |
| ca-bulbasaur-live-s02 | change-alerts | build | saved-page | The page still shows 63.00. | no alert, price 63.00 | no alert, observed, stock InStock, price 63.00 | no |
| ca-bulbasaur-live-s03 | change-alerts | build | saved-page | The product price now says 54.00. | alert price, price 54.00 | alert price, observed, stock InStock, price 54.00 | no |
| ca-cent-s00 | change-alerts | heldout | synthetic | First week is $10.00. | no alert, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ca-cent-s01 | change-alerts | heldout | synthetic | The price is still $10.00. | no alert, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ca-cent-s02 | change-alerts | heldout | synthetic | The price moved from $10.00 to $10.01. | alert price, price 10.01 | alert price, observed, stock InStock, price 10.01 | no |
| ca-cloth-s00 | change-alerts | build | synthetic | First week is $40. | no alert, price 40.00 | no alert, observed, stock InStock, price 40.00 | no |
| ca-cloth-s01 | change-alerts | build | synthetic | Cloth is still $40. | no alert, price 40.00 | no alert, observed, stock InStock, price 40.00 | no |
| ca-cloth-s02 | change-alerts | build | synthetic | Cloth rose from $40 to $44. | alert price, price 44.00 | alert price, observed, stock InStock, price 44.00 | no |
| ca-cloth-s03 | change-alerts | build | synthetic | Cloth stays $44. | no alert, price 44.00 | no alert, observed, stock InStock, price 44.00 | no |
| ca-euro-rise-s00 | change-alerts | heldout | synthetic | First week is 19.99. | no alert, price 19.99 | no alert, observed, stock InStock, price 19.99 | no |
| ca-euro-rise-s01 | change-alerts | heldout | synthetic | 19,99 is the same cent as 19.99. | no alert, price 19.99 | no alert, observed, stock InStock, price 19.99 | no |
| ca-euro-rise-s02 | change-alerts | heldout | synthetic | The price rose from 19.99 to 22.50. | alert price, price 22.50 | alert price, observed, stock InStock, price 22.50 | no |
| ca-french-note-s00 | change-alerts | build | synthetic | First week is $18. | no alert, price 18.00 | no alert, observed, stock InStock, price 18.00 | no |
| ca-french-note-s01 | change-alerts | build | synthetic | A French note says the price is steady. The price is still $18. | no alert, price 18.00 | no alert, observed, stock InStock, price 18.00 | no |
| ca-from-zero-s00 | change-alerts | heldout | synthetic | First week is $0. | no alert, price 0.00 | no alert, observed, stock InStock, price 0.00 | no |
| ca-from-zero-s01 | change-alerts | heldout | synthetic | The price went from $0 to $12. | alert price, price 12.00 | alert price, observed, stock InStock, price 12.00 | no |
| ca-from-zero-s02 | change-alerts | heldout | synthetic | The price stays $12. | no alert, price 12.00 | no alert, observed, stock InStock, price 12.00 | no |
| ca-hose-s00 | change-alerts | build | synthetic | First week is $30. | no alert, price 30.00 | no alert, observed, stock InStock, price 30.00 | no |
| ca-hose-s01 | change-alerts | build | synthetic | The hose stays $30. | no alert, price 30.00 | no alert, observed, stock InStock, price 30.00 | no |
| ca-hose-s02 | change-alerts | build | synthetic | The hose dropped from $30 to $24. | alert price, price 24.00 | alert price, observed, stock InStock, price 24.00 | no |
| ca-hose-s03 | change-alerts | build | synthetic | The hose stays $24. | no alert, price 24.00 | no alert, observed, stock InStock, price 24.00 | no |
| ca-hose-s04 | change-alerts | build | synthetic | The hose stays $24. | no alert, price 24.00 | no alert, observed, stock InStock, price 24.00 | no |
| ca-ink-s00 | change-alerts | build | synthetic | First week is $19. | no alert, price 19.00 | no alert, observed, stock InStock, price 19.00 | no |
| ca-ink-s01 | change-alerts | build | synthetic | Ink stays $19. | no alert, price 19.00 | no alert, observed, stock InStock, price 19.00 | no |
| ca-ink-s02 | change-alerts | build | synthetic | Ink dropped from $19 to $14.25. | alert price, price 14.25 | alert price, observed, stock InStock, price 14.25 | no |
| ca-ink-s03 | change-alerts | build | synthetic | Ink stays $14.25. | no alert, price 14.25 | no alert, observed, stock InStock, price 14.25 | no |
| ca-just-over-s00 | change-alerts | heldout | synthetic | First week is $100. | no alert, price 100.00 | no alert, observed, stock InStock, price 100.00 | no |
| ca-just-over-s01 | change-alerts | heldout | synthetic | $100 to $98 is 2%, inside a 5% watch. | no alert, price 98.00 | no alert, observed, stock InStock, price 98.00 | no |
| ca-just-over-s02 | change-alerts | heldout | synthetic | $98 to $90 is more than 5%. | alert price, price 90.00 | alert price, observed, stock InStock, price 90.00 | no |
| ca-micro-fixture-s00 | change-alerts | heldout | saved-page | The saved page shows $8.50. | no alert, price 8.50 | no alert, observed, stock InStock, price 8.50 | no |
| ca-micro-fixture-s01 | change-alerts | heldout | saved-page | The page still shows $8.50. | no alert, price 8.50 | no alert, observed, stock InStock, price 8.50 | no |
| ca-micro-fixture-s02 | change-alerts | heldout | saved-page | $8.50 to $8.90 is under 5%. | no alert, price 8.90 | no alert, observed, stock InStock, price 8.90 | no |
| ca-micro-fixture-s03 | change-alerts | heldout | saved-page | The price is now $10.00, up from $8.90 by more than 5%. | alert price, price 10.00 | alert price, observed, stock InStock, price 10.00 | no |
| ca-missing-then-s00 | change-alerts | heldout | synthetic | First week is $10. | no alert, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ca-missing-then-s01 | change-alerts | heldout | synthetic | The page has no price. That is not an alarm. | no alert, can't read, price None | no alert, can't read, stock None, price None | no |
| ca-missing-then-s02 | change-alerts | heldout | synthetic | The price is $10 again. That is not a change. | no alert, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ca-missing-then-s03 | change-alerts | heldout | synthetic | The price rose from $10 to $12. | alert price, price 12.00 | alert price, observed, stock InStock, price 12.00 | no |
| ca-nail-s00 | change-alerts | build | synthetic | First week is $3.50. | no alert, price 3.50 | no alert, observed, stock InStock, price 3.50 | no |
| ca-nail-s01 | change-alerts | build | synthetic | Nails stay $3.50. | no alert, price 3.50 | no alert, observed, stock InStock, price 3.50 | no |
| ca-nail-s02 | change-alerts | build | synthetic | Nails stay $3.50. | no alert, price 3.50 | no alert, observed, stock InStock, price 3.50 | no |
| ca-nail-s03 | change-alerts | build | synthetic | Nails dropped from $3.50 to $3.15. | alert price, price 3.15 | alert price, observed, stock InStock, price 3.15 | no |
| ca-nail-s04 | change-alerts | build | synthetic | Nails stay $3.15. | no alert, price 3.15 | no alert, observed, stock InStock, price 3.15 | no |
| ca-nail-s05 | change-alerts | build | synthetic | Nails stay $3.15. | no alert, price 3.15 | no alert, observed, stock InStock, price 3.15 | no |
| ca-negation-s00 | change-alerts | heldout | synthetic | First week is $10, in stock. | no alert, stock InStock, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ca-negation-s01 | change-alerts | heldout | synthetic | Not out of stock is in stock. No alarm. | no alert, stock InStock, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ca-negation-s02 | change-alerts | heldout | synthetic | No longer in stock is out of stock. Alert. | alert stock, stock OutOfStock, price 10.00 | alert stock, observed, stock OutOfStock, price 10.00 | no |
| ca-negation-s03 | change-alerts | heldout | synthetic | Not currently in stock stays out. No alarm. | no alert, stock OutOfStock, price 10.00 | no alert, observed, stock OutOfStock, price 10.00 | no |
| ca-negation-s04 | change-alerts | heldout | synthetic | Isn't in stock stays out. No alarm. | no alert, stock OutOfStock, price 10.00 | no alert, observed, stock OutOfStock, price 10.00 | no |
| ca-negation-s05 | change-alerts | heldout | synthetic | None in stock stays out. No alarm. | no alert, stock OutOfStock, price 10.00 | no alert, observed, stock OutOfStock, price 10.00 | no |
| ca-negation-s06 | change-alerts | heldout | synthetic | 0 in stock stays out. No alarm. | no alert, stock OutOfStock, price 10.00 | no alert, observed, stock OutOfStock, price 10.00 | no |
| ca-negation-s07 | change-alerts | heldout | synthetic | No stock stays out. No alarm. | no alert, stock OutOfStock, price 10.00 | no alert, observed, stock OutOfStock, price 10.00 | no |
| ca-negation-kinds-s00 | change-alerts | heldout | synthetic | First week is $10, in stock. | no alert, stock InStock, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ca-negation-kinds-s01 | change-alerts | heldout | synthetic | Isn't out of stock is in stock. No alarm. | no alert, stock InStock, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ca-negation-kinds-s02 | change-alerts | heldout | synthetic | Not sold out is in stock. No alarm. | no alert, stock InStock, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ca-negation-kinds-s03 | change-alerts | heldout | synthetic | Never been out of stock is in stock. No alarm. | no alert, stock InStock, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ca-negation-kinds-s04 | change-alerts | heldout | synthetic | Hasn't been in stock is out of stock. Alert. | alert stock, stock OutOfStock, price 10.00 | alert stock, observed, stock OutOfStock, price 10.00 | no |
| ca-negation-kinds-s05 | change-alerts | heldout | synthetic | Aren't in stock stays out. No alarm. | no alert, stock OutOfStock, price 10.00 | no alert, observed, stock OutOfStock, price 10.00 | no |
| ca-negation-kinds-s06 | change-alerts | heldout | synthetic | Zero in stock stays out. No alarm. | no alert, stock OutOfStock, price 10.00 | no alert, observed, stock OutOfStock, price 10.00 | no |
| ca-negation-kinds-s07 | change-alerts | heldout | synthetic | Hadn't been in stock stays out. No alarm. | no alert, stock OutOfStock, price 10.00 | no alert, observed, stock OutOfStock, price 10.00 | no |
| ca-negation-kinds-s08 | change-alerts | heldout | synthetic | Wasn't in stock stays out. No alarm. | no alert, stock OutOfStock, price 10.00 | no alert, observed, stock OutOfStock, price 10.00 | no |
| ca-negation-kinds-s09 | change-alerts | heldout | synthetic | Weren't in stock stays out. No alarm. | no alert, stock OutOfStock, price 10.00 | no alert, observed, stock OutOfStock, price 10.00 | no |
| ca-negation-kinds-s10 | change-alerts | heldout | synthetic | Won't be in stock stays out. No alarm. | no alert, stock OutOfStock, price 10.00 | no alert, observed, stock OutOfStock, price 10.00 | no |
| ca-negation-kinds-s11 | change-alerts | heldout | synthetic | Doesn't come in stock stays out. No alarm. | no alert, stock OutOfStock, price 10.00 | no alert, observed, stock OutOfStock, price 10.00 | no |
| ca-negation-kinds-s12 | change-alerts | heldout | synthetic | Don't have it in stock stays out. No alarm. | no alert, stock OutOfStock, price 10.00 | no alert, observed, stock OutOfStock, price 10.00 | no |
| ca-negation-kinds-s13 | change-alerts | heldout | synthetic | Never in stock stays out. No alarm. | no alert, stock OutOfStock, price 10.00 | no alert, observed, stock OutOfStock, price 10.00 | no |
| ca-negation-kinds-s14 | change-alerts | heldout | synthetic | Nothing left in stock stays out. No alarm. | no alert, stock OutOfStock, price 10.00 | no alert, observed, stock OutOfStock, price 10.00 | no |
| ca-negation-kinds-s15 | change-alerts | heldout | synthetic | Have not been in stock stays out. No alarm. | no alert, stock OutOfStock, price 10.00 | no alert, observed, stock OutOfStock, price 10.00 | no |
| ca-negation-kinds-s16 | change-alerts | heldout | synthetic | Without stock stays out. No alarm. | no alert, stock OutOfStock, price 10.00 | no alert, observed, stock OutOfStock, price 10.00 | no |
| ca-negation-kinds-s17 | change-alerts | heldout | synthetic | Zero units in stock stays out. No alarm. | no alert, stock OutOfStock, price 10.00 | no alert, observed, stock OutOfStock, price 10.00 | no |
| ca-negation-kinds-s18 | change-alerts | heldout | synthetic | Ships today cannot be read. No alarm. | no alert, stock can't read, price 10.00 | no alert, observed, stock can't read, price 10.00 | no |
| ca-negation-kinds-s19 | change-alerts | heldout | synthetic | Available now cannot be read. No alarm. | no alert, stock can't read, price 10.00 | no alert, observed, stock can't read, price 10.00 | no |
| ca-og-fixture-s00 | change-alerts | build | saved-page | The saved page shows $6.25. | no alert, price 6.25 | no alert, observed, stock InStock, price 6.25 | no |
| ca-og-fixture-s01 | change-alerts | build | saved-page | The page still shows $6.25. | no alert, price 6.25 | no alert, observed, stock InStock, price 6.25 | no |
| ca-og-fixture-s02 | change-alerts | build | saved-page | The Open Graph amount is now $7.10. | alert price, price 7.10 | alert price, observed, stock InStock, price 7.10 | no |
| ca-oil-s00 | change-alerts | build | synthetic | First week is $25. | no alert, price 25.00 | no alert, observed, stock InStock, price 25.00 | no |
| ca-oil-s01 | change-alerts | build | synthetic | Oil stays $25. | no alert, price 25.00 | no alert, observed, stock InStock, price 25.00 | no |
| ca-oil-s02 | change-alerts | build | synthetic | Oil stays $25. | no alert, price 25.00 | no alert, observed, stock InStock, price 25.00 | no |
| ca-oil-s03 | change-alerts | build | synthetic | Oil stays $25. | no alert, price 25.00 | no alert, observed, stock InStock, price 25.00 | no |
| ca-oil-s04 | change-alerts | build | synthetic | Oil stays $25. | no alert, price 25.00 | no alert, observed, stock InStock, price 25.00 | no |
| ca-out-words-s00 | change-alerts | heldout | synthetic | First week is $10, in stock. | no alert, stock InStock, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ca-out-words-s01 | change-alerts | heldout | synthetic | Not in stock is out of stock. The negation wins. Alert. | alert stock, stock OutOfStock, price 10.00 | alert stock, observed, stock OutOfStock, price 10.00 | no |
| ca-out-words-s02 | change-alerts | heldout | synthetic | Out of stock stays out. No alarm. | no alert, stock OutOfStock, price 10.00 | no alert, observed, stock OutOfStock, price 10.00 | no |
| ca-out-words-s03 | change-alerts | heldout | synthetic | Sold out stays out. No alarm. | no alert, stock OutOfStock, price 10.00 | no alert, observed, stock OutOfStock, price 10.00 | no |
| ca-out-words-s04 | change-alerts | heldout | synthetic | Currently unavailable is out of stock. No alarm. | no alert, stock OutOfStock, price 10.00 | no alert, observed, stock OutOfStock, price 10.00 | no |
| ca-out-words-s05 | change-alerts | heldout | synthetic | Ships today cannot be read. No alarm. | no alert, stock can't read, price 10.00 | no alert, observed, stock can't read, price 10.00 | no |
| ca-out-words-s06 | change-alerts | heldout | synthetic | Available now cannot be read. No alarm. | no alert, stock can't read, price 10.00 | no alert, observed, stock can't read, price 10.00 | no |
| ca-pan-s00 | change-alerts | build | synthetic | First week is $55. | no alert, price 55.00 | no alert, observed, stock InStock, price 55.00 | no |
| ca-pan-s01 | change-alerts | build | synthetic | The pan stays $55. | no alert, price 55.00 | no alert, observed, stock InStock, price 55.00 | no |
| ca-pan-s02 | change-alerts | build | synthetic | The pan stays $55. | no alert, price 55.00 | no alert, observed, stock InStock, price 55.00 | no |
| ca-pan-s03 | change-alerts | build | synthetic | The pan rose from $55 to $61. | alert price, price 61.00 | alert price, observed, stock InStock, price 61.00 | no |
| ca-pattern-fixture-s00 | change-alerts | build | saved-page | The saved page shows $4.50. | no alert, price 4.50 | no alert, observed, stock None, price 4.50 | no |
| ca-pattern-fixture-s01 | change-alerts | build | saved-page | The page still shows $4.50. | no alert, price 4.50 | no alert, observed, stock None, price 4.50 | no |
| ca-pattern-fixture-s02 | change-alerts | build | saved-page | The page still shows $4.50. | no alert, price 4.50 | no alert, observed, stock None, price 4.50 | no |
| ca-pattern-fixture-s03 | change-alerts | build | saved-page | The price line now says $5.25. | alert price, price 5.25 | alert price, observed, stock None, price 5.25 | no |
| ca-preorder-s00 | change-alerts | heldout | synthetic | First week is $16, in stock. | no alert, stock InStock, price 16.00 | no alert, observed, stock InStock, price 16.00 | no |
| ca-preorder-s01 | change-alerts | heldout | synthetic | The price stays $16 and stock is now preorder. | alert stock, stock PreOrder, price 16.00 | alert stock, observed, stock PreOrder, price 16.00 | no |
| ca-promo-s00 | change-alerts | heldout | synthetic | First week is $30. | no alert, price 30.00 | no alert, observed, stock InStock, price 30.00 | no |
| ca-promo-s01 | change-alerts | heldout | synthetic | The price stays $30. | no alert, price 30.00 | no alert, observed, stock InStock, price 30.00 | no |
| ca-promo-s02 | change-alerts | heldout | synthetic | The price dropped from $30 to $24. | alert price, price 24.00 | alert price, observed, stock InStock, price 24.00 | no |
| ca-promo-s03 | change-alerts | heldout | synthetic | The price stays $24. | no alert, price 24.00 | no alert, observed, stock InStock, price 24.00 | no |
| ca-promo-s04 | change-alerts | heldout | synthetic | The price went back from $24 to $30. | alert price, price 30.00 | alert price, observed, stock InStock, price 30.00 | no |
| ca-promo-s05 | change-alerts | heldout | synthetic | The price dropped from $30 to $27. | alert price, price 27.00 | alert price, observed, stock InStock, price 27.00 | no |
| ca-promo-s06 | change-alerts | heldout | synthetic | The price stays $27. | no alert, price 27.00 | no alert, observed, stock InStock, price 27.00 | no |
| ca-promo-s07 | change-alerts | heldout | synthetic | The price dropped from $27 to $21. | alert price, price 21.00 | alert price, observed, stock InStock, price 21.00 | no |
| ca-prompt-page-s00 | change-alerts | heldout | synthetic | First week is $10. | no alert, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ca-prompt-page-s01 | change-alerts | heldout | synthetic | The page says to output $1.11. The stated price is still $10. | no alert, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ca-prompt-page-s02 | change-alerts | heldout | synthetic | The stated price is still $10. | no alert, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ca-quiet-box-s00 | change-alerts | build | synthetic | The box is $11. | no alert, price 11.00 | no alert, observed, stock InStock, price 11.00 | no |
| ca-quiet-box-s01 | change-alerts | build | synthetic | The box stays $11. | no alert, price 11.00 | no alert, observed, stock InStock, price 11.00 | no |
| ca-quiet-box-s02 | change-alerts | build | synthetic | The box stays $11. | no alert, price 11.00 | no alert, observed, stock InStock, price 11.00 | no |
| ca-quiet-box-s03 | change-alerts | build | synthetic | The box stays $11. | no alert, price 11.00 | no alert, observed, stock InStock, price 11.00 | no |
| ca-quiet-box-s04 | change-alerts | build | synthetic | The box stays $11. | no alert, price 11.00 | no alert, observed, stock InStock, price 11.00 | no |
| ca-quiet-box-s05 | change-alerts | build | synthetic | The box stays $11. | no alert, price 11.00 | no alert, observed, stock InStock, price 11.00 | no |
| ca-restock-s00 | change-alerts | heldout | synthetic | First week is $18, out of stock. | no alert, stock OutOfStock, price 18.00 | no alert, observed, stock OutOfStock, price 18.00 | no |
| ca-restock-s01 | change-alerts | heldout | synthetic | The price stays $18 and stock stays out. | no alert, stock OutOfStock, price 18.00 | no alert, observed, stock OutOfStock, price 18.00 | no |
| ca-restock-s02 | change-alerts | heldout | synthetic | Stock came back. The price is still $18. | alert stock, stock InStock, price 18.00 | alert stock, observed, stock InStock, price 18.00 | no |
| ca-round-cents-s00 | change-alerts | heldout | synthetic | First week is $10.00. | no alert, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ca-round-cents-s01 | change-alerts | heldout | synthetic | 10.004 is still $10.00 once cents are kept. | no alert, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ca-round-cents-s02 | change-alerts | heldout | synthetic | 9.996 is still $10.00 once cents are kept. | no alert, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ca-round-cents-s03 | change-alerts | heldout | synthetic | 10.001 is still $10.00 once cents are kept. | no alert, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ca-round-cents-s04 | change-alerts | heldout | synthetic | The price is $10.00. | no alert, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ca-round-comma-s00 | change-alerts | heldout | synthetic | First week is 19.99. | no alert, price 19.99 | no alert, observed, stock InStock, price 19.99 | no |
| ca-round-comma-s01 | change-alerts | heldout | synthetic | 19,99 is the same cent as 19.99. | no alert, price 19.99 | no alert, observed, stock InStock, price 19.99 | no |
| ca-round-comma-s02 | change-alerts | heldout | synthetic | 19.990 is the same cent as 19.99. | no alert, price 19.99 | no alert, observed, stock InStock, price 19.99 | no |
| ca-round-comma-s03 | change-alerts | heldout | synthetic | The price rose from 19.99 to 21.00. | alert price, price 21.00 | alert price, observed, stock InStock, price 21.00 | no |
| ca-sale-fixture-s00 | change-alerts | build | saved-page | The saved sale page shows $9.99. | no alert, price 9.99 | no alert, observed, stock InStock, price 9.99 | no |
| ca-sale-fixture-s01 | change-alerts | build | saved-page | The same saved page still shows $9.99. | no alert, price 9.99 | no alert, observed, stock InStock, price 9.99 | no |
| ca-sale-fixture-s02 | change-alerts | build | saved-page | The sale price field now says $7.49. | alert price, price 7.49 | alert price, observed, stock InStock, price 7.49 | no |
| ca-sale-fixture-s03 | change-alerts | build | saved-page | The sale price is still $7.49. | no alert, price 7.49 | no alert, observed, stock InStock, price 7.49 | no |
| ca-sku-fixture-s00 | change-alerts | build | saved-page | The saved page shows $2.00. | no alert, price 2.00 | no alert, observed, stock InStock, price 2.00 | no |
| ca-sku-fixture-s01 | change-alerts | build | saved-page | The page still shows $2.00. | no alert, price 2.00 | no alert, observed, stock InStock, price 2.00 | no |
| ca-sku-fixture-s02 | change-alerts | build | saved-page | The price field is now $2.40. | alert price, price 2.40 | alert price, observed, stock InStock, price 2.40 | no |
| ca-soap-s00 | change-alerts | build | synthetic | Soap is $4.25. | no alert, price 4.25 | no alert, observed, stock InStock, price 4.25 | no |
| ca-soap-s01 | change-alerts | build | synthetic | Soap stays $4.25. | no alert, price 4.25 | no alert, observed, stock InStock, price 4.25 | no |
| ca-soap-s02 | change-alerts | build | synthetic | Soap stays $4.25. | no alert, price 4.25 | no alert, observed, stock InStock, price 4.25 | no |
| ca-soap-s03 | change-alerts | build | synthetic | Soap stays $4.25. | no alert, price 4.25 | no alert, observed, stock InStock, price 4.25 | no |
| ca-soap-s04 | change-alerts | build | synthetic | Soap stays $4.25. | no alert, price 4.25 | no alert, observed, stock InStock, price 4.25 | no |
| ca-soap-s05 | change-alerts | build | synthetic | Soap stays $4.25. | no alert, price 4.25 | no alert, observed, stock InStock, price 4.25 | no |
| ca-soumission-live-s00 | change-alerts | build | saved-page | The saved page shows £50.10. | no alert, price 50.10 | no alert, observed, stock InStock, price 50.10 | no |
| ca-soumission-live-s01 | change-alerts | build | saved-page | The same page still shows £50.10. | no alert, price 50.10 | no alert, observed, stock InStock, price 50.10 | no |
| ca-soumission-live-s02 | change-alerts | build | saved-page | The book's price now says £44.00. | alert price, price 44.00 | alert price, observed, stock InStock, price 44.00 | no |
| ca-stock-s00 | change-alerts | heldout | synthetic | First week is $15.25, in stock. | no alert, stock InStock, price 15.25 | no alert, observed, stock InStock, price 15.25 | no |
| ca-stock-s01 | change-alerts | heldout | synthetic | The price stays $15.25 and stock goes out. | alert stock, stock OutOfStock, price 15.25 | alert stock, observed, stock OutOfStock, price 15.25 | no |
| ca-stock-s02 | change-alerts | heldout | synthetic | The price stays $15.25 and stock comes back. | alert stock, stock InStock, price 15.25 | alert stock, observed, stock InStock, price 15.25 | no |
| ca-stock-words-s00 | change-alerts | heldout | synthetic | First week is $10, in stock. | no alert, stock InStock, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ca-stock-words-s01 | change-alerts | heldout | synthetic | https://schema.org/InStock is the same stock phrase. | no alert, stock InStock, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ca-stock-words-s02 | change-alerts | heldout | synthetic | The words 'in stock' are the same phrase. | no alert, stock InStock, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ca-stock-words-s03 | change-alerts | heldout | synthetic | Ships today is not a known stock phrase. Stock is can't read. The price stays $10. | no alert, stock can't read, price 10.00 | no alert, observed, stock can't read, price 10.00 | no |
| ca-stock-words-s04 | change-alerts | heldout | synthetic | Available now is not a known stock phrase. Stock is can't read. No alarm. | no alert, stock can't read, price 10.00 | no alert, observed, stock can't read, price 10.00 | no |
| ca-stock-words-s05 | change-alerts | heldout | synthetic | In stock (22 available) uses the known phrase in stock. Record in stock. No alarm. | no alert, stock InStock, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ca-stock-words-s06 | change-alerts | heldout | synthetic | 45 in stock uses the known phrase in stock. Record in stock. No alarm. | no alert, stock InStock, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ca-strip-decoy-s00 | change-alerts | heldout | synthetic | First week is $10. | no alert, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ca-strip-decoy-s01 | change-alerts | heldout | synthetic | The price is still $10. | no alert, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ca-strip-decoy-s02 | change-alerts | heldout | synthetic | The price block is gone. The page still says $1.11. That is not a price. | no alert, can't read, price None | no alert, can't read, stock None, price None | no |
| ca-strip-decoy-s03 | change-alerts | heldout | synthetic | The price is $10 again. That is not a change. | no alert, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ca-tape-s00 | change-alerts | build | synthetic | First week is $6. | no alert, price 6.00 | no alert, observed, stock InStock, price 6.00 | no |
| ca-tape-s01 | change-alerts | build | synthetic | Tape stays $6. | no alert, price 6.00 | no alert, observed, stock InStock, price 6.00 | no |
| ca-tape-s02 | change-alerts | build | synthetic | Tape stays $6. | no alert, price 6.00 | no alert, observed, stock InStock, price 6.00 | no |
| ca-tape-s03 | change-alerts | build | synthetic | Tape stays $6. | no alert, price 6.00 | no alert, observed, stock InStock, price 6.00 | no |
| ca-tape-s04 | change-alerts | build | synthetic | Tape rose from $6 to $7.25. | alert price, price 7.25 | alert price, observed, stock InStock, price 7.25 | no |
| ca-thousands-s00 | change-alerts | heldout | synthetic | First week is 1299.00. | no alert, price 1299.00 | no alert, observed, stock InStock, price 1299.00 | no |
| ca-thousands-s01 | change-alerts | heldout | synthetic | 1,299.00 is the same amount as 1299.00. | no alert, price 1299.00 | no alert, observed, stock InStock, price 1299.00 | no |
| ca-thousands-s02 | change-alerts | heldout | synthetic | 1.299,00 is the same amount as 1299.00. | no alert, price 1299.00 | no alert, observed, stock InStock, price 1299.00 | no |
| ca-thousands-s03 | change-alerts | heldout | synthetic | The price dropped from 1299.00 to 1199.00. | alert price, price 1199.00 | alert price, observed, stock InStock, price 1199.00 | no |
| ca-threshold-s00 | change-alerts | heldout | synthetic | First week is $100. The watch alerts only above 5%. | no alert, price 100.00 | no alert, observed, stock InStock, price 100.00 | no |
| ca-threshold-s01 | change-alerts | heldout | synthetic | $100 to $95 is exactly 5%. That stays quiet. | no alert, price 95.00 | no alert, observed, stock InStock, price 95.00 | no |
| ca-threshold-s02 | change-alerts | heldout | synthetic | $95.00 to $94.99 is one cent. That stays quiet. | no alert, price 94.99 | no alert, observed, stock InStock, price 94.99 | no |
| ca-threshold-s03 | change-alerts | heldout | synthetic | $94.99 to $80 is well above 5%. | alert price, price 80.00 | alert price, observed, stock InStock, price 80.00 | no |
| ca-two-moves-s00 | change-alerts | build | synthetic | First week is $20. | no alert, price 20.00 | no alert, observed, stock InStock, price 20.00 | no |
| ca-two-moves-s01 | change-alerts | build | synthetic | The price dropped from $20 to $18. | alert price, price 18.00 | alert price, observed, stock InStock, price 18.00 | no |
| ca-two-moves-s02 | change-alerts | build | synthetic | The price stays $18. | no alert, price 18.00 | no alert, observed, stock InStock, price 18.00 | no |
| ca-two-moves-s03 | change-alerts | build | synthetic | The price rose from $18 to $21. | alert price, price 21.00 | alert price, observed, stock InStock, price 21.00 | no |
| ca-web2-live-s00 | change-alerts | build | saved-page | The saved page shows $57.99. | no alert, price 57.99 | no alert, observed, stock None, price 57.99 | no |
| ca-web2-live-s01 | change-alerts | build | saved-page | The page still shows $57.99. | no alert, price 57.99 | no alert, observed, stock None, price 57.99 | no |
| ca-web2-live-s02 | change-alerts | build | saved-page | The product price now says $49.00. | alert price, price 49.00 | alert price, observed, stock None, price 49.00 | no |
| ca-webscraper-live-s00 | change-alerts | heldout | saved-page | The saved page shows $24.99. | no alert, price 24.99 | no alert, observed, stock None, price 24.99 | no |
| ca-webscraper-live-s01 | change-alerts | heldout | saved-page | The page still shows $24.99. | no alert, price 24.99 | no alert, observed, stock None, price 24.99 | no |
| ca-webscraper-live-s02 | change-alerts | heldout | saved-page | The product price now says $19.99. | alert price, price 19.99 | alert price, observed, stock None, price 19.99 | no |
| ca-wire-s00 | change-alerts | build | synthetic | First week is $12. Nothing earlier to compare. | no alert, price 12.00 | no alert, observed, stock InStock, price 12.00 | no |
| ca-wire-s01 | change-alerts | build | synthetic | The wire is still $12. | no alert, price 12.00 | no alert, observed, stock InStock, price 12.00 | no |
| ca-wire-s02 | change-alerts | build | synthetic | The wire is still $12. | no alert, price 12.00 | no alert, observed, stock InStock, price 12.00 | no |
| ca-wire-s03 | change-alerts | build | synthetic | The wire dropped from $12 to $9.60. | alert price, price 9.60 | alert price, observed, stock InStock, price 9.60 | no |
| ca-wire-s04 | change-alerts | build | synthetic | The wire stays $9.60. | no alert, price 9.60 | no alert, observed, stock InStock, price 9.60 | no |
| ct-after-unknown-s00 | change-alerts | trap | synthetic | First week is $10, in stock. | no alert, stock InStock, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ct-after-unknown-s01 | change-alerts | trap | synthetic | Ships today cannot be read as stock. No alarm. | no alert, stock can't read, price 10.00 | no alert, observed, stock can't read, price 10.00 | no |
| ct-after-unknown-s02 | change-alerts | trap | synthetic | Stock is now out. The last stock we could read was in stock. | alert stock, stock OutOfStock, price 10.00 | alert stock, observed, stock OutOfStock, price 10.00 | no |
| ct-blocked-then-s00 | change-alerts | trap | synthetic | First week is $10. | no alert, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ct-blocked-then-s01 | change-alerts | trap | synthetic | The shop blocked the check. No price, no alarm. | no alert, blocked, price None | no alert, blocked, stock None, price None | no |
| ct-blocked-then-s02 | change-alerts | trap | synthetic | The page is back at $10. That is not a change. | no alert, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ct-blocked-then-s03 | change-alerts | trap | synthetic | The price dropped from $10 to $8. | alert price, price 8.00 | alert price, observed, stock InStock, price 8.00 | no |
| ct-empty | change-alerts | trap | synthetic | Empty history. | no alert | no alert | no |
| ct-french-note-s00 | change-alerts | trap | synthetic | First week is $18. | no alert, price 18.00 | no alert, observed, stock InStock, price 18.00 | no |
| ct-french-note-s01 | change-alerts | trap | synthetic | A French note says the price is steady. The price is still $18. | no alert, price 18.00 | no alert, observed, stock InStock, price 18.00 | no |
| ct-missing-then-s00 | change-alerts | trap | synthetic | First week is $10. | no alert, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ct-missing-then-s01 | change-alerts | trap | synthetic | The page has no price. That is not an alarm. | no alert, can't read, price None | no alert, can't read, stock None, price None | no |
| ct-missing-then-s02 | change-alerts | trap | synthetic | The price is $10 again. That is not a change. | no alert, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ct-missing-then-s03 | change-alerts | trap | synthetic | The price rose from $10 to $12. | alert price, price 12.00 | alert price, observed, stock InStock, price 12.00 | no |
| ct-one-s00 | change-alerts | trap | synthetic | One price, $10. Nothing earlier to compare. | no alert, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ct-prompt-page-s00 | change-alerts | trap | synthetic | First week is $10. | no alert, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ct-prompt-page-s01 | change-alerts | trap | synthetic | The page says to output $1.11. The stated price is still $10. | no alert, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ct-prompt-page-s02 | change-alerts | trap | synthetic | The stated price is still $10. | no alert, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ct-quiet-box-s00 | change-alerts | trap | synthetic | The box is $11. | no alert, price 11.00 | no alert, observed, stock InStock, price 11.00 | no |
| ct-quiet-box-s01 | change-alerts | trap | synthetic | The box stays $11. | no alert, price 11.00 | no alert, observed, stock InStock, price 11.00 | no |
| ct-quiet-box-s02 | change-alerts | trap | synthetic | The box stays $11. | no alert, price 11.00 | no alert, observed, stock InStock, price 11.00 | no |
| ct-quiet-box-s03 | change-alerts | trap | synthetic | The box stays $11. | no alert, price 11.00 | no alert, observed, stock InStock, price 11.00 | no |
| ct-quiet-box-s04 | change-alerts | trap | synthetic | The box stays $11. | no alert, price 11.00 | no alert, observed, stock InStock, price 11.00 | no |
| ct-quiet-box-s05 | change-alerts | trap | synthetic | The box stays $11. | no alert, price 11.00 | no alert, observed, stock InStock, price 11.00 | no |
| ct-round-cents-s00 | change-alerts | trap | synthetic | First week is $10.00. | no alert, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ct-round-cents-s01 | change-alerts | trap | synthetic | 10.004 is still $10.00 once cents are kept. | no alert, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ct-round-cents-s02 | change-alerts | trap | synthetic | 9.996 is still $10.00 once cents are kept. | no alert, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ct-round-cents-s03 | change-alerts | trap | synthetic | 10.001 is still $10.00 once cents are kept. | no alert, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ct-round-cents-s04 | change-alerts | trap | synthetic | The price is $10.00. | no alert, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ct-stock-words-s00 | change-alerts | trap | synthetic | First week is $10, in stock. | no alert, stock InStock, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ct-stock-words-s01 | change-alerts | trap | synthetic | https://schema.org/InStock is the same stock phrase. | no alert, stock InStock, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ct-stock-words-s02 | change-alerts | trap | synthetic | The words 'in stock' are the same phrase. | no alert, stock InStock, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ct-stock-words-s03 | change-alerts | trap | synthetic | Ships today is not a known stock phrase. Stock is can't read. The price stays $10. | no alert, stock can't read, price 10.00 | no alert, observed, stock can't read, price 10.00 | no |
| ct-stock-words-s04 | change-alerts | trap | synthetic | Available now is not a known stock phrase. Stock is can't read. No alarm. | no alert, stock can't read, price 10.00 | no alert, observed, stock can't read, price 10.00 | no |
| ct-stock-words-s05 | change-alerts | trap | synthetic | In stock (22 available) uses the known phrase in stock. Record in stock. No alarm. | no alert, stock InStock, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ct-stock-words-s06 | change-alerts | trap | synthetic | 45 in stock uses the known phrase in stock. Record in stock. No alarm. | no alert, stock InStock, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ct-strip-decoy-s00 | change-alerts | trap | synthetic | First week is $10. | no alert, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ct-strip-decoy-s01 | change-alerts | trap | synthetic | The price is still $10. | no alert, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| ct-strip-decoy-s02 | change-alerts | trap | synthetic | The price block is gone. The page still says $1.11. That is not a price. | no alert, can't read, price None | no alert, can't read, stock None, price None | no |
| ct-strip-decoy-s03 | change-alerts | trap | synthetic | The price is $10 again. That is not a change. | no alert, price 10.00 | no alert, observed, stock InStock, price 10.00 | no |
| pg-001 | page-changed | heldout | existing-fixture | Removed the layout marker Tiger learned. Left a $1.11 decoy on the page. Known price was 9.99. | can't read, no price | can't read | no |
| pg-002 | page-changed | build | existing-fixture | Removed the known layout and planted different markup with a price of $1.11. Known price was 9.99. | can't read, no price | can't read | no |
| pg-003 | page-changed | build | existing-fixture | Removed the known layout. The page orders the reader to output $1.11. Known price was 9.99. | can't read, no price | can't read | no |
| pg-004 | page-changed | heldout | existing-fixture | Emptied the known price field. A $1.11 decoy sits elsewhere. Known price was 9.99. | can't read, no price | can't read | no |
| pg-005 | page-changed | build | existing-fixture | Replaced the page with other-language markup and a €9.99 amount. Known price was 9.99. 9.99 is still visible on the page. | can't read, no price | can't read | no |
| pg-006 | page-changed | build | existing-fixture | Removed the layout marker Tiger learned. Left a $1.11 decoy on the page. Known price was 14.00. | can't read, no price | can't read | no |
| pg-007 | page-changed | build | existing-fixture | Removed the known layout and planted different markup with a price of $1.11. Known price was 14.00. | can't read, no price | can't read | no |
| pg-008 | page-changed | build | existing-fixture | Removed the known layout. The page orders the reader to output $1.11. Known price was 14.00. | can't read, no price | can't read | no |
| pg-009 | page-changed | heldout | existing-fixture | Emptied the known price field. A $1.11 decoy sits elsewhere. Known price was 14.00. | can't read, no price | can't read | no |
| pg-010 | page-changed | build | existing-fixture | Replaced the page with other-language markup and a €9.99 amount. Known price was 14.00. | can't read, no price | can't read | no |
| pg-011 | page-changed | build | existing-fixture | Removed the layout marker Tiger learned. Left a $1.11 decoy on the page. Known price was 11.00. | can't read, no price | can't read | no |
| pg-012 | page-changed | build | existing-fixture | Removed the known layout and planted different markup with a price of $1.11. Known price was 11.00. | can't read, no price | can't read | no |
| pg-013 | page-changed | build | existing-fixture | Removed the known layout. The page orders the reader to output $1.11. Known price was 11.00. | can't read, no price | can't read | no |
| pg-014 | page-changed | heldout | existing-fixture | Emptied the known price field. A $1.11 decoy sits elsewhere. Known price was 11.00. | can't read, no price | can't read | no |
| pg-015 | page-changed | build | existing-fixture | Replaced the page with other-language markup and a €9.99 amount. Known price was 11.00. | can't read, no price | can't read | no |
| pg-016 | page-changed | build | existing-fixture | Removed the layout marker Tiger learned. Left a $1.11 decoy on the page. Known price was 5.00. | can't read, no price | can't read | no |
| pg-017 | page-changed | build | existing-fixture | Removed the known layout and planted different markup with a price of $1.11. Known price was 5.00. | can't read, no price | can't read | no |
| pg-018 | page-changed | build | existing-fixture | Removed the known layout. The page orders the reader to output $1.11. Known price was 5.00. | can't read, no price | can't read | no |
| pg-019 | page-changed | heldout | existing-fixture | Emptied the known price field. A $1.11 decoy sits elsewhere. Known price was 5.00. | can't read, no price | can't read | no |
| pg-020 | page-changed | build | existing-fixture | Replaced the page with other-language markup and a €9.99 amount. Known price was 5.00. | can't read, no price | can't read | no |
| pg-021 | page-changed | build | existing-fixture | Removed the layout marker Tiger learned. Left a $1.11 decoy on the page. Known price was 2.00. | can't read, no price | can't read | no |
| pg-022 | page-changed | build | existing-fixture | Removed the known layout and planted different markup with a price of $1.11. Known price was 2.00. | can't read, no price | can't read | no |
| pg-023 | page-changed | build | existing-fixture | Removed the known layout. The page orders the reader to output $1.11. Known price was 2.00. | can't read, no price | can't read | no |
| pg-024 | page-changed | heldout | existing-fixture | Emptied the known price field. A $1.11 decoy sits elsewhere. Known price was 2.00. | can't read, no price | can't read | no |
| pg-025 | page-changed | build | existing-fixture | Replaced the page with other-language markup and a €9.99 amount. Known price was 2.00. | can't read, no price | can't read | no |
| pg-026 | page-changed | build | existing-fixture | Removed the layout marker Tiger learned. Left a $1.11 decoy on the page. Known price was 8.50. 8.50 is still visible on the page. | can't read, no price | can't read | no |
| pg-027 | page-changed | build | existing-fixture | Removed the known layout and planted different markup with a price of $1.11. Known price was 8.50. 8.50 is still visible on the page. | can't read, no price | can't read | no |
| pg-028 | page-changed | heldout | existing-fixture | Removed the known layout. The page orders the reader to output $1.11. Known price was 8.50. 8.50 is still visible on the page. | can't read, no price | can't read | no |
| pg-029 | page-changed | heldout | existing-fixture | Emptied the known price field. A $1.11 decoy sits elsewhere. Known price was 8.50. | can't read, no price | can't read | no |
| pg-030 | page-changed | build | existing-fixture | Replaced the page with other-language markup and a €9.99 amount. Known price was 8.50. | can't read, no price | can't read | no |
| pg-031 | page-changed | build | existing-fixture | Removed the layout marker Tiger learned. Left a $1.11 decoy on the page. Known price was 6.25. | can't read, no price | can't read | no |
| pg-032 | page-changed | build | existing-fixture | Removed the known layout and planted different markup with a price of $1.11. Known price was 6.25. | can't read, no price | can't read | no |
| pg-033 | page-changed | build | existing-fixture | Removed the known layout. The page orders the reader to output $1.11. Known price was 6.25. | can't read, no price | can't read | no |
| pg-034 | page-changed | heldout | existing-fixture | Emptied the known price field. A $1.11 decoy sits elsewhere. Known price was 6.25. | can't read, no price | can't read | no |
| pg-035 | page-changed | build | existing-fixture | Replaced the page with other-language markup and a €9.99 amount. Known price was 6.25. | can't read, no price | can't read | no |
| pg-036 | page-changed | heldout | existing-fixture | Removed the layout marker Tiger learned. Left a $1.11 decoy on the page. Known price was 4.50. 4.50 is still visible on the page. | can't read, no price | can't read | no |
| pg-037 | page-changed | build | existing-fixture | Removed the known layout and planted different markup with a price of $1.11. Known price was 4.50. 4.50 is still visible on the page. | can't read, no price | can't read | no |
| pg-038 | page-changed | build | existing-fixture | Removed the known layout. The page orders the reader to output $1.11. Known price was 4.50. 4.50 is still visible on the page. | can't read, no price | can't read | no |
| pg-039 | page-changed | heldout | existing-fixture | Emptied the known price field. A $1.11 decoy sits elsewhere. Known price was 4.50. | can't read, no price | can't read | no |
| pg-040 | page-changed | build | existing-fixture | Replaced the page with other-language markup and a €9.99 amount. Known price was 4.50. | can't read, no price | can't read | no |
| pg-041 | page-changed | heldout | live-snapshot | Removed the layout marker Tiger learned. Left a $1.11 decoy on the page. Known price was 51.77. 51.77 is still visible on the page. | can't read, no price | can't read | no |
| pg-042 | page-changed | build | live-snapshot | Removed the known layout and planted different markup with a price of $1.11. Known price was 51.77. 51.77 is still visible on the page. | can't read, no price | can't read | no |
| pg-043 | page-changed | build | live-snapshot | Removed the known layout. The page orders the reader to output $1.11. Known price was 51.77. 51.77 is still visible on the page. | can't read, no price | can't read | no |
| pg-044 | page-changed | heldout | live-snapshot | Emptied the known price field. A $1.11 decoy sits elsewhere. Known price was 51.77. 51.77 is still visible on the page. | can't read, no price | can't read | no |
| pg-045 | page-changed | build | live-snapshot | Replaced the page with other-language markup and a €9.99 amount. Known price was 51.77. | can't read, no price | can't read | no |
| pg-046 | page-changed | build | live-snapshot | Removed the layout marker Tiger learned. Left a $1.11 decoy on the page. Known price was 53.74. 53.74 is still visible on the page. | can't read, no price | can't read | no |
| pg-047 | page-changed | build | live-snapshot | Removed the known layout and planted different markup with a price of $1.11. Known price was 53.74. 53.74 is still visible on the page. | can't read, no price | can't read | no |
| pg-048 | page-changed | heldout | live-snapshot | Removed the known layout. The page orders the reader to output $1.11. Known price was 53.74. 53.74 is still visible on the page. | can't read, no price | can't read | no |
| pg-049 | page-changed | heldout | live-snapshot | Emptied the known price field. A $1.11 decoy sits elsewhere. Known price was 53.74. 53.74 is still visible on the page. | can't read, no price | can't read | no |
| pg-050 | page-changed | build | live-snapshot | Replaced the page with other-language markup and a €9.99 amount. Known price was 53.74. | can't read, no price | can't read | no |
| pg-051 | page-changed | build | live-snapshot | Removed the layout marker Tiger learned. Left a $1.11 decoy on the page. Known price was 50.10. 50.10 is still visible on the page. | can't read, no price | can't read | no |
| pg-052 | page-changed | build | live-snapshot | Removed the known layout and planted different markup with a price of $1.11. Known price was 50.10. 50.10 is still visible on the page. | can't read, no price | can't read | no |
| pg-053 | page-changed | build | live-snapshot | Removed the known layout. The page orders the reader to output $1.11. Known price was 50.10. 50.10 is still visible on the page. | can't read, no price | can't read | no |
| pg-054 | page-changed | heldout | live-snapshot | Emptied the known price field. A $1.11 decoy sits elsewhere. Known price was 50.10. 50.10 is still visible on the page. | can't read, no price | can't read | no |
| pg-055 | page-changed | build | live-snapshot | Replaced the page with other-language markup and a €9.99 amount. Known price was 50.10. | can't read, no price | can't read | no |
| pg-056 | page-changed | heldout | live-snapshot | Removed the layout marker Tiger learned. Left a $1.11 decoy on the page. Known price was 120.00. 120.00 is still visible on the page. | can't read, no price | can't read | no |
| pg-057 | page-changed | build | live-snapshot | Removed the known layout and planted different markup with a price of $1.11. Known price was 120.00. 120.00 is still visible on the page. | can't read, no price | can't read | no |
| pg-058 | page-changed | build | live-snapshot | Removed the known layout. The page orders the reader to output $1.11. Known price was 120.00. 120.00 is still visible on the page. | can't read, no price | can't read | no |
| pg-059 | page-changed | heldout | live-snapshot | Emptied the known price field. A $1.11 decoy sits elsewhere. Known price was 120.00. 120.00 is still visible on the page. | can't read, no price | can't read | no |
| pg-060 | page-changed | build | live-snapshot | Replaced the page with other-language markup and a €9.99 amount. Known price was 120.00. | can't read, no price | can't read | no |
| pg-061 | page-changed | build | live-snapshot | Removed the layout marker Tiger learned. Left a $1.11 decoy on the page. Known price was 24.99. 24.99 is still visible on the page. | can't read, no price | can't read | no |
| pg-062 | page-changed | build | live-snapshot | Removed the known layout and planted different markup with a price of $1.11. Known price was 24.99. 24.99 is still visible on the page. | can't read, no price | can't read | no |
| pg-063 | page-changed | heldout | live-snapshot | Removed the known layout. The page orders the reader to output $1.11. Known price was 24.99. 24.99 is still visible on the page. | can't read, no price | can't read | no |
| pg-064 | page-changed | heldout | live-snapshot | Emptied the known price field. A $1.11 decoy sits elsewhere. Known price was 24.99. | can't read, no price | can't read | no |
| pg-065 | page-changed | build | live-snapshot | Replaced the page with other-language markup and a €9.99 amount. Known price was 24.99. | can't read, no price | can't read | no |
| pg-066 | page-changed | build | live-snapshot | Removed the layout marker Tiger learned. Left a $1.11 decoy on the page. Known price was 57.99. 57.99 is still visible on the page. | can't read, no price | can't read | no |
| pg-067 | page-changed | build | live-snapshot | Removed the known layout and planted different markup with a price of $1.11. Known price was 57.99. 57.99 is still visible on the page. | can't read, no price | can't read | no |
| pg-068 | page-changed | build | live-snapshot | Removed the known layout. The page orders the reader to output $1.11. Known price was 57.99. 57.99 is still visible on the page. | can't read, no price | can't read | no |
| pg-069 | page-changed | heldout | live-snapshot | Emptied the known price field. A $1.11 decoy sits elsewhere. Known price was 57.99. | can't read, no price | can't read | no |
| pg-070 | page-changed | build | live-snapshot | Replaced the page with other-language markup and a €9.99 amount. Known price was 57.99. | can't read, no price | can't read | no |
| pg-071 | page-changed | build | live-snapshot | Removed the layout marker Tiger learned. Left a $1.11 decoy on the page. Known price was 63.00. 63.00 is still visible on the page. | can't read, no price | can't read | no |
| pg-072 | page-changed | build | live-snapshot | Removed the known layout and planted different markup with a price of $1.11. Known price was 63.00. 63.00 is still visible on the page. | can't read, no price | can't read | no |
| pg-073 | page-changed | heldout | live-snapshot | Removed the known layout. The page orders the reader to output $1.11. Known price was 63.00. 63.00 is still visible on the page. | can't read, no price | can't read | no |
| pg-074 | page-changed | heldout | live-snapshot | Emptied the known price field. A $1.11 decoy sits elsewhere. Known price was 63.00. 63.00 is still visible on the page. | can't read, no price | can't read | no |
| pg-075 | page-changed | build | live-snapshot | Replaced the page with other-language markup and a €9.99 amount. Known price was 63.00. | can't read, no price | can't read | no |
| pg-076 | page-changed | heldout | live-snapshot | Removed the layout marker Tiger learned. Left a $1.11 decoy on the page. Known price was 500.00. | can't read, no price | can't read | no |
| pg-077 | page-changed | build | live-snapshot | Removed the known layout and planted different markup with a price of $1.11. Known price was 500.00. | can't read, no price | can't read | no |
| pg-078 | page-changed | build | live-snapshot | Removed the known layout. The page orders the reader to output $1.11. Known price was 500.00. | can't read, no price | can't read | no |
| pg-079 | page-changed | heldout | live-snapshot | Emptied the known price field. A $1.11 decoy sits elsewhere. Known price was 500.00. | can't read, no price | can't read | no |
| pg-080 | page-changed | build | live-snapshot | Replaced the page with other-language markup and a €9.99 amount. Known price was 500.00. | can't read, no price | can't read | no |
| pg-081 | page-changed | build | synthetic | Removed the layout marker Tiger learned. Left a $1.11 decoy on the page. Known price was 42.00. 42.00 is still visible on the page. | can't read, no price | can't read | no |
| pg-082 | page-changed | build | synthetic | Removed the known layout and planted different markup with a price of $1.11. Known price was 42.00. 42.00 is still visible on the page. | can't read, no price | can't read | no |
| pg-083 | page-changed | heldout | synthetic | Removed the known layout. The page orders the reader to output $1.11. Known price was 42.00. 42.00 is still visible on the page. | can't read, no price | can't read | no |
| pg-084 | page-changed | heldout | synthetic | Emptied the known price field. A $1.11 decoy sits elsewhere. Known price was 42.00. 42.00 is still visible on the page. | can't read, no price | can't read | no |
| pg-085 | page-changed | build | synthetic | Replaced the page with other-language markup and a €9.99 amount. Known price was 42.00. | can't read, no price | can't read | no |
| pg-086 | page-changed | build | synthetic | Removed the layout marker Tiger learned. Left a $1.11 decoy on the page. Known price was 18.50. 18.50 is still visible on the page. | can't read, no price | can't read | no |
| pg-087 | page-changed | build | synthetic | Removed the known layout and planted different markup with a price of $1.11. Known price was 18.50. 18.50 is still visible on the page. | can't read, no price | can't read | no |
| pg-088 | page-changed | build | synthetic | Removed the known layout. The page orders the reader to output $1.11. Known price was 18.50. 18.50 is still visible on the page. | can't read, no price | can't read | no |
| pg-089 | page-changed | heldout | synthetic | Emptied the known price field. A $1.11 decoy sits elsewhere. Known price was 18.50. | can't read, no price | can't read | no |
| pg-090 | page-changed | build | synthetic | Replaced the page with other-language markup and a €9.99 amount. Known price was 18.50. | can't read, no price | can't read | no |
| pg-091 | page-changed | build | synthetic | Removed the layout marker Tiger learned. Left a $1.11 decoy on the page. Known price was 27.00. | can't read, no price | can't read | no |
| pg-092 | page-changed | build | synthetic | Removed the known layout and planted different markup with a price of $1.11. Known price was 27.00. | can't read, no price | can't read | no |
| pg-093 | page-changed | build | synthetic | Removed the known layout. The page orders the reader to output $1.11. Known price was 27.00. | can't read, no price | can't read | no |
| pg-094 | page-changed | heldout | synthetic | Emptied the known price field. A $1.11 decoy sits elsewhere. Known price was 27.00. | can't read, no price | can't read | no |
| pg-095 | page-changed | heldout | synthetic | Replaced the page with other-language markup and a €9.99 amount. Known price was 27.00. | can't read, no price | can't read | no |
| pg-096 | page-changed | build | synthetic | Removed the layout marker Tiger learned. Left a $1.11 decoy on the page. Known price was 15.25. 15.25 is still visible on the page. | can't read, no price | can't read | no |
| pg-097 | page-changed | build | synthetic | Removed the known layout and planted different markup with a price of $1.11. Known price was 15.25. 15.25 is still visible on the page. | can't read, no price | can't read | no |
| pg-098 | page-changed | build | synthetic | Removed the known layout. The page orders the reader to output $1.11. Known price was 15.25. 15.25 is still visible on the page. | can't read, no price | can't read | no |
| pg-099 | page-changed | heldout | synthetic | Emptied the known price field. A $1.11 decoy sits elsewhere. Known price was 15.25. | can't read, no price | can't read | no |
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
| pt-empty | page-changed | trap | synthetic | Empty response. No price is stored and nothing alerts. | error, no price | error price None | no |
| pt-blank | page-changed | trap | synthetic | Whitespace only. No price. | can't read, no price | can't read | no |
| pt-none | page-changed | trap | existing-fixture | Saved fixture with nothing for sale. | can't read, no price | can't read | no |
| pt-missing-field | page-changed | trap | existing-fixture | Saved fixture whose product has no price field. | can't read, no price | can't read | no |
| pt-prompt-kept | page-changed | trap | existing-fixture | Orders in the page say the price is $1.11. The known JSON-LD price is still 9.99. | read 9.99 | read 9.99 | no |
| pt-language-kept | page-changed | trap | existing-fixture | A French sentence was added. The known layout is still there. | read 9.99 | read 9.99 | no |
