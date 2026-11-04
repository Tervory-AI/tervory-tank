# F1 window agent frames — Proposed

Figma file: [Tervory design file](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS). Separate page: [F1 · Window agent tools · Proposed](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-1460).

Branch: `codex/figma-window-agent`. All frames and new wording are **Proposed**. These are editable designs for the window build, not shipped UI.

Scope split confirmed by the founder on 4 November 2026: this branch owns multi-file/per-hunk review, receipts and savings, autocomplete, inline edit, codebase search, background agents and PR review comments. The `codex/figma-w5` chat owns sign-in, empty, conversation, command, undo, plugins/MCP, error and offline.

Reuse: Code-OSS shell components `548:43` / `548:76`, panel header `553:1313`, composer `553:1325` where a chat composer is relevant, and `CRM / Action` `93:4`. Shared mains are unchanged. The shell is the other chat’s Code-OSS 1.145.0 proposal, with its exact repository-logo image slots and imported Codicons. Light theme, Inter throughout, 448px right dock, navy actions. Existing navy/surface/border variables remain bound. Only the two discrete logo slots are raster; no complete-UI screenshot is imported.

The review uses illustrative `file.txt` / `notes.txt` changes with an independent Accept/Reject pair at file and hunk level. Receipt numbers are explicitly proposed examples: a $0.00 code/cache turn against a $0.04 comparison estimate; savings are an estimate, never a production billing claim. Search paths, agent jobs, PR #42, comments and replies are fixture content, not live results or submitted comments. Autocomplete shows ghost text at the cursor; inline selection, instruction and in-place diff are separate frames.

## Step 1 — Multi-file review and receipts

| State | Size | Frame ID | Status | Screenshot |
| --- | --- | --- | --- | --- |
| Multi-file and hunk review | 1440×900 | [557:4283](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-4283) | Proposed | [F1-W03-1440.png](agent-evidence/F1-W03-1440.png) |
| Multi-file and hunk review | 1280×800 | [557:4392](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-4392) | Proposed | [F1-W03-1280.png](agent-evidence/F1-W03-1280.png) |
| Receipt and savings | 1440×900 | [557:4501](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-4501) | Proposed | [F1-W09-1440.png](agent-evidence/F1-W09-1440.png) |
| Receipt and savings | 1280×800 | [557:4592](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-4592) | Proposed | [F1-W09-1280.png](agent-evidence/F1-W09-1280.png) |

Evidence: [review-receipt-audit.json](agent-evidence/review-receipt-audit.json). Read-back asserts Inter, exact size, content fit, semantic layer counts, component mains and discrete image slots. Screenshots are full-window exports reviewed for clipping and overlap.

## Step 2 — Editor tools, background agents and PR review

| State | Size | Frame ID | Status | Screenshot |
| --- | --- | --- | --- | --- |
| Tab autocomplete | 1440×900 | [557:1461](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-1461) | Proposed | [F1-W12-1440.png](agent-evidence/F1-W12-1440.png) |
| Tab autocomplete | 1280×800 | [557:1555](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-1555) | Proposed | [F1-W12-1280.png](agent-evidence/F1-W12-1280.png) |
| Inline selection | 1440×900 | [557:1649](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-1649) | Proposed | [F1-W13-1440.png](agent-evidence/F1-W13-1440.png) |
| Inline selection | 1280×800 | [557:1746](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-1746) | Proposed | [F1-W13-1280.png](agent-evidence/F1-W13-1280.png) |
| Inline instruction | 1440×900 | [557:1843](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-1843) | Proposed | [F1-W14-1440.png](agent-evidence/F1-W14-1440.png) |
| Inline instruction | 1280×800 | [557:1940](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-1940) | Proposed | [F1-W14-1280.png](agent-evidence/F1-W14-1280.png) |
| Inline diff | 1440×900 | [557:2037](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-2037) | Proposed | [F1-W15-1440.png](agent-evidence/F1-W15-1440.png) |
| Inline diff | 1280×800 | [557:2141](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-2141) | Proposed | [F1-W15-1280.png](agent-evidence/F1-W15-1280.png) |
| Codebase search | 1440×900 | [557:2245](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-2245) | Proposed | [F1-W16-1440.png](agent-evidence/F1-W16-1440.png) |
| Codebase search | 1280×800 | [557:2334](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-2334) | Proposed | [F1-W16-1280.png](agent-evidence/F1-W16-1280.png) |
| Background agents | 1440×900 | [557:2423](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-2423) | Proposed | [F1-W17-1440.png](agent-evidence/F1-W17-1440.png) |
| Background agents | 1280×800 | [557:2513](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-2513) | Proposed | [F1-W17-1280.png](agent-evidence/F1-W17-1280.png) |
| PR review comments | 1440×900 | [557:2603](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-2603) | Proposed | [F1-W18-1440.png](agent-evidence/F1-W18-1440.png) |
| PR review comments | 1280×800 | [557:2692](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-2692) | Proposed | [F1-W18-1280.png](agent-evidence/F1-W18-1280.png) |

Evidence: [editor-agent-audit.json](agent-evidence/editor-agent-audit.json) and [screenshot-validation.json](agent-evidence/screenshot-validation.json). All 18 full-window PNGs use the requested dimensions; all 18 frames use Inter, have no outer-bounds or content-fit errors, retain editable text/vector/instance layers, and use only the discrete logo images. The editor-demo frame is an editable overlay over the shared shell’s source area; the shared shell main is unchanged.
