# MCP Figma register

Updated 3 Nov 2026 for the founder rule 9 follow-up. The explicit navy-primary-button ruling supersedes the previous treatment of controls as backgrounds.

[Figma page 7 · MCP](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=230-9). All 44 original frame IDs remain. Added 24 missing states, for 68 frames total.

2 frames: **Approved 3 Nov**. The other 66 frames say **Changed after approval, awaiting founder**. Frame 231:12680 and notice 231:12682 now carry the latter label.

Rule 9: page surfaces remain light. The 52 main controls (Approve, Add, Add server, Add connection, Try again and Sign in with the provider) have navy #001840 fills and white labels. Deny, Cancel, Disconnect and Revoke remain white with navy text. Remove server styling is unchanged. Brand red #E80008 remains confined to logo image assets.

CRM Action 93:4, Field 93:6 and white navigation 182:9119 / 180:8387 (mobile variant 180:8467) are reused. Shared main components and production code were not changed. The shared CRM navigation and its Close button were not edited. Organization is consistent in copy and layer names. All 56 duplicate content identity/logo blocks were removed; 28 Rig/Tisan text nodes were preserved outside those blocks.

Preserved intro IDs 239:102 and 239:110. Removed choice blocks 239:95 and 239:103, including 239:96 and old wording 231:11802 / 231:11840. Removed return-host field instances 231:10280 / 231:10330.

Revoke confirmations cover computer and app rows on desktop/mobile. All 12 existing Rig/Tisan Disconnect actions open corresponding confirmation frames. Expand/collapse and Add connection controls link to their states. New reason, confirmation, empty-state and error wording awaits founder approval.

## Verification

All 68 frames passed the rule 9 audit: correct primary/secondary palettes, no duplicate content logos, correct terminology and heading colors, correct address typography, no horizontal content overflow, wrong fonts or dark non-control content surfaces. All 38 section headings (10 MCP servers, 28 MCP connections) use #3d4a66. Both server addresses use Inter Regular 14. Button labels measure at least 17.44:1 contrast. All six toggles have #76839a track strokes with at least 3.11:1 contrast against their light track fills and navy knobs; on is right, off is left, with existing Allowed / Not allowed labels. Field edges retain the previous verified contrast. Mobile content scrolls as needed; consent actions remain pinned.

[Rule 9: every changed and removed node, plus exact wording changes](MCP-RULE9-20261103.md) · [Rule 9 changes JSON](mcp-evidence-rule9-20261103/changes.json) · [Before](mcp-evidence-rule9-20261103/before.json) · [After](mcp-evidence-rule9-20261103/after.json) · [Validation](mcp-evidence-rule9-20261103/validation.json) · [Operations](mcp-evidence-rule9-20261103/operations.json). The previous pass remains recorded in [its historical change list](MCP-CHANGES-20261103.md).

Wording: recognize replaces recognise in the four intro nodes. The computer row now uses [Computer], Computer, and Computer name as the computer reported it. No other production wording was added. The Add server notice now says Changed after approval, awaiting founder.

## Screenshots

- [Control panel desktop](mcp-evidence-rule9-20261103/control-desktop.png)
- [Control panel mobile](mcp-evidence-rule9-20261103/control-mobile.png)
- [Rig mobile](mcp-evidence-rule9-20261103/rig-mobile.png)
- [Consent mobile with pinned primary Approve](mcp-evidence-rule9-20261103/consent-mobile.png)

## Frames

