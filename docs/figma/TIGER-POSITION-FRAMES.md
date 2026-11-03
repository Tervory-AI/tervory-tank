# Tiger follow-up correction — navy borders and Cheapest line height

Branch `codex/tiger-figma`; starting commit `881a2ab6`. Implemented the founder’s two follow-up corrections in Figma. All existing IDs and every text string are preserved. No nodes created or removed. No new words. Current status stays **Changed after approval, awaiting founder**. Only this register is committed; production code and deployments are unchanged.

## Directly edited nodes — 14

| Correction | Exact node IDs | Persisted result |
| --- | --- | --- |
| Confirm border | `256:380`, `256:450` | 1px `#001840`, copied with its existing colour-variable binding from read-only CRM / Action Confirm `98:8796`. White fill, navy text and 48px height retained. |
| Selected segment border | `256:67`, `256:197`, `256:342`, `256:435`, `256:532`, `256:640`, `267:19268`, `267:19380`, `267:19462`, `267:19588` | Same 1px `#001840` border. Existing `#e9edf6` fill, navy text and 48px height retained. No dark fill added. |
| Cheapest typography | `I256:254;43:407`, `I256:271;43:407` | Line height changed from 21px to 140%, matching `I256:257;43:407`; Inter Regular 14 remains. Values render 20px high and parent rows `256:254`, `256:271` are now 36px, matching the Rank row. |

## Nodes changed by automatic layout reflow — 15 additional IDs

`256:170`, `256:174`, `256:180`, `256:194`, `256:204`, `256:240`, `256:254`, `256:257`, `256:260`, `256:263`, `256:271`, `256:274`, `256:277`, `256:280`, `256:692`

These nodes were not directly edited. The two Cheapest rows each lost 1px; the mobile Price position frame `256:170` is now **375 × 2725**, previously 375 × 2727. All other nine frame sizes and all other node geometry remained unchanged. In total this pass changed **29 existing nodes** (14 direct + 15 additional reflow nodes).

## Wording and validation

**New words: none.** A full before/after comparison of every text ID and character string on page `256:9` passed. All original node-ID sets match, with no additions/removals. The shared CRM source was read only. Persisted-property verification passed for all twelve borders, all twelve 48px control heights, the ten retained light selected fills, and both 140% line heights / 36px Cheapest rows. Navy border contrast is 17.43:1 on white and exceeds 3:1 on the selected light fill.

Final desktop/mobile Matches and mobile Price position screenshots were visually inspected after the edit. No new clipping or overflow was visible; source geometry comparison confirms that only the intended mobile Cheapest reflow occurred. The prior light-theme/spacing restyle handoff still applies; Workspace must also match these navy borders and 140% line heights. No production code was edited. Application tests are not applicable to this Figma/document-only correction.

| Frame | Screenshot | SHA-256 |
| --- | --- | --- |
| `256:170` | [PNG](/workspace/codex-tiger-figma/.git/tiger-design/border-256-170.png) | `b4dec2fce11ca18215cbb46953e767cfd24c9d3679cdcbf17e2394166d2aa4d6` |
| `256:283` | [PNG](/workspace/codex-tiger-figma/.git/tiger-design/border-256-283.png) | `d86b06a1cd51a555009c56582b08f0e81f592ba6dc448c697d1d6e04680f95c0` |
| `256:406` | [PNG](/workspace/codex-tiger-figma/.git/tiger-design/border-256-406.png) | `d8258546c093683c9cc7247afbe0ef72e10b4d8436faea97f7e6a1965cf87202` |

Checks: exact before/after node IDs and text; all twelve border colours/weights/heights/fills; both line-height values and row heights; all ten frame sizes; full geometry comparison; `git diff --check`; only this register differs from main. Commit and push target: `origin codex/tiger-figma`; result is reported in this chat.

---

## Previous correction pass — historical evidence
# Tiger correction register — 3 Nov, founder ruling 11:37 PT

Implemented the nine requested corrections and the founder’s 3 Nov 11:37 PT ruling: no dark backgrounds on this Tiger page. All ten existing frame IDs and every existing descendant ID survive. No nodes were deleted. Changes remain **Changed after approval, awaiting founder**; the recorded earlier approval is history, not approval of this correction pass.

Branch: `codex/tiger-figma`. Starting commit: `239e5db4`. Only this register is committed. Production code, deployment and main are unchanged. The earlier register follows below as historical evidence.

## Corrections and exact wording

| Item | Result |
| --- | --- |
| 1 | View segments, primary/line/text buttons, Menu, search, and linked controls meet 44px minimum. Buttons and inputs are 48px; the inherited CRM business switcher persists at 44px. Existing Tiger side-menu instances are 48px. Links have at least 48px hit height. |
| 2 | All ten search borders use existing Tiger muted colour `#6b7590`: **4.5928:1 against white**, above 3:1. |
| 3 | Every 12px table/card corner in these frames is now 8px. |
| 4 | Visible layout gaps use 0/8/16/24. Padding uses those values or larger multiples of 8. Mobile side padding is 24px and full-width descendants follow the new width. |
| 5 | `I256:254;43:407` and `I256:271;43:407`: Inter Regular 14px / 21px, matching the missing Rank/Difference values. |
| 6 | `256:585`: `Attempted 25 minutes ago` → `Last attempt: 25 minutes ago`. `256:601`: `Attempted 1 hour ago` → `Last attempt: 1 hour ago`. These exactly reuse existing mobile wording. `I256:550;43:390` retains `Last checked` for the successful-check column; attempted cells now explicitly identify attempts. |
| 7 | `256:399` and `256:464` remain plain, unfilled, unstroked Rejected statuses. Their text and Undo text use the same left inset and vertical alignment; status/action wrappers are 48px high. |
| 8 | All five 375px search fields are 327 × 48px, with a 21px single-line text box and end ellipsis. The full stored placeholder remains `Search watched products, readings and alerts`. |
| 9 + 11:37 ruling | Desktop panels use white CRM Navigation instances of `180:8387`, referenced by approved `182:9119`; mobile bars and Menu use the same light palette. Selected segments use existing light `#e9edf6`; there are no visible dark surface fills. Sidebar section identity/labels use `#3d4a66`. |

