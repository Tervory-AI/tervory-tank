# Founder control panel: Figma frame 10:115

- **Figma:** https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS/?node-id=10-115. The frame is named "Founder control panel · everything on one screen".
- **Size:** 1440 × 1140, with padding 24 top, 32 sides and 32 bottom, and 18 between rows.
- **Built at:** `app.tervory.com/control` (`workspace/app/control/`). **Founder only.**
- **Fonts:**
  - Jost Light for the logo word and "Control panel";
  - JetBrains Mono for every number;
  - Inter for everything else.

  All three are in `workspace/app/fonts`.
- **Colours:**

  | Use | Colour |
  |---|---|
  | Page background | `#f4f6fa` |
  | Cards | white |
  | Card border | `#b8bfd0` |
  | Main text | `#001840` |
  | Muted text | `#3d4a66` |
  | Faint text | `#8c94a6` |
  | Green | `#1e7a46` |
  | Green pill background | `#eaf6ef` |
  | Red | `#e80008` |
  | Bar background | `#d6deeb` |
  | Status dot: amber | `#B26B00` |
  | Status dot: grey | `#8C94A6` |

- **Radii:** cards 14, buttons 8, pills 999, bars 3.
- **Exact sizes, gaps and paddings:** in `reference.tsx`. The image is `frame.png`.

## FIXED text: build exactly, to the character
| Node | Text |
|---|---|
| 10:120 | `Control panel` |
| 10:126 | `Pause all paid work` |
| 10:129 | `Sign-ups` |
| 10:137 | `Paying clients` |
| 10:145 | `Work done today` |
| 10:153 | `Spent this month` |
| 10:161 | `Saved this month` |
| 10:164 | `vs top models` |
| 10:176 | `Verified records by state` |
| 10:214 / 10:215 | `■ Verified` / `■ Licences` |
| 10:217 | `Cost per verified record` |
| 10:223 / 10:224 | `— Tervory, falling` / `- - Apollo` |
| 10:227 | `Tervory found` |
| 10:230 | `Apollo found` |
| 10:233 | `Cost per record` |
| 10:236 | `States done` |
| 10:240 | `Run next state` |
| 10:242 | `Export case study` |
| 10:245 | `Needs you` |
| 10:251 | `Approve all` |
| 10:255 / 10:257 | `Run` / `Skip` |
| 10:261 / 10:263 | `Switch` / `Later` |
| 10:267, 10:303 | `Start` |
| 10:271 / 10:273 | `Look` / `Let it fix` |
| 10:277 | `Squad` |
| 10:282 to 10:324 | Squad names: `Base`, `Tiger`, `Market Lab`, `Rig`, `Tisan`, `Radix`, `Zenas`, `Ghost`. See open question 1 |
| 10:285 and the other squad buttons | `Pause`, or `Start` when that squad is stopped |
| 10:330 | `Latest sign-ups` |
| 10:370 | `Controls` |
| 10:372 | `Shadow checks on every model call` |
| 10:376 | `Overnight half-price batches` |
| 10:380 | `Paid tools without asking` |
| 10:384 | `Squad builds Tervory` |
| 10:389 | `Daily budget` |
| 10:395 | `Servers` |
| 10:398 | `Boston` |
| 10:408 | `Storage` |
| 10:413 | `Open the window` |
| 10:415 | `Proof report` |

