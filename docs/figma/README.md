# Figma exports for builders

Builders can't open the founder's Figma (Codex got 403). So each approved frame is exported here **exactly as Figma has it**. These files are the design. Nothing else is.

Each frame folder has:

| File | What it is |
|---|---|
| `frame.png` | The frame at full size, straight from Figma. The live page must look like this at the same width. |
| `reference.tsx` | Figma's own code for the frame: every text, size, colour, font, gap, padding and radius. **Not production code.** It's the measurement sheet. Rebuild it in the Workspace's own style (plain CSS files, the fonts in `workspace/app/fonts`), with the same result. |
| `assets/` | Every image in the frame (status dots, switches, sparklines), downloaded from Figma. Use these files and no others. |
| `states.png`, `states.tsx` | The frame's other approved states (greetings, empty states, problem pill). They are the only other texts the page may show. |
| `SPEC.md` | Every text on the frame, split into **FIXED** (built exactly to the character) and **DATA** (filled from a real source, in exactly the format shown). If a source is missing, the builder stops and reports it. A builder never fills the gap. |

## The rules (founder, 25 Oct 2026)
1. **Figma first.** Nothing goes onto any site without an approved Figma frame.
2. **FIXED text matches to the character:** every word, full stop, capital letter, digit and space.
3. **DATA text** takes a real value in the exact format the frame shows, for example `18 420` (a space between thousands) or `$3,691.70`.
4. **Nothing is added that isn't in the frame:** no extra text, section, button, tooltip, empty-state wording, loading wording or error wording. If you need one, stop and report it, and the founder adds it to Figma first.
5. **Deviate once and the thread is deleted** with all its work, and the job starts again in a new thread.

## Frames exported
| Frame | Figma node | Page in the Workspace | Status |
|---|---|---|---|
| Client dashboard | `12:2` + states `20:2` (page "0 · Dashboards") | `app.tervory.com/` (`workspace/app/page.tsx`) | Re-exported 25 Oct 17:10 PT (only what is real). Links to a client savings page wait for that page |
| Founder control panel | `10:115` + states `20:44` (page "0 · Dashboards") | `app.tervory.com/control` (`workspace/app/control/`) | Re-exported 25 Oct 17:10 PT; Approve all states added 26 Oct 01:25 PT |
| Base page (C5) | `7:221` + states `26:31` (page "2 · Client screens") | `app.tervory.com/base` | Exported 26 Oct 01:40 PT (only what is real) |

Figma file: https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS

**If the founder changes a frame in Figma, this export is out of date.** It's re-exported (by Claude) before any builder touches that page again.