**New visible wording in this pass:** only `Last attempt: 25 minutes ago` and `Last attempt: 1 hour ago`, copied from mobile into the two existing desktop text IDs above. Navigation instance overrides reuse existing `{Store name}` and `Tiger`; no new UI phrase was authored. Approved copy, illustrative-only data and review labels are otherwise preserved.

## Navigation reuse with original IDs preserved

Each existing `.panel` remains its original frame and keeps its original Tiger menu instances. A linked CRM Navigation instance supplies the white shell, approved on-white Tervory artwork, business identity and Tiger section label. Its stock Trigger menu/footer groups are hidden, and the original Tiger menu groups remain visible siblings inside the existing panel. The original dark-logo nodes are retained but hidden. This preserves the original menu IDs and avoids modifying the shared CRM main component or other pages. Mobile image nodes retain their IDs and reuse the approved on-white logo image already in the file.

| Existing frame | Existing panel | New CRM shell instance | Main component |
| --- | --- | --- | --- |
| `256:10` | `256:15` | `465:26693` | `180:8387` |
| `256:283` | `256:288` | `465:26776` | `180:8387` |
| `256:471` | `256:476` | `465:26859` | `180:8387` |
| `267:19232` | `267:19238` | `465:26942` | `180:8387` |
| `267:19424` | `267:19430` | `465:27025` | `180:8387` |

## Required Workspace restyle handoff

**Items 1–4 and 9 differ from live `workspace/app/tiger/tiger.css` and require the matching code change in the Workspace restyle.** This pass changes Figma only. The restyle must carry the tap targets/equal button heights, accessible search border, 8px table/card corners, spacing grid, white CRM navigation and light mobile bars/selected states into code. The no-dark-background ruling applies to all Tervory application surfaces; homepage exceptions do not apply to this Tiger page. Also carry the single-line mobile input and explicit attempted-check wording into the implementation.

Read-only source comparison used the branch copy of `tiger.css` (`.panel` navy at its panel rule; compact buttons/padding, `.search`, `.table-wrap`, `.note-card`, `.row-actions`, `.seg`). No production stylesheet was edited.

## Final verification and screenshots

All ten full-frame screenshots below were visually inspected after the final geometry changes. The final structural audit found **zero controls below 44px, zero off-grid spacing values, zero visible 12px corners, zero dark surface fills, and zero text boxes outside their immediate parent**. Checks covered both populated and empty frames at 1440px/375px. Jost headings, Inter body, existing warning colours and discrete logo images are preserved; the UI remains editable layers. There is no flattened UI image in the deliverable.

Contrast, using WCAG sRGB luminance: `#6b7590`/white 4.5928:1; `#3d4a66`/white 8.8615:1; navy/white 17.4319:1; warning `#b45309`/white 5.0216:1. Navy text on selected light `#e9edf6` also exceeds 4.5:1.

Screenshots are local evidence, deliberately outside the tracked tree. Their full pixel sizes and SHA-256 hashes make the checked images identifiable. Figma links point to the unchanged frame IDs.

| Frame | Final size | Minimum control height | Screenshot | SHA-256 |
| --- | --- | --- | --- | --- |
| [256:10](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=256-10) | 1440 × 1449 | 44px | [PNG](/workspace/codex-tiger-figma/.git/tiger-design/final-256-10.png) | `5838f85a58daf8989fdefbae9d49ec2583ee8cddc034947691ebfa95b1f19d61` |
| [256:170](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=256-170) | 375 × 2727 | 48px | [PNG](/workspace/codex-tiger-figma/.git/tiger-design/final-256-170.png) | `25e6fc210b85c8aaa85bc700f6afd1a3e7aa0f079947e6cfcf5ddded280e0f91` |
| [256:283](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=256-283) | 1440 × 1165 | 44px | [PNG](/workspace/codex-tiger-figma/.git/tiger-design/final-256-283.png) | `21f3f9d92c900290b80ca7ae96ae0cc0840e9b81e2f28d982e44fb5de8de5e6a` |
| [256:406](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=256-406) | 375 × 1955 | 48px | [PNG](/workspace/codex-tiger-figma/.git/tiger-design/final-256-406.png) | `d6f87be141f09b569254ef7bf2e31ed6620c95cc87721b27ae8e52eeaaf599b9` |
| [256:471](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=256-471) | 1440 × 1145 | 44px | [PNG](/workspace/codex-tiger-figma/.git/tiger-design/final-256-471.png) | `e10dd5ec116aea15f5dda302f45f74e0939a324997fbe1a76a04bd07b8f75678` |
| [256:609](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=256-609) | 375 × 2170 | 48px | [PNG](/workspace/codex-tiger-figma/.git/tiger-design/final-256-609.png) | `18c8c63683177b421b0ccbe297d02868c65fdc24fc8f0840a4d26675587022b3` |
| [267:19232](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=267-19232) | 1440 × 937 | 44px | [PNG](/workspace/codex-tiger-figma/.git/tiger-design/final-267-19232.png) | `209af9591bc6e434e6fd95344c66778e959154ab88e4467a151af4c51dd95b61` |
| [267:19356](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=267-19356) | 375 × 708 | 48px | [PNG](/workspace/codex-tiger-figma/.git/tiger-design/final-267-19356.png) | `78f177bd6794afe13540f5eb2fa92c3c90af769e631f9c29ee2e8a77f2f0f486` |
| [267:19424](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=267-19424) | 1440 × 937 | 44px | [PNG](/workspace/codex-tiger-figma/.git/tiger-design/final-267-19424.png) | `e7d503a11d8cb161d45d87f430a1a392c52cc2e010dbcb676656e65641a94e8f` |
| [267:19562](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=267-19562) | 375 × 825 | 48px | [PNG](/workspace/codex-tiger-figma/.git/tiger-design/final-267-19562.png) | `d84157a75fe23ace5dd4a8dae689a93a379556c27172b5681aa9acbdc7c5f83d` |