## DATA text: a real value, in exactly this format
| Node | Frame shows | Real source | Format rule |
|---|---|---|---|
| 10:124 | `All systems normal · Ghost on watch` | Health checks and the security guard | Open question 2 |
| 10:130 | `214` | Clerk: total sign-ups | Comma between thousands |
| 10:132 | `+31 this week` | Clerk: sign-ups in the last 7 days | `+N this week` |
| 10:138 | `9` | **Stripe: customers with a paid, active subscription** (not 8, and not trials) | Comma between thousands |
| 10:140 | `+2 this week` | Stripe: new paid customers in the last 7 days | `+N this week` |
| 10:146 | `4,812` | Ledger: tasks finished today | Comma between thousands |
| 10:148 | `71% by code, no model` | Ledger: the share done with no model call | `N% by code, no model` |
| 10:154 | `$212.40` | Ledger: spend this month | `$` and 2 decimals, comma between thousands |
| 10:156 | `budget $600` | The monthly budget setting | `budget $N` |
| 10:162 | `$3,691.70` | Ledger: saved this month | `$` and 2 decimals, comma between thousands |
| 10:134 to 10:166 | sparklines | The same numbers per day, last 14 days | Same stroke colour and size as the asset |
| 10:171 | `Case study · AmmoSync on Base` | The case-study job | `Case study · ` + job name. Open question 4 |
| 10:173 | `ATF list · 74,012 licences` | The job's source list and row count | `<source> · N licences` |
| 10:180 to 10:212 | bars DE, VT, RI, WY, TX, FL, CA | Per state: licences and verified | Same bar colours, widths and gaps |
| 10:218 | line chart | Cost per verified record over time, and Apollo's line | Same stroke colours as the asset |
| 10:228 | `14,000 records` | Verified records | `N records` |
| 10:231 | `800 records` | Apollo's count for the same list | `N records`. Open question 4 |
| 10:234 | `$0.0004` | Cost ÷ verified records | `$` and 4 decimals |
| 10:237 | `12 of 50` | States finished | `N of 50` |
| 10:247 | `5` | How many items are in "Needs you" | Number |
| 10:249 to 10:269 | the five items | Real pending founder decisions | One row per item, with the buttons from the FIXED list for that kind of item |
| 10:279 | `Boston ▾` | The region picker | Open question 3 |
| 10:283 to 10:325 | `Texas list · 61%`, `—`, and so on | Each squad's current job and progress | `<job> · N%`, or `—` when idle |
| status dots | green, amber, grey | Each squad's state | Green running, amber queued, grey stopped (the frame's assets) |
| 10:333 | `All 214` | Total sign-ups | `All N` |
| 10:336 to 10:368 | name, `Company · Country`, plan pill, `2h ago` | Clerk: the 5 latest sign-ups | Exactly as the frame shows |
| switches | on / off | The real setting | `switch-on.svg` / `switch-off.svg` |
| 10:391 | `$20 · $7.10 used` | The daily budget and today's spend | `$N · $N.NN used` |
| 10:393 | the bar fill | Used ÷ budget | Width as a share of 318 |
| 10:400 / 10:405 | `CPU 34% · memory 61%` | Server stats | `CPU N% · memory N%` |
| 10:410 | `R2 · 41 GB of 1 TB` | Storage used | `R2 · N GB of 1 TB` |

**Every button does its real job, and every number opens its source.** No section may show "unavailable", "not linked" or a build code (build list, step 2.2). If a source for any DATA line doesn't exist yet, **stop and report it.** Never fill in a sample value.

## Founder's open questions: answer in Figma before the build starts
1. **"Ghost" or "Autumbra"?** The frame says `Ghost` (squad row 10:324, the health pill 10:124 and the item 10:269). Ghost is now called Autumbra. As it stands, the builder must write `Ghost`.
2. **The health pill:** the frame has only the good state, `All systems normal · Ghost on watch`. What does it say when something is down?
3. **The "South Africa" server row (10:403) and `Boston ▾`:** ZA is stopped. Keep the row, remove it, or show it as stopped?
4. **The case study and Apollo numbers:** which job is the case study, and where does Apollo's count come from? If there's no real source, this whole card has no data.
5. **The footer (10:416):** `Sample figures for layout. Real numbers come from the ledger, Clerk sign-ups and the servers.` Is it built? On a page with real numbers, it would be wrong.
6. **Empty states:** when "Needs you" is empty, or a list has nothing, what shows? Nothing is in the frame.
