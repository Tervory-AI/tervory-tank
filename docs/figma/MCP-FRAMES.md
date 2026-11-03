# MCP Figma register

Updated 3 Nov 2026 from the founder correction brief and the 11:37 PT ruling.

[Figma page 7 · MCP](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=230-9). All 44 original frame IDs remain. Added 24 missing states, for 68 frames total.

3 frames: **Approved 3 Nov**. The other 65 frames contain changed or new wording and say **Changed after approval, awaiting founder**.

The latest ruling supersedes earlier dark action fills: every surface on this page is light, including action buttons. White surfaces use navy #001840 text. Remove server confirmation uses #b91c1c text and stroke on white. Brand red #E80008 is confined to logo image assets.

CRM Action 93:4, Field 93:6 and white navigation 182:9119 / 180:8387 (mobile variant 180:8467) are reused. Shared main components and production code were not changed. Organization is consistent in copy and layer names.

Preserved intro IDs 239:102 and 239:110. Removed choice blocks 239:95 and 239:103, including 239:96 and old wording 231:11802 / 231:11840. Removed return-host field instances 231:10280 / 231:10330.

Revoke confirmations cover computer and app rows on desktop/mobile. All 12 existing Rig/Tisan Disconnect actions open corresponding confirmation frames. Expand/collapse and Add connection controls link to their states. New reason, confirmation, empty-state and error wording awaits founder approval.

## Verification

All 68 frames passed: no dark surface fills, horizontal content overflow, stale wording, 14px cards, off-grid content spacing, wrong fonts or missing in-app navigation. Button labels have at least 6.47:1 contrast. Field edges measure at least 3.83:1 on white and 3.54:1 on #f4f6fa. Text uses Jost Light and Inter. Mobile content scrolls as needed; consent actions remain pinned.

[Every changed node and all new words](MCP-CHANGES-20261103.md) · [Changes JSON](mcp-evidence-20261103/changes.json) · [Before](mcp-evidence-20261103/before.json) · [After](mcp-evidence-20261103/after.json) · [Validation](mcp-evidence-20261103/validation.json) · [Full mutation records](mcp-evidence-20261103/operations.json). Additional hidden navigation IDs are listed from operation records because final reads do not return them.

## Screenshots

- [control-desktop](mcp-evidence-20261103/control-desktop.png)
- [consent-mobile](mcp-evidence-20261103/consent-mobile.png)
- [rig-mobile](mcp-evidence-20261103/rig-mobile.png)
- [sign-in-failed-mobile](mcp-evidence-20261103/sign-in-failed-mobile.png)
- [disconnect-mobile](mcp-evidence-20261103/disconnect-mobile.png)
- [server-unreachable-mobile](mcp-evidence-20261103/server-unreachable-mobile.png)

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
| [`231:12680`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=231-12680) | Founder MCP servers / Add server / Desktop / Approved 3 Nov | `465:48828` |
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