## Every changed existing node ID

The lists below enumerate all **675 existing nodes with persisted differences**, including automatic layout movement/reflow as well as direct property changes. Snapshot comparison covered each original node before/after; removed IDs: **none**. Geometry-only entries are included so this is the full list, not just the nodes directly written by the script.

### Frame `256:10` — 109 existing nodes

`256:10`, `256:14`, `256:15`, `256:16`, `256:17`, `256:18`, `256:19`, `I256:19;43:410`, `256:22`, `I256:22;43:410`, `256:25`, `I256:25;43:410`, `256:28`, `I256:28;43:410`, `256:31`, `256:32`, `I256:32;43:410`, `256:35`, `I256:35;43:410`, `256:38`, `I256:38;43:422`, `256:41`, `I256:41;43:410`, `256:44`, `256:45`, `256:46`, `256:47`, `I256:47;43:410`, `256:50`, `256:51`, `256:52`, `256:55`, `256:56`, `256:64`, `256:66`, `256:67`, `256:68`, `256:69`, `256:70`, `256:71`, `256:72`, `256:73`, `256:74`, `256:76`, `I256:76;43:390`, `256:80`, `I256:80;43:390`, `256:84`, `I256:84;43:390`, `256:88`, `I256:88;43:390`, `256:92`, `I256:92;43:390`, `256:96`, `I256:96;43:390`, `256:101`, `256:102`, `256:109`, `256:103`, `256:104`, `256:111`, `256:112`, `256:113`, `256:114`, `256:115`, `256:116`, `256:117`, `256:118`, `256:119`, `256:120`, `256:121`, `256:122`, `256:123`, `256:124`, `256:125`, `256:126`, `256:127`, `256:128`, `256:105`, `256:106`, `256:107`, `256:132`, `256:133`, `256:134`, `256:141`, `256:135`, `256:136`, `256:143`, `256:144`, `256:145`, `256:146`, `256:147`, `256:148`, `256:137`, `256:138`, `256:139`, `256:152`, `256:153`, `256:154`, `256:161`, `256:155`, `256:156`, `256:157`, `256:158`, `256:159`, `256:167`, `256:168`, `256:169`, `256:689`

### Frame `256:170` — 105 existing nodes

`256:170`, `256:174`, `256:175`, `256:176`, `256:177`, `256:178`, `256:179`, `256:180`, `256:181`, `256:182`, `256:185`, `256:186`, `256:187`, `256:188`, `256:194`, `256:196`, `256:197`, `256:198`, `256:199`, `256:200`, `256:201`, `256:202`, `256:203`, `256:204`, `256:205`, `256:206`, `256:207`, `256:208`, `I256:208;43:406`, `I256:208;43:407`, `256:211`, `256:212`, `256:213`, `256:214`, `256:215`, `256:216`, `256:217`, `256:218`, `256:219`, `256:220`, `256:221`, `256:222`, `256:223`, `256:224`, `256:225`, `256:226`, `256:227`, `256:228`, `256:229`, `256:230`, `256:231`, `I256:231;43:406`, `I256:231;43:407`, `256:234`, `I256:234;43:406`, `I256:234;43:407`, `256:237`, `I256:237;43:406`, `I256:237;43:407`, `256:240`, `256:241`, `256:242`, `256:243`, `I256:243;43:406`, `I256:243;43:407`, `256:246`, `256:247`, `256:248`, `256:249`, `256:250`, `256:251`, `256:252`, `256:253`, `256:254`, `I256:254;43:406`, `I256:254;43:407`, `256:257`, `I256:257;43:406`, `I256:257;43:407`, `256:260`, `I256:260;43:406`, `I256:260;43:407`, `256:263`, `256:264`, `256:265`, `256:266`, `I256:266;43:406`, `I256:266;43:407`, `256:269`, `256:270`, `256:271`, `I256:271;43:406`, `I256:271;43:407`, `256:274`, `I256:274;43:406`, `I256:274;43:407`, `256:277`, `I256:277;43:406`, `I256:277;43:407`, `256:280`, `256:281`, `256:282`, `256:692`, `256:693`, `256:694`

### Frame `256:283` — 89 existing nodes

`256:283`, `256:287`, `256:288`, `256:289`, `256:290`, `256:291`, `256:292`, `I256:292;43:410`, `256:295`, `I256:295;43:410`, `256:298`, `I256:298;43:410`, `256:301`, `I256:301;43:410`, `256:304`, `256:305`, `I256:305;43:410`, `256:308`, `I256:308;43:410`, `256:311`, `I256:311;43:422`, `256:314`, `I256:314;43:410`, `256:317`, `256:318`, `256:319`, `256:320`, `I256:320;43:410`, `256:323`, `256:324`, `256:325`, `256:328`, `256:329`, `256:337`, `256:339`, `256:340`, `256:341`, `256:342`, `256:343`, `256:344`, `256:345`, `256:347`, `256:349`, `I256:349;43:390`, `256:353`, `I256:353;43:390`, `256:357`, `I256:357;43:390`, `256:361`, `I256:361;43:390`, `256:366`, `256:367`, `256:372`, `256:373`, `256:368`, `256:374`, `256:375`, `256:376`, `256:377`, `256:369`, `256:378`, `256:379`, `256:370`, `256:380`, `256:381`, `256:382`, `256:383`, `256:384`, `256:385`, `256:386`, `256:391`, `256:392`, `256:387`, `256:393`, `256:394`, `256:395`, `256:396`, `256:388`, `256:397`, `256:398`, `256:389`, `256:399`, `256:400`, `256:401`, `256:402`, `256:403`, `256:404`, `256:405`, `256:695`