| ID | Frame and status | Navigation |
| --- | --- | --- |
| [`231:10255`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-10255) | Connect consent / Pending / Desktop / Changed after approval, awaiting founder | External consent |
| [`231:10306`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-10306) | Connect consent / Pending / Mobile / Changed after approval, awaiting founder | External consent |
| [`231:10356`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-10356) | Connect consent / Approved / Desktop / Approved 3 Nov | External consent |
| [`231:10376`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-10376) | Connect consent / Approved / Mobile / Approved 3 Nov | External consent |
| [`231:10396`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-10396) | Connect consent / Denied / Desktop / Changed after approval, awaiting founder | External consent |
| [`231:10416`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-10416) | Connect consent / Denied / Mobile / Changed after approval, awaiting founder | External consent |
| [`231:10436`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-10436) | Connect consent / Invalid / Desktop / Changed after approval, awaiting founder | External consent |
| [`231:10456`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-10456) | Connect consent / Invalid / Mobile / Changed after approval, awaiting founder | External consent |
| [`231:10476`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-10476) | Connect consent / Expired / Desktop / Changed after approval, awaiting founder | External consent |
| [`231:10496`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-10496) | Connect consent / Expired / Mobile / Changed after approval, awaiting founder | External consent |
| [`231:10516`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-10516) | Connect consent / ZA founder refusal / Desktop / Changed after approval, awaiting founder | External consent |
| [`231:10539`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-10539) | Connect consent / ZA founder refusal / Mobile / Changed after approval, awaiting founder | External consent |
| [`231:11794`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-11794) | CLI sign-ins and connected apps / Connected / Desktop / Changed after approval, awaiting founder | `465:43393` |
| [`231:11832`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-11832) | CLI sign-ins and connected apps / Connected / Mobile / Changed after approval, awaiting founder | `465:43476` |
| [`231:11870`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-11870) | Rig Plugins / MCP connections / Saved with a token / Desktop / Changed after approval, awaiting founder | `465:45832` |
| [`231:11900`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-11900) | Rig Plugins / MCP connections / Saved with a token / Mobile / Changed after approval, awaiting founder | `465:45919` |
| [`231:11930`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-11930) | Rig Plugins / MCP connections / Needs sign-in / Desktop / Changed after approval, awaiting founder | `465:46007` |
| [`231:11958`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-11958) | Rig Plugins / MCP connections / Needs sign-in / Mobile / Changed after approval, awaiting founder | `465:46094` |
| [`231:11986`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-11986) | Rig Plugins / MCP connections / Connected / Desktop / Changed after approval, awaiting founder | `465:46183` |
| [`231:12014`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-12014) | Rig Plugins / MCP connections / Connected / Mobile / Changed after approval, awaiting founder | `465:46270` |
| [`231:12042`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-12042) | Rig Plugins / MCP connections / Sign-in failed / Desktop / Changed after approval, awaiting founder | `465:46359` |
| [`231:12070`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-12070) | Rig Plugins / MCP connections / Sign-in failed / Mobile / Changed after approval, awaiting founder | `465:46447` |
| [`231:12098`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-12098) | Rig Plugins / MCP connections / Server not approved by Tervory / Desktop / Changed after approval, awaiting founder | `465:47228` |
| [`231:12124`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-12124) | Rig Plugins / MCP connections / Server not approved by Tervory / Mobile / Changed after approval, awaiting founder | `465:47318` |
| [`231:12150`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-12150) | Rig Plugins / MCP connections / Expanded / Desktop / Changed after approval, awaiting founder | `465:47406` |
| [`231:12187`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-12187) | Rig Plugins / MCP connections / Expanded / Mobile / Changed after approval, awaiting founder | `465:47493` |
| [`231:12224`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-12224) | Tisan Plugins / MCP connections / Saved with a token / Desktop / Changed after approval, awaiting founder | `465:47581` |
| [`231:12254`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-12254) | Tisan Plugins / MCP connections / Saved with a token / Mobile / Changed after approval, awaiting founder | `465:47668` |
| [`231:12284`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-12284) | Tisan Plugins / MCP connections / Needs sign-in / Desktop / Changed after approval, awaiting founder | `465:47756` |
| [`231:12312`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-12312) | Tisan Plugins / MCP connections / Needs sign-in / Mobile / Changed after approval, awaiting founder | `465:47843` |
| [`231:12340`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-12340) | Tisan Plugins / MCP connections / Connected / Desktop / Changed after approval, awaiting founder | `465:47931` |
| [`231:12368`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-12368) | Tisan Plugins / MCP connections / Connected / Mobile / Changed after approval, awaiting founder | `465:48018` |
| [`231:12396`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-12396) | Tisan Plugins / MCP connections / Sign-in failed / Desktop / Changed after approval, awaiting founder | `465:48107` |
| [`231:12424`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-12424) | Tisan Plugins / MCP connections / Sign-in failed / Mobile / Changed after approval, awaiting founder | `465:48195` |
| [`231:12452`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-12452) | Tisan Plugins / MCP connections / Server not approved by Tervory / Desktop / Changed after approval, awaiting founder | `465:48286` |
| [`231:12478`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-12478) | Tisan Plugins / MCP connections / Server not approved by Tervory / Mobile / Changed after approval, awaiting founder | `465:48376` |
| [`231:12504`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-12504) | Tisan Plugins / MCP connections / Expanded / Desktop / Changed after approval, awaiting founder | `465:48464` |
| [`231:12541`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-12541) | Tisan Plugins / MCP connections / Expanded / Mobile / Changed after approval, awaiting founder | `465:48551` |
| [`231:12578`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-12578) | Founder MCP servers / Servers / Desktop / Changed after approval, awaiting founder | `465:48656` |
| [`231:12629`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-12629) | Founder MCP servers / Servers / Mobile / Changed after approval, awaiting founder | `465:48743` |
| [`231:12680`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-12680) | Founder MCP servers / Add server / Desktop / Changed after approval, awaiting founder | `465:48828` |
| [`231:12712`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-12712) | Founder MCP servers / Add server / Mobile / Changed after approval, awaiting founder | `465:48912` |
| [`231:12744`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-12744) | Founder MCP servers / Remove server / Desktop / Changed after approval, awaiting founder | `465:48997` |
| [`231:12774`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-12774) | Founder MCP servers / Remove server / Mobile / Changed after approval, awaiting founder | `465:49081` |
| [`468:26067`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=468-26067) | Computers and connected apps / Revoke Computer / Desktop / Changed after approval, awaiting founder | `468:26071` |
| [`468:26173`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=468-26173) | Computers and connected apps / Revoke Computer / Mobile / Changed after approval, awaiting founder | `468:26177` |
| [`468:26207`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=468-26207) | Computers and connected apps / Revoke App / Desktop / Changed after approval, awaiting founder | `468:26211` |
| [`468:26313`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=468-26313) | Computers and connected apps / Revoke App / Mobile / Changed after approval, awaiting founder | `468:26317` |
| [`468:26347`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=468-26347) | Rig Plugins / Disconnect / Desktop / Changed after approval, awaiting founder | `468:26351` |
| [`468:26455`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=468-26455) | Rig Plugins / Disconnect / Mobile / Changed after approval, awaiting founder | `468:26459` |
| [`468:26491`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=468-26491) | Tisan Plugins / Disconnect / Desktop / Changed after approval, awaiting founder | `468:26495` |
| [`468:26599`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=468-26599) | Tisan Plugins / Disconnect / Mobile / Changed after approval, awaiting founder | `468:26603` |
| [`468:27698`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=468-27698) | Rig Plugins / Add connection / Desktop / Changed after approval, awaiting founder | `468:27702` |
| [`468:27804`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=468-27804) | Rig Plugins / Empty / Desktop / Changed after approval, awaiting founder | `468:27808` |
| [`468:27919`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=468-27919) | Rig Plugins / Add connection / Mobile / Changed after approval, awaiting founder | `468:27923` |
| [`468:27953`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=468-27953) | Rig Plugins / Empty / Mobile / Changed after approval, awaiting founder | `468:27957` |
| [`468:27996`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=468-27996) | Tisan Plugins / Add connection / Desktop / Changed after approval, awaiting founder | `468:28000` |
| [`468:28102`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=468-28102) | Tisan Plugins / Empty / Desktop / Changed after approval, awaiting founder | `468:28106` |
| [`468:28217`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=468-28217) | Tisan Plugins / Add connection / Mobile / Changed after approval, awaiting founder | `468:28221` |
| [`468:28251`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=468-28251) | Tisan Plugins / Empty / Mobile / Changed after approval, awaiting founder | `468:28255` |
| [`468:30889`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=468-30889) | Founder MCP servers / Add server / Bad address / Desktop / Changed after approval, awaiting founder | `468:30893` |
| [`468:30996`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=468-30996) | Founder MCP servers / Add server / Bad address / Mobile / Changed after approval, awaiting founder | `468:31000` |
| [`468:31031`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=468-31031) | Founder MCP servers / Add server / Duplicate / Desktop / Changed after approval, awaiting founder | `468:31035` |
| [`468:31138`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=468-31138) | Founder MCP servers / Add server / Duplicate / Mobile / Changed after approval, awaiting founder | `468:31142` |
| [`468:31173`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=468-31173) | Founder MCP servers / Add server / Unreachable / Desktop / Changed after approval, awaiting founder | `468:31177` |
| [`468:31280`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=468-31280) | Founder MCP servers / Add server / Unreachable / Mobile / Changed after approval, awaiting founder | `468:31284` |
| [`468:31315`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=468-31315) | Computers and connected apps / Empty / Desktop / Changed after approval, awaiting founder | `468:31319` |
| [`468:31427`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=468-31427) | Computers and connected apps / Empty / Mobile / Changed after approval, awaiting founder | `468:31431` |
