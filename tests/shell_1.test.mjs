import assert from "node:assert/strict";
import { readFileSync, writeFileSync } from "node:fs";
import { stripTypeScriptTypes } from "node:module";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { pathToFileURL } from "node:url";

const source = readFileSync(new URL("../workspace/app/squad-links.tsx", import.meta.url), "utf8");
const css = readFileSync(new URL("../workspace/app/globals.css", import.meta.url), "utf8");
const shell = readFileSync(new URL("../workspace/app/shell.tsx", import.meta.url), "utf8");
const logicSource = source.split("// shell-1 logic\n")[1].split("// shell-1 view")[0];
const logicFile = join(tmpdir(), "shell-1-logic.mjs");
writeFileSync(logicFile, stripTypeScriptTypes(logicSource, { mode: "strip" }));
const logic = await import(pathToFileURL(logicFile).href);

const names = ["Base", "Tiger", "Market Lab", "Rig", "Tisan", "Radix", "Zenas", "Skala", "Tank"];

function panel(founder, pathname) {
  return {
    members: logic.visibleMembers(founder),
    act(state, action) {
      return logic.applySquadAction(state, action, this.members, pathname);
    },
  };
}

test("the panel opens and closes", () => {
  const view = panel(false, "/base");
  let state = { open: false, focus: "squad", sidebarHeight: 480 };
  state = view.act(state, { type: "toggle" });
  assert.equal(state.open, true);
  assert.equal(state.focus, "/base");
  state = view.act(state, { type: "choose" });
  assert.equal(state.open, false);
  assert.equal(state.focus, "squad");
  state = view.act(state, { type: "toggle" });
  state = view.act(state, { type: "outside" });
  assert.equal(state.open, false);
  assert.equal(state.focus, "squad");
  state = view.act(state, { type: "toggle" });
  state = view.act(state, { type: "close" });
  assert.equal(state.open, false);
  assert.equal(state.focus, "squad");
  state = view.act(state, { type: "outside" });
  assert.equal(state.open, false);
});

test("the sidebar height does not change", () => {
  const view = panel(true, "/rig");
  let state = { open: false, focus: "squad", sidebarHeight: 640 };
  const before = state.sidebarHeight;
  state = view.act(state, { type: "toggle" });
  assert.equal(state.open, true);
  assert.equal(state.sidebarHeight, before);
  state = view.act(state, { type: "arrow", key: "ArrowDown" });
  state = view.act(state, { type: "escape" });
  assert.equal(state.open, false);
  assert.equal(state.sidebarHeight, before);
  const viewSource = source.split("// shell-1 view")[1];
  const nav = viewSource.split("<nav")[1].split("</nav>")[0];
  assert.match(nav, />\s*Squad\s*</);
  for (const name of names) assert.equal(nav.includes(`>${name}<`), false, name);
  assert.match(viewSource, /createPortal\(popout, document\.body\)/);
  const pop = css.split(".squad-pop {")[1].split("}")[0];
  assert.match(pop, /position:\s*fixed/);
  assert.match(pop, /z-index:\s*80/);
});

test("Escape closes and arrow keys move between members", () => {
  const view = panel(true, "/tiger");
  let state = { open: false, focus: "squad", sidebarHeight: 320 };
  state = view.act(state, { type: "arrow", key: "ArrowDown" });
  assert.equal(state.open, false);
  assert.equal(state.focus, "squad");
  state = view.act(state, { type: "toggle" });
  assert.equal(state.focus, "/tiger");
  state = view.act(state, { type: "arrow", key: "ArrowDown" });
  assert.equal(state.focus, "/market-lab");
  state = view.act(state, { type: "arrow", key: "ArrowUp" });
  assert.equal(state.focus, "/tiger");
  state = view.act(state, { type: "arrow", key: "ArrowLeft" });
  assert.equal(state.focus, "/base");
  state = view.act(state, { type: "arrow", key: "Home" });
  assert.equal(state.focus, "/base");
  state = view.act(state, { type: "arrow", key: "End" });
  assert.equal(state.focus, "/tank");
  state = view.act(state, { type: "arrow", key: "ArrowRight" });
  assert.equal(state.focus, "/tank");
  state = view.act(state, { type: "escape" });
  assert.equal(state.open, false);
  assert.equal(state.focus, "squad");
  assert.equal(state.sidebarHeight, 320);
  const customer = panel(false, "/zenas");
  let last = { open: true, focus: "/zenas", sidebarHeight: 320 };
  last = customer.act(last, { type: "arrow", key: "ArrowDown" });
  assert.equal(last.focus, "/zenas");
  const viewSource = source.split("// shell-1 view")[1];
  assert.match(viewSource, /aria-expanded=\{panel\.open\}/);
  assert.match(viewSource, /aria-controls=\{panelId\}/);
  assert.match(viewSource, /type="button"/);
  assert.match(viewSource, /event\.key !== "Escape"/);
  assert.match(viewSource, /isArrowKey\(event\.key\)/);
  assert.match(viewSource, /buttonRef\.current\?\.focus\(\)/);
});

test("founders see Skala and Tank, others do not", () => {
  const customer = logic.visibleMembers(false).map((member) => member.label);
  const founder = logic.visibleMembers(true).map((member) => member.label);
  assert.deepEqual(customer, names.filter((name) => name !== "Skala" && name !== "Tank"));
  assert.equal(customer.includes("Skala"), false);
  assert.equal(customer.includes("Tank"), false);
  assert.deepEqual(founder, names);
  assert.match(source.split("// shell-1 view")[1], /visibleMembers\(founder\)/);
  assert.match(shell, /SquadFounderProvider founder=\{founder\}/);
  for (const member of logic.SQUAD_MEMBERS) {
    assert.equal(member.job.includes("\n"), false);
    assert.equal(member.logo, `/brand/${member.href.slice(1)}-on-dark.png`);
    const bytes = readFileSync(new URL(`../workspace/public${member.logo}`, import.meta.url));
    assert.equal(bytes.subarray(0, 8).toString("binary"), "\x89PNG\r\n\x1a\n");
    assert.ok(member.width > 0 && member.height > 0);
  }
  assert.equal(logic.isCurrent("/base/records", "/base"), true);
  assert.equal(logic.isCurrent("/baseline", "/base"), false);
  assert.equal(logic.memberToFocus("/market-lab", logic.visibleMembers(false)), "/market-lab");
  assert.match(css, /@media \(max-width: 800px\)/);
  assert.match(css, /\.squad-pop-close/);
  assert.match(css, /100dvh/);
});