### Frame `256:406` — 60 existing nodes

`256:406`, `256:410`, `256:411`, `256:412`, `256:413`, `256:414`, `256:415`, `256:416`, `256:417`, `256:418`, `256:421`, `256:422`, `256:423`, `256:424`, `256:430`, `256:432`, `256:433`, `256:434`, `256:435`, `256:436`, `256:437`, `256:438`, `256:440`, `256:441`, `267:19226`, `256:442`, `256:443`, `256:444`, `256:445`, `256:446`, `256:447`, `256:448`, `267:19227`, `256:449`, `256:450`, `256:451`, `256:452`, `256:453`, `256:454`, `256:455`, `267:19228`, `256:456`, `256:457`, `256:458`, `256:459`, `256:460`, `256:461`, `256:462`, `267:19229`, `256:463`, `256:464`, `256:465`, `256:466`, `256:467`, `256:468`, `256:469`, `256:470`, `256:698`, `256:699`, `256:700`

### Frame `256:471` — 98 existing nodes

`256:471`, `256:475`, `256:476`, `256:477`, `256:478`, `256:479`, `256:480`, `I256:480;43:410`, `256:483`, `I256:483;43:410`, `256:486`, `I256:486;43:410`, `256:489`, `I256:489;43:410`, `256:492`, `256:493`, `I256:493;43:410`, `256:496`, `I256:496;43:410`, `256:499`, `I256:499;43:422`, `256:502`, `I256:502;43:410`, `256:505`, `256:506`, `256:507`, `256:508`, `I256:508;43:410`, `256:511`, `256:512`, `256:513`, `256:516`, `256:517`, `256:525`, `256:527`, `256:528`, `256:529`, `256:530`, `256:531`, `256:532`, `256:533`, `256:534`, `256:535`, `256:536`, `256:538`, `I256:538;43:390`, `256:542`, `I256:542;43:390`, `256:546`, `I256:546;43:390`, `256:550`, `I256:550;43:390`, `256:554`, `I256:554;43:390`, `256:559`, `256:560`, `256:565`, `256:566`, `256:561`, `256:562`, `256:563`, `256:564`, `256:570`, `256:571`, `256:572`, `256:573`, `256:574`, `256:575`, `256:576`, `256:581`, `256:582`, `256:577`, `256:578`, `256:579`, `256:585`, `256:580`, `256:586`, `256:587`, `256:588`, `256:589`, `256:590`, `256:591`, `256:592`, `256:597`, `256:598`, `256:593`, `256:594`, `256:595`, `256:601`, `256:596`, `256:602`, `256:603`, `256:604`, `256:605`, `256:606`, `256:607`, `256:608`, `256:701`

### Frame `256:609` — 72 existing nodes

`256:609`, `256:613`, `256:614`, `256:615`, `256:616`, `256:617`, `256:618`, `256:619`, `256:620`, `256:621`, `256:624`, `256:625`, `256:626`, `256:627`, `256:633`, `256:635`, `256:636`, `256:637`, `256:638`, `256:639`, `256:640`, `256:641`, `256:642`, `256:643`, `256:644`, `256:645`, `256:646`, `256:647`, `I256:647;43:406`, `I256:647;43:407`, `256:650`, `I256:650;43:406`, `I256:650;43:407`, `256:653`, `256:654`, `256:655`, `256:656`, `256:657`, `256:658`, `256:659`, `256:660`, `256:661`, `I256:661;43:406`, `I256:661;43:407`, `256:664`, `I256:664;43:406`, `I256:664;43:407`, `256:667`, `256:668`, `256:669`, `256:670`, `256:671`, `256:672`, `256:673`, `256:674`, `256:675`, `I256:675;43:406`, `I256:675;43:407`, `256:678`, `I256:678;43:406`, `I256:678;43:407`, `256:681`, `256:682`, `256:683`, `256:684`, `256:685`, `256:686`, `256:687`, `256:688`, `256:704`, `256:705`, `256:706`

### Frame `267:19232` — 43 existing nodes

`267:19232`, `267:19237`, `267:19238`, `267:19239`, `267:19240`, `267:19241`, `267:19242`, `I267:19242;43:410`, `267:19243`, `I267:19243;43:410`, `267:19244`, `I267:19244;43:410`, `267:19245`, `I267:19245;43:410`, `267:19246`, `267:19247`, `I267:19247;43:410`, `267:19248`, `I267:19248;43:410`, `267:19249`, `I267:19249;43:422`, `267:19250`, `I267:19250;43:410`, `267:19251`, `267:19252`, `267:19253`, `267:19254`, `I267:19254;43:410`, `267:19255`, `267:19256`, `267:19257`, `267:19260`, `267:19261`, `267:19264`, `267:19265`, `267:19266`, `267:19267`, `267:19268`, `267:19269`, `267:19270`, `267:19271`, `267:19355`, `267:19321`

### Frame `267:19356` — 26 existing nodes

`267:19356`, `267:19361`, `267:19362`, `267:19363`, `267:19364`, `267:19365`, `267:19366`, `267:19367`, `267:19368`, `267:19369`, `267:19372`, `267:19373`, `267:19374`, `267:19375`, `267:19376`, `267:19377`, `267:19378`, `267:19379`, `267:19380`, `267:19381`, `267:19382`, `267:19383`, `267:19423`, `267:19419`, `267:19420`, `267:19421`

### Frame `267:19424` — 45 existing nodes

