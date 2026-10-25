import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import {
  SHELL_ROUTES,
  linkIsCurrent,
  pageSection,
  sidebarLabels,
  squadKey,
  squadMembers,
  usesOwnShell,
} from "../workspace/app/product-nav.ts";

const root = new URL("..", import.meta.url);

test("sidebar order is Dashboard, Projects, Chats, Squad, then the page section, then the rest", () => {
  const labels = sidebarLabels("/base", false, false);
  const squad = labels.indexOf("Squad");
  assert.deepEqual(labels.slice(0, 4), ["Dashboard", "Projects", "Chats", "Squad"]);
  assert.ok(labels.indexOf("Base") > squad);
  assert.ok(labels.indexOf("Overview") > labels.indexOf("Base"));
  assert.ok(labels.indexOf("Search") > labels.indexOf("Overview"));
  assert.ok(labels.indexOf("Ledger") > labels.indexOf("Search"));
  assert.ok(labels.indexOf("Billing") > labels.indexOf("Ledger"));
  assert.ok(labels.indexOf("Tasks") > labels.indexOf("Billing"));
  assert.ok(labels.indexOf("Settings") > labels.indexOf("Tasks"));
  assert.ok(labels.indexOf("Support") > labels.indexOf("Settings"));
});

test("the nine squad names are not a list in the sidebar", () => {
  const labels = sidebarLabels("/ledger", true, true);
  for (const name of ["Tiger", "Market Lab", "Rig", "Tisan", "Radix", "Zenas", "Skala", "Tank"]) {
    assert.equal(labels.includes(name), false, name);
  }
  assert.equal(labels.includes("Squad"), true);
});

test("founders see Skala and Tank in the squad pop-out, and other people do not", () => {
  const founder = squadMembers(true).map((member) => member.label);
  const customer = squadMembers(false).map((member) => member.label);
  assert.deepEqual(founder, ["Base", "Tiger", "Market Lab", "Rig", "Tisan", "Radix", "Zenas", "Skala", "Tank"]);
  assert.deepEqual(customer, ["Base", "Tiger", "Market Lab", "Rig", "Tisan", "Radix", "Zenas"]);
  assert.equal(sidebarLabels("/admin", true, false).includes("Admin"), true);
  assert.equal(sidebarLabels("/admin", false, false).includes("Admin"), false);
  assert.equal(sidebarLabels("/review", false, true).includes("Review"), true);
  assert.equal(sidebarLabels("/review", false, false).includes("Review"), false);
});

test("Escape closes and arrows move between members", () => {
  assert.equal(squadKey("Escape", 0, 7), "close");
  assert.equal(squadKey("ArrowDown", 0, 7), 1);
  assert.equal(squadKey("ArrowDown", 6, 7), 6);
  assert.equal(squadKey("ArrowUp", 0, 7), 0);
  assert.equal(squadKey("ArrowUp", -1, 7), 6);
  assert.equal(squadKey("ArrowDown", -1, 7), 0);
  assert.equal(squadKey("Home", 3, 7), 0);
  assert.equal(squadKey("End", 3, 7), 6);
  assert.equal(squadKey("Enter", 1, 7), null);
});

test("Base section links the real parts of the page", () => {
  const section = pageSection("/base");
  assert.equal(section?.title, "Base");
  assert.deepEqual(section?.links.map((link) => link.label), ["Overview", "Search", "Ask Base", "Batches", "Skills"]);
  assert.equal(linkIsCurrent("/base#overview", "/base", "", ""), true);
  assert.equal(linkIsCurrent("/base#search", "/base", "", ""), false);
  assert.equal(linkIsCurrent("/base#search", "/base", "", "#search"), true);
  assert.equal(linkIsCurrent("/billing", "/billing", "tab=usage", ""), false);
  assert.equal(linkIsCurrent("/billing?tab=usage", "/billing", "tab=usage", ""), true);
});

test("workspace routes use the shared shell; auth and squad product roots use their own", () => {
  for (const path of SHELL_ROUTES) assert.equal(usesOwnShell(path), false, path);
  assert.equal(usesOwnShell("/sign-in"), true);
  assert.equal(usesOwnShell("/sign-up/verify"), true);
  for (const path of ["/base", "/tiger", "/market-lab", "/rig", "/tisan", "/radix", "/zenas", "/skala", "/tank", "/moot"]) {
    assert.equal(usesOwnShell(path), true, path);
  }
  assert.equal(usesOwnShell("/moot/fixture-published"), true);
  assert.equal(usesOwnShell("/zenas/feeds"), false);
  assert.equal(usesOwnShell("/skala/gold"), false);
});

test("the shell wires the pop-out, Escape, and focus return", () => {
  const squad = readFileSync(new URL("workspace/app/squad-links.tsx", root), "utf8");
  const shell = readFileSync(new URL("workspace/app/shell.tsx", root), "utf8");
  assert.match(squad, /aria-expanded=\{panel\.open\}/);
  assert.match(squad, /aria-controls=\{panelId\}/);
  assert.match(squad, /createPortal\(popout, document\.body\)/);
  assert.match(squad, /event\.key !== "Escape"/);
  assert.match(squad, /buttonRef\.current\?\.focus\(\)/);
  assert.match(squad, /data-squad-member/);
  assert.match(squad, /isArrowKey\(event\.key\)/);
  assert.match(shell, /id="app-sidebar"/);
  assert.match(shell, /aria-controls="app-sidebar"/);
  assert.match(shell, />Menu</);
  assert.match(shell, />Close</);
  const aside = shell.split('id="app-sidebar"')[1]?.split("</aside>")[0] ?? "";
  assert.equal(aside.includes("squad-popout"), false);
});
