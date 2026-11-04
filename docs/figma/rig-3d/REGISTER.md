# Rig 3D · approved frames 06–07 · implementation

The founder approved frames 06–07 in the implementation instruction for `codex/rig-3d`. The complete original design register, IDs and exports are preserved on [codex/figma-rig-3d at 3e6306a4](https://github.com/Tervory-AI/tervory-tank/blob/3e6306a46c77ce608be63d7ca1f9ae86df0fba3a/docs/figma/rig-3d/REGISTER.md), PR #671. Its earlier Proposed annotations record the design's status when authored; the founder's approval supersedes them. No Figma node was changed by this implementation.

| Approved state | Desktop / mobile node IDs | Offline browser evidence |
| --- | --- | --- |
| 06 ready / approved model viewer | 514:4045 / 514:4101 | [1440](../../rig/3d-implementation/screenshots/06-ready-1440.png), [375](../../rig/3d-implementation/screenshots/06-ready-375.png) |
| 07 phone | 516:1275 / 516:1347 | [1440](../../rig/3d-implementation/screenshots/07-phone-1440.png), [375](../../rig/3d-implementation/screenshots/07-phone-375.png) |
| 07 email | 516:1419 / 516:1491 | [1440](../../rig/3d-implementation/screenshots/07-email-1440.png), [375](../../rig/3d-implementation/screenshots/07-email-375.png) |
| 07 quote failure | 516:2121 / 516:2194 | [1440](../../rig/3d-implementation/screenshots/07-error-quote-1440.png), [375](../../rig/3d-implementation/screenshots/07-error-quote-375.png) |
| 07 saved receipt | 516:1709 / 516:1770 | [1440](../../rig/3d-implementation/screenshots/07-saved-1440.png), [375](../../rig/3d-implementation/screenshots/07-saved-375.png) |

[Implementation and verification](../../rig/3d-implementation/README.md), [comparison measurements](../../rig/3d-implementation/comparison.json). Export comparisons omit the design annotation, stand-in illustration/caption and dynamic catalogue values. The original review shapes and caption never ship to the live page. Models come exclusively from the authenticated approved-assembly/asset routes behind `rig_3d`.

New words: none beyond approved register/product wording and store/API supplied content. Light Custom Nation styling, navy main buttons and Inter are retained. Header navigation delegates the existing shared menu to the embed host using `rig-menu`; no CRM navigation routes are copied into a public retailer widget. GPU generation paths/configuration remain off and unchanged.