`267:19424`, `267:19429`, `267:19430`, `267:19431`, `267:19432`, `267:19433`, `267:19434`, `I267:19434;43:410`, `267:19435`, `I267:19435;43:410`, `267:19436`, `I267:19436;43:410`, `267:19437`, `I267:19437;43:410`, `267:19438`, `267:19439`, `I267:19439;43:410`, `267:19440`, `I267:19440;43:410`, `267:19441`, `I267:19441;43:422`, `267:19442`, `I267:19442;43:410`, `267:19443`, `267:19444`, `267:19445`, `267:19446`, `I267:19446;43:410`, `267:19447`, `267:19448`, `267:19449`, `267:19452`, `267:19453`, `267:19456`, `267:19457`, `267:19458`, `267:19459`, `267:19460`, `267:19461`, `267:19462`, `267:19463`, `267:19464`, `267:19465`, `267:19561`, `267:19524`

### Frame `267:19562` — 28 existing nodes

`267:19562`, `267:19567`, `267:19568`, `267:19569`, `267:19570`, `267:19571`, `267:19572`, `267:19573`, `267:19574`, `267:19575`, `267:19578`, `267:19579`, `267:19580`, `267:19581`, `267:19582`, `267:19583`, `267:19584`, `267:19585`, `267:19586`, `267:19587`, `267:19588`, `267:19589`, `267:19590`, `267:19591`, `267:19641`, `267:19625`, `267:19626`, `267:19627`

## Every created node ID

The five linked CRM shells and their inherited descendants create **310 nodes**, listed exhaustively below. Hidden stock navigation descendants are included. The only visible text overrides in these new instances are `Business` → existing `{Store name}` and `Trigger` → existing `Tiger`.

### Frame `256:10` — CRM instance `465:26693`

`465:26693`, `I465:26693;180:8388`, `I465:26693;180:8389`, `I465:26693;180:8390`, `I465:26693;180:8391`, `I465:26693;180:8392`, `I465:26693;180:8393`, `I465:26693;180:8394`, `I465:26693;180:8395`, `I465:26693;180:8396`, `I465:26693;180:8397`, `I465:26693;180:8398`, `I465:26693;180:8398;43:410`, `I465:26693;180:8401`, `I465:26693;180:8401;43:410`, `I465:26693;180:8404`, `I465:26693;180:8405`, `I465:26693;180:8406`, `I465:26693;180:8406;43:410`, `I465:26693;180:8409`, `I465:26693;180:8409;43:410`, `I465:26693;180:8412`, `I465:26693;180:8412;43:410`, `I465:26693;180:8415`, `I465:26693;180:8415;43:410`, `I465:26693;180:8418`, `I465:26693;180:8418;43:410`, `I465:26693;180:8421`, `I465:26693;180:8421;43:410`, `I465:26693;180:8424`, `I465:26693;180:8425`, `I465:26693;180:8426`, `I465:26693;180:8426;43:410`, `I465:26693;180:8429`, `I465:26693;180:8429;43:410`, `I465:26693;180:8432`, `I465:26693;180:8433`, `I465:26693;180:8434`, `I465:26693;180:8434;43:410`, `I465:26693;180:8437`, `I465:26693;180:8437;43:410`, `I465:26693;180:8440`, `I465:26693;180:8440;43:410`, `I465:26693;465:25708`, `I465:26693;465:25708;43:410`, `I465:26693;180:8443`, `I465:26693;180:8443;43:410`, `I465:26693;180:8446`, `I465:26693;180:8447`, `I465:26693;180:8448`, `I465:26693;180:8448;43:410`, `I465:26693;180:8451`, `I465:26693;180:8451;43:410`, `I465:26693;180:8454`, `I465:26693;180:8455`, `I465:26693;180:8455;43:410`, `I465:26693;180:8458`, `I465:26693;180:8458;43:410`, `I465:26693;180:8461`, `I465:26693;180:8461;43:410`, `I465:26693;180:8464`, `I465:26693;180:8464;43:410`

### Frame `256:283` — CRM instance `465:26776`

`465:26776`, `I465:26776;180:8388`, `I465:26776;180:8389`, `I465:26776;180:8390`, `I465:26776;180:8391`, `I465:26776;180:8392`, `I465:26776;180:8393`, `I465:26776;180:8394`, `I465:26776;180:8395`, `I465:26776;180:8396`, `I465:26776;180:8397`, `I465:26776;180:8398`, `I465:26776;180:8398;43:410`, `I465:26776;180:8401`, `I465:26776;180:8401;43:410`, `I465:26776;180:8404`, `I465:26776;180:8405`, `I465:26776;180:8406`, `I465:26776;180:8406;43:410`, `I465:26776;180:8409`, `I465:26776;180:8409;43:410`, `I465:26776;180:8412`, `I465:26776;180:8412;43:410`, `I465:26776;180:8415`, `I465:26776;180:8415;43:410`, `I465:26776;180:8418`, `I465:26776;180:8418;43:410`, `I465:26776;180:8421`, `I465:26776;180:8421;43:410`, `I465:26776;180:8424`, `I465:26776;180:8425`, `I465:26776;180:8426`, `I465:26776;180:8426;43:410`, `I465:26776;180:8429`, `I465:26776;180:8429;43:410`, `I465:26776;180:8432`, `I465:26776;180:8433`, `I465:26776;180:8434`, `I465:26776;180:8434;43:410`, `I465:26776;180:8437`, `I465:26776;180:8437;43:410`, `I465:26776;180:8440`, `I465:26776;180:8440;43:410`, `I465:26776;465:25708`, `I465:26776;465:25708;43:410`, `I465:26776;180:8443`, `I465:26776;180:8443;43:410`, `I465:26776;180:8446`, `I465:26776;180:8447`, `I465:26776;180:8448`, `I465:26776;180:8448;43:410`, `I465:26776;180:8451`, `I465:26776;180:8451;43:410`, `I465:26776;180:8454`, `I465:26776;180:8455`, `I465:26776;180:8455;43:410`, `I465:26776;180:8458`, `I465:26776;180:8458;43:410`, `I465:26776;180:8461`, `I465:26776;180:8461;43:410`, `I465:26776;180:8464`, `I465:26776;180:8464;43:410`

