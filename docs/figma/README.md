# Figma exports for builders

Builders can't open the founder's Figma (Codex got 403). So each approved frame is exported here **exactly as Figma has it**. These files are the design. Nothing else is.

Each frame folder has:

| File | What it is |
|---|---|
| `frame.png` | The frame at full size, straight from Figma. The live page must look like this at the same width. |
| `reference.tsx` | Figma's own code for the frame: every text, size, colour, font, gap, padding and radius. **Not production code.** It's the measurement sheet. Rebuild it in the Workspace's own style (plain CSS files, the fonts in `workspace/app/fonts`), with the same result. |
| `assets/` | Every image in the frame (status dots, switches, sparklines), downloaded from Figma. Use these files and no others. |
| `SPEC.md` | Every text on the frame, split into **FIXED** (built exactly to the character) and **DATA** (filled from a real source, in exactly the format shown). It also lists the **founder's open questions**. A builder never answers those. |

## The rules (founder, 25 Oct 2026)
1. **Figma first.** Nothing goes onto any site without an approved Figma frame.
2. **FIXED text matches to the character:** every word, full stop, capital letter, digit and space.
3. **DATA text** takes a real value in the exact format the frame shows, for example `18 420` (a space between thousands) or `$3,691.70`.
4. **Nothing is added that isn't in the frame:** no extra text, section, button, tooltip, empty-state wording, loading wording or error wording. If you need one, stop and report it, and the founder adds it to Figma first.
5. **Deviate once and the thread is deleted** with all its work, and the job starts again in a new thread.

## Frames exported
| Frame | Figma node | Page in the Workspace | Status |
|---|---|---|---|
| Client dashboard | `12:2` (page "0 · Dashboards") | `app.tervory.com/` (`workspace/app/page.tsx`) | Exported 25 Oct. Open questions in its SPEC |
| Founder control panel | `10:115` (page "0 · Dashboards") | `app.tervory.com/control` (`workspace/app/control/`) | Exported 25 Oct. Open questions in its SPEC |

Figma file: https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS

**If the founder changes a frame in Figma, this export is out of date.** It's re-exported (by Claude) before any builder touches that page again.
