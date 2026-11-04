# Per-product menus · Wave 5

**Proposed.** Figma [file](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS). Branch `codex/figma-w5`. The founder's 4 Nov instruction authorizes separate Rig, Tisan and Tiger menus; Claude may approve the basics under delegation. This register does not grant approval.

122 existing instances were repointed: 89 Rig, 28 Tisan and 5 Tiger. This covers all 52 product instances in the previous assignments plus 60 Rig 3D bars/drawers and 10 Tisan client-quote bars. Every outer instance and owning frame ID is retained. The before/after ledger records inherited descendant IDs from component swaps separately; intermediate geometry corrections are retained as authoring evidence. Final checks confirm all 122 instances retain their original width/height and use Inter. Trigger's two original mains, their item wording and Close geometry are unchanged.

| Product | Desktop main | Drawer main | Compact bar main | Source of own items |
| --- | --- | --- | --- | --- |
| Rig | 533:19231 | 533:19273 | 539:19647 | `workspace/app/rig/copy.ts`, `lab.tsx`: Search, Overview, Catalogues, Fits to review, Skins, Progress, Plugins; Settings, Support |
| Tisan | 533:19517 | 533:19559 | 539:19711 | `workspace/app/tisan/copy.ts`, `tisan.tsx`: Overview, Builds, Design, Tests, Plugins; Settings, Support |
| Tiger | 533:19787 | 533:19829 | 539:19769 | `workspace/app/tiger/model.ts`, `view.tsx`: Overview, Alerts, Watch list, History; Support |

Account destinations come from each product's existing built navigation. Rig/Tisan retain Dashboard, Projects, Chats and Squad; Tiger retains Dashboard, Tasks, Chats and Squad. No CRM Leads/Clients/Contacts/Sales/Marketing/Chat bot destinations remain in these product mains. Header/main combinations are Proposed design changes, including where source wording is reused. Product-state buttons are visual proposals; no live application navigation or runtime code was changed.

| New review frame | ID | Status | Screenshot |
| --- | --- | --- | --- |
| Six menu variants / 1440 | [534:19362](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=534-19362) | Proposed | [PNG](menu-review.png) |
| Rig mobile menu / 375 | [539:19651](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=539-19651) | Proposed | [PNG](rig-mobile-menu.png) |
| Tisan mobile menu / 375 | [539:19715](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=539-19715) | Proposed | [PNG](tisan-mobile-menu.png) |
| Tiger mobile menu / 375 | [539:19773](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=539-19773) | Proposed | [PNG](tiger-mobile-menu.png) |

Existing-frame screenshots: [Rig MCP](rig-mcp-desktop.png), [Tisan MCP](tisan-mcp-desktop.png), [Rig compact bar](rig-compact-bar.png), [Rig cart](rig-cart-menu.png), [Tiger](tiger-desktop.png), [Rig 3D](rig-3d-header.png). The 72px compact MCP headers and narrow Rig 3D menu slots retain their dimensions. Compact product bars open the corresponding Proposed drawer frame; the original Close control closes the overlay. Existing product pages with bespoke non-Trigger menus were inspected and not repointed.

[All before/after records](before-after.json) · [Current assignments](assignments.json) · [Mains and surviving IDs](mains.json) · [Review IDs](review.json) · [Mobile header/drawer IDs](mobile-headers.json) · [Source labels and menu checks](export-checks.json). Per-page `validation-*.json` files contain exact instance IDs, mains, geometry and font checks. Other `geometry-*.json` and swap receipts list every affected node, including inherited reflow. The original `../assignments.json` now points its 52 affected entries to the new product mains and retains `previousMainId`.

New product words: none. The new compositions and review annotations are **Proposed**. Light surfaces, existing variable-backed navigation rows, the official raster logo, Inter and navy text are retained; no dark page/panel or new brand asset was introduced. Rule 9 does not require inventing missing menu destinations: this task's item labels are all present in built product pages.