### Frame `256:471` — CRM instance `465:26859`

`465:26859`, `I465:26859;180:8388`, `I465:26859;180:8389`, `I465:26859;180:8390`, `I465:26859;180:8391`, `I465:26859;180:8392`, `I465:26859;180:8393`, `I465:26859;180:8394`, `I465:26859;180:8395`, `I465:26859;180:8396`, `I465:26859;180:8397`, `I465:26859;180:8398`, `I465:26859;180:8398;43:410`, `I465:26859;180:8401`, `I465:26859;180:8401;43:410`, `I465:26859;180:8404`, `I465:26859;180:8405`, `I465:26859;180:8406`, `I465:26859;180:8406;43:410`, `I465:26859;180:8409`, `I465:26859;180:8409;43:410`, `I465:26859;180:8412`, `I465:26859;180:8412;43:410`, `I465:26859;180:8415`, `I465:26859;180:8415;43:410`, `I465:26859;180:8418`, `I465:26859;180:8418;43:410`, `I465:26859;180:8421`, `I465:26859;180:8421;43:410`, `I465:26859;180:8424`, `I465:26859;180:8425`, `I465:26859;180:8426`, `I465:26859;180:8426;43:410`, `I465:26859;180:8429`, `I465:26859;180:8429;43:410`, `I465:26859;180:8432`, `I465:26859;180:8433`, `I465:26859;180:8434`, `I465:26859;180:8434;43:410`, `I465:26859;180:8437`, `I465:26859;180:8437;43:410`, `I465:26859;180:8440`, `I465:26859;180:8440;43:410`, `I465:26859;465:25708`, `I465:26859;465:25708;43:410`, `I465:26859;180:8443`, `I465:26859;180:8443;43:410`, `I465:26859;180:8446`, `I465:26859;180:8447`, `I465:26859;180:8448`, `I465:26859;180:8448;43:410`, `I465:26859;180:8451`, `I465:26859;180:8451;43:410`, `I465:26859;180:8454`, `I465:26859;180:8455`, `I465:26859;180:8455;43:410`, `I465:26859;180:8458`, `I465:26859;180:8458;43:410`, `I465:26859;180:8461`, `I465:26859;180:8461;43:410`, `I465:26859;180:8464`, `I465:26859;180:8464;43:410`

### Frame `267:19232` — CRM instance `465:26942`

`465:26942`, `I465:26942;180:8388`, `I465:26942;180:8389`, `I465:26942;180:8390`, `I465:26942;180:8391`, `I465:26942;180:8392`, `I465:26942;180:8393`, `I465:26942;180:8394`, `I465:26942;180:8395`, `I465:26942;180:8396`, `I465:26942;180:8397`, `I465:26942;180:8398`, `I465:26942;180:8398;43:410`, `I465:26942;180:8401`, `I465:26942;180:8401;43:410`, `I465:26942;180:8404`, `I465:26942;180:8405`, `I465:26942;180:8406`, `I465:26942;180:8406;43:410`, `I465:26942;180:8409`, `I465:26942;180:8409;43:410`, `I465:26942;180:8412`, `I465:26942;180:8412;43:410`, `I465:26942;180:8415`, `I465:26942;180:8415;43:410`, `I465:26942;180:8418`, `I465:26942;180:8418;43:410`, `I465:26942;180:8421`, `I465:26942;180:8421;43:410`, `I465:26942;180:8424`, `I465:26942;180:8425`, `I465:26942;180:8426`, `I465:26942;180:8426;43:410`, `I465:26942;180:8429`, `I465:26942;180:8429;43:410`, `I465:26942;180:8432`, `I465:26942;180:8433`, `I465:26942;180:8434`, `I465:26942;180:8434;43:410`, `I465:26942;180:8437`, `I465:26942;180:8437;43:410`, `I465:26942;180:8440`, `I465:26942;180:8440;43:410`, `I465:26942;465:25708`, `I465:26942;465:25708;43:410`, `I465:26942;180:8443`, `I465:26942;180:8443;43:410`, `I465:26942;180:8446`, `I465:26942;180:8447`, `I465:26942;180:8448`, `I465:26942;180:8448;43:410`, `I465:26942;180:8451`, `I465:26942;180:8451;43:410`, `I465:26942;180:8454`, `I465:26942;180:8455`, `I465:26942;180:8455;43:410`, `I465:26942;180:8458`, `I465:26942;180:8458;43:410`, `I465:26942;180:8461`, `I465:26942;180:8461;43:410`, `I465:26942;180:8464`, `I465:26942;180:8464;43:410`

### Frame `267:19424` — CRM instance `465:27025`

`465:27025`, `I465:27025;180:8388`, `I465:27025;180:8389`, `I465:27025;180:8390`, `I465:27025;180:8391`, `I465:27025;180:8392`, `I465:27025;180:8393`, `I465:27025;180:8394`, `I465:27025;180:8395`, `I465:27025;180:8396`, `I465:27025;180:8397`, `I465:27025;180:8398`, `I465:27025;180:8398;43:410`, `I465:27025;180:8401`, `I465:27025;180:8401;43:410`, `I465:27025;180:8404`, `I465:27025;180:8405`, `I465:27025;180:8406`, `I465:27025;180:8406;43:410`, `I465:27025;180:8409`, `I465:27025;180:8409;43:410`, `I465:27025;180:8412`, `I465:27025;180:8412;43:410`, `I465:27025;180:8415`, `I465:27025;180:8415;43:410`, `I465:27025;180:8418`, `I465:27025;180:8418;43:410`, `I465:27025;180:8421`, `I465:27025;180:8421;43:410`, `I465:27025;180:8424`, `I465:27025;180:8425`, `I465:27025;180:8426`, `I465:27025;180:8426;43:410`, `I465:27025;180:8429`, `I465:27025;180:8429;43:410`, `I465:27025;180:8432`, `I465:27025;180:8433`, `I465:27025;180:8434`, `I465:27025;180:8434;43:410`, `I465:27025;180:8437`, `I465:27025;180:8437;43:410`, `I465:27025;180:8440`, `I465:27025;180:8440;43:410`, `I465:27025;465:25708`, `I465:27025;465:25708;43:410`, `I465:27025;180:8443`, `I465:27025;180:8443;43:410`, `I465:27025;180:8446`, `I465:27025;180:8447`, `I465:27025;180:8448`, `I465:27025;180:8448;43:410`, `I465:27025;180:8451`, `I465:27025;180:8451;43:410`, `I465:27025;180:8454`, `I465:27025;180:8455`, `I465:27025;180:8455;43:410`, `I465:27025;180:8458`, `I465:27025;180:8458;43:410`, `I465:27025;180:8461`, `I465:27025;180:8461;43:410`, `I465:27025;180:8464`, `I465:27025;180:8464;43:410`

## Verification commands and results

Read-only Git checks confirmed the requested branch and fetched `origin/codex/tiger-figma`; the starting tree was clean and up to date. Design-system discovery found no Code Connect mapping in this checkout. Existing local CRM component `180:8387`, approved reference `182:9119`, and existing colour/spacing bindings were used; unrelated community library search results were not substituted.

An oversized read was narrowed to per-frame compact snapshots. One transient sizing pass was rejected before commit because minimum size cannot be overridden inside an instance; it was retried with permitted instance geometry only. The first persisted-height audit caught auto-layout reflow shrinking controls, and explicit final heights corrected it. Final audits and screenshots listed above were taken after these fixes.

Documentation checks: `git diff --check`, exact ID coverage/counts, two original-text changes only, all ten source-frame IDs retained, all original descendant IDs retained, and only this Markdown file in `git diff --name-only origin/main...HEAD`. Application tests are not applicable to this Figma/document-only change.

Push target: `origin codex/tiger-figma`. The commit/push result is reported in this chat; no PR is created by this pass, following the existing register handoff that Claude opens the PR.

---

## Previous register — historical handoff
# Tiger price position — design check, 3 Nov

The founder approved the baseline on 3 Nov, as reported in this task. Every modified/new frame and its review top bar now records **Approved 3 Nov** and **Changed after approval, awaiting founder**. All ten frames have changed wording; the earlier approval does not approve these changes.

Page: [9 · Tiger price position](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=256-9), node `256:9`. Same branch: `codex/tiger-figma`. Only this document is committed. No application or live-data changes; nothing merged or deployed. Claude opens the PR and the founder merges.

## Frame map — one line per frame

All rows below have both approval-history and awaiting-founder labels.

| Frame | Node ID | Size | Existing components reused |
| --- | --- | --- | --- |
| Price position | [256:10](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=256-10) | 1440 × 1292 | TigerApp panel, Side menu items 43:409/43:421, SimpleTable, Table header 43:389, PageLink, AttemptTime, Pill/RowStatus |
| Price position | [256:170](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=256-170) | 375 × 2336 | TigerApp mobile bar 53:5990, Overview .cards, Table row 43:405, PageLink, AttemptTime, Pill/RowStatus |
| Matches to review, pending and rejected rows | [256:283](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=256-283) | 1440 × 1114 | TigerApp panel, Side menu items, SimpleTable, Table header 43:389, PageLink, button.line.small, button.text |
| Matches to review, pending and rejected cards | [256:406](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=256-406) | 375 × 1776 | Mobile bar 53:5990, Overview .cards, PageLink, button.line.small, button.text, .row-actions |
| Competitor sites | [256:471](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=256-471) | 1440 × 1070 | TigerApp panel, Side menu items, Plugins Source links, SimpleTable, Table header 43:389, Pill/RowStatus |
| Competitor sites | [256:609](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=256-609) | 375 × 1878 | Mobile bar 53:5990, responsive Source links, Overview .cards, Table row 43:405, Pill/RowStatus |
| Matches to review — empty | [267:19232](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=267-19232) | 1440 × 989 | Existing desktop Matches shell and controls; Tiger empty-text pattern |
| Matches to review — empty | [267:19356](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=267-19356) | 375 × 713 | Existing mobile Matches shell and controls; Tiger empty-text pattern |
| Competitor sites — empty | [267:19424](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=267-19424) | 1440 × 989 | Existing desktop sites shell and controls; Tiger empty-text pattern |
| Competitor sites — empty | [267:19562](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=267-19562) | 375 × 794 | Existing mobile sites shell and controls; Tiger empty-text pattern |

All six original frame IDs survive. Four new frames cover the two empty states at both widths. The second original Matches row/card demonstrates Rejected with Undo; the first retains Confirm and Reject.

## Changed node IDs and behavior

- Approval bars retained: `256:11`, `256:171`, `256:284`, `256:407`, `256:472`, `256:610`. Existing heading/body text IDs retained. New illustrative-data annotations: `267:19218`, `267:19219`, `267:19220`, `267:19224`, `267:19230`, `267:19231`.
- South shop becomes saved North shop at `256:377`, `256:378`, `256:448`, including evidence hyperlinks to `https://north-shop.example/products/desk-lamp`. All illustrative competitors are saved North, West or East sites. Reserved .example links remain Figma-only examples, not claimed observations.
- Duplicate section strips removed: desktop `256:59`, `256:332`, `256:520`; mobile `256:189`, `256:425`, `256:628`. Desktop section navigation remains once in the panel, as in TigerApp; mobile uses Menu.
- Repeated view-heading text removed: `256:65`, `256:195`, `256:338`, `256:431`, `256:526`, `256:634`. Each view name appears once in its segment below the Tiger heading.
- Shared Matches intro removed at `256:346`, `256:439`. Its unchanged sentence is now each row/card's reason: `267:19222`, `267:19223`, `267:19226`, `267:19228`.
- Rejected/Undo retain original text IDs: desktop `256:400`/`256:402`; mobile `256:465`/`256:467`. Rejected is plain status, not a Confirm-style button; evidence is retained.
- Explicit mobile competitor-page links added at `267:19227`, `267:19229`, with the North/East page URLs and placed before actions.
- Empty text nodes: `267:19355`, `267:19423` = No matches to review.; `267:19561`, `267:19641` = No saved sites.
- Warning text/pill pairs: stale `256:127`/`256:125`, `256:228`/`256:226`; human check `256:588`/`256:586`, `256:670`/`256:668`; robots `256:604`/`256:602`, `256:684`/`256:682`. Text, border and dot use existing light warning colour `--warn: #b45309` from `workspace/app/globals.css:60`. Checked stays neutral. No Figma warning token exists, so this source value was used directly rather than inventing a token.
- Compact desktop rows retain IDs: price `256:101`, `256:133`, `256:153`; matches `256:366`, `256:385`; sites `256:559`, `256:575`, `256:591`. Row height now fits the tallest content cell plus existing padding. Empty desktop panel height accommodates History and Support.
- Aligned missing-value glyphs: `256:149`–`256:151`, `256:164`–`256:166`, all Inter 14px / 21px. Desktop difference `256:131` matches mobile `I256:237;43:407`: +£20.00 · +20%. Desktop Difference column widened to 160px.
- Native Tiger logo rule: original Tiger artwork is 48px high at native 2607:801 aspect ratio in the desktop panel (`256:16`, `256:289`, `256:477`). Mobile bar is 67px high with actual original Tervory artwork resized to 186 × 34 (`256:177`, `256:413`, `256:616`); new empty mobile artwork `267:19364`, `267:19570` uses the same rule. No logo redrawn.
- Search text updated: `256:55`, `256:185`, `256:328`, `256:421`, `256:516`, `256:624`; copied to empty frames.
- Mobile attempt wording: `256:667`, `256:681`.
- Plugins navigation `256:535`, `256:643` is underlined as a link and copied to empty sites frames. No working application route was invented.

## Added or changed words awaiting founder

| Exact text | Purpose |
| --- | --- |
| Approved 3 Nov | Baseline approval history |
| Changed after approval, awaiting founder | Current review status |
| Illustrative values · Figma only. | Review annotation |
| Search watched products, readings and alerts | Search placeholder |
| North shop ↗ | Saved-site correction |
| North shop · page evidence ↗ | Evidence-link correction |
| Rejected | Row status |
| Undo | Rejected-row action |
| No matches to review. | Empty Matches |
| No saved sites. | Empty sites |
| Blocked by a human check | Warning |
| Some pages closed to robots | Warning |
| Last attempt: 25 minutes ago | Corrected mobile metadata |
| Last attempt: 1 hour ago | Same correction on the other attempted check |
| Competitor page: north-shop.example/products/desk-lamp ↗ | Explicit mobile page link |
| Competitor page: east-shop.example/products/wall-lamp ↗ | Explicit mobile page link |
| +£20.00 · +20% | Shared difference format |

Moved, not rewritten: “Same brand and maker part number. No barcode match. Confirm the product before it affects price position.” It now belongs to each row. The previously approved price-position rule and all other unchanged wording remain intact.

## Reuse and validation

Baseline source commit `bb3200835b519826b4664418c4ccb5ab900cff73`; previous design handoff `ad4168a8`. Sources: `workspace/app/tiger/view.tsx`, `tiger.css`, Tiger Plugins Source links and existing Figma Tiger frames/components. Live logo rules are at `view.tsx:87` onward and `tiger.css:129` onward. Original pages and main components were not edited.

Ten editable frames: five at 1440 and five at 375. Final bounds audit found zero text outside its frame or immediate parent, zero old South shop / reads and alerts / Last checked: Attempted wording, and verified Jost Light plus Inter Regular/Medium/Semi Bold. Original discrete logos are the only raster images; no flattened UI image is a design layer. Existing spacing, colour and type bindings remain.

The initial audit found sidebar overflow on short empty desktop frames; minimum panel height was corrected before final verification. Full-frame screenshots were inspected for corrected desktop price, desktop/mobile Matches, desktop/mobile sites, desktop Matches empty and mobile sites empty. The mobile Matches screenshot was checked again after correcting the actual logo image size. These are agent visual checks. Baseline founder approval is recorded from the user's message; acceptance and founder screenshots for the changes remain pending.

## Commands and results

Required branch/source checks and reads:

```sh
git status --short --branch
git branch --show-current
cat docs/figma/TIGER-POSITION-FRAMES.md
sed -n '80,160p' workspace/app/tiger/view.tsx
rg -n 'warn|warning|logo|topbar|panel-top' workspace/app/tiger/tiger.css
rg -n -i 'warn(ing)?[^\n]{0,70}(#|color)|#[a-f0-9]{3,8}[^\n]{0,50}warn' workspace/app workspace/components | head -n 45
nl -ba workspace/app/globals.css | sed -n '55,63p'
```

Result: correct branch, clean starting tree and all required brief files present. The optional warning search reported that `workspace/components` does not exist; the existing warning colour was found in `workspace/app/globals.css`. No required file was missing. The first document replacement tool call failed validation before changing the document; it was corrected with a single-file write. Design orchestration scripts are transient under `.git/tiger-design/` and not tracked.

Final commands:

```sh
git diff --check
git add docs/figma/TIGER-POSITION-FRAMES.md
git commit -m 'docs(figma): record Tiger post-approval design corrections'
git push origin codex/tiger-figma
git diff --check origin/main...HEAD
git diff --name-only origin/main...HEAD
git status --short --branch
```

The command output in this task records the results. Only this document may differ from main. No application tests are needed for this Figma-only change; no runtime feature is claimed to work. The founder must approve changed/new words before build.
