import type { Page } from "@playwright/test";

export type Frame = {
  incomplete?: boolean;
  page: string;
  frameId: string;
  width: 375 | 1440;
  height: number;
  tokens: Record<string, string>;
  elements: {
    nodeId: string;
    selector: string;
    box: { x: number; y: number; width: number; height: number };
    text?: string;
    colours: Partial<Record<"color" | "backgroundColor" | "borderTopColor", string>>;
  }[];
};

function validateFrameData(raw: unknown, requirePair: boolean): Frame[] {
  if (!Array.isArray(raw) || raw.length === 0) throw new Error("frame data incomplete");
  const keys = new Set<string>();
  const widths = new Map<string, Set<number>>();
  for (const frame of raw as Frame[]) {
    if (
      !frame ||
      frame.incomplete ||
      typeof frame.page !== "string" ||
      !/^\/(?:[a-z0-9/-]*)$/.test(frame.page) ||
      !frame.frameId ||
      ![375, 1440].includes(frame.width) ||
      !Number.isFinite(frame.height) ||
      frame.height <= 0 ||
      frame.height > 20000 ||
      !frame.tokens ||
      typeof frame.tokens !== "object" ||
      !Array.isArray(frame.elements) ||
      !frame.elements.length
    )
      throw new Error("frame data incomplete");
    if (
      !frame.elements.some((element) => element.text !== undefined) ||
      !Object.keys(frame.tokens).length
    )
      throw new Error("frame data incomplete");
    const key = `${frame.page}:${frame.width}`;
    if (keys.has(key)) throw new Error("frame data incomplete");
    keys.add(key);
    widths.set(frame.page, (widths.get(frame.page) ?? new Set()).add(frame.width));
    for (const [token, value] of Object.entries(frame.tokens)) {
      if (!/^--[a-z0-9-]+$/.test(token) || !/^#[a-f0-9]{6}$/i.test(value))
        throw new Error("frame data incomplete");
    }
    const selectors = new Set<string>();
    const nodes = new Set<string>();
    for (const element of frame.elements) {
      if (
        !element.nodeId ||
        nodes.has(element.nodeId) ||
        !element.selector ||
        selectors.has(element.selector) ||
        !element.box ||
        ![element.box.x, element.box.y, element.box.width, element.box.height].every(
          Number.isFinite,
        ) ||
        element.box.width <= 0 ||
        element.box.height <= 0 ||
        (element.text !== undefined && typeof element.text !== "string") ||
        !element.colours
      )
        throw new Error("frame data incomplete");
      selectors.add(element.selector);
      nodes.add(element.nodeId);
      for (const [property, token] of Object.entries(element.colours)) {
        if (
          !["color", "backgroundColor", "borderTopColor"].includes(property) ||
          !frame.tokens[token]
        )
          throw new Error("frame data incomplete");
      }
    }
  }
  for (const set of widths.values()) {
    if (requirePair && set.size !== 2) throw new Error("frame data incomplete");
  }
  return raw as Frame[];
}

export function validateFrames(raw: unknown): Frame[] {
  try {
    return validateFrameData(raw, true);
  } catch {
    throw new Error("frame data incomplete");
  }
}

const rgb = (hex: string) =>
  `rgb(${[1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)).join(", ")})`;

export async function scoreFrame(page: Page, frame: Frame) {
  try {
    validateFrameData([frame], false);
  } catch {
    throw new Error("frame data incomplete");
  }
  const checks: { nodeId: string; kind: "layout" | "text" | "colour"; passed: boolean }[] = [];
  for (const element of frame.elements) {
    const locator = page.locator(element.selector);
    const unique = (await locator.count()) === 1;
    const visible = unique && (await locator.isVisible());
    const measured = visible
      ? await locator.evaluate((node) => {
          if (!node.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })) return null;
          const box = node.getBoundingClientRect();
          const style = getComputedStyle(node);
          return {
            box: { x: box.x + scrollX, y: box.y + scrollY, width: box.width, height: box.height },
            text: (node as HTMLElement).innerText ?? node.textContent ?? "",
            colors: {
              color: style.color,
              backgroundColor: style.backgroundColor,
              borderTopColor: style.borderTopColor,
            },
          };
        })
      : null;
    checks.push({
      nodeId: element.nodeId,
      kind: "layout",
      passed:
        measured !== null &&
        (Object.keys(element.box) as (keyof typeof element.box)[]).every(
          (key) => Math.abs(measured.box[key] - element.box[key]) <= 2,
        ),
    });
    if (element.text !== undefined)
      checks.push({
        nodeId: element.nodeId,
        kind: "text",
        passed:
          measured?.text.replace(/\s+/g, " ").trim() === element.text.replace(/\s+/g, " ").trim(),
      });
    for (const [property, token] of Object.entries(element.colours)) {
      const declared = visible
        ? await locator.evaluate(
            (node, name) => getComputedStyle(node).getPropertyValue(name).trim(),
            token,
          )
        : "";
      // Check both the token and the actual painted property. A matching variable alone is insufficient.
      const tokenColor =
        declared.startsWith("#") && /^#[a-f0-9]{6}$/i.test(declared) ? rgb(declared) : declared;
      checks.push({
        nodeId: element.nodeId,
        kind: "colour",
        passed:
          measured?.colors[property as keyof typeof measured.colors] === rgb(frame.tokens[token]) &&
          tokenColor === rgb(frame.tokens[token]),
      });
    }
  }
  const scores = Object.fromEntries(
    ["layout", "text", "colour"].map((kind) => {
      const group = checks.filter((check) => check.kind === kind);
      return [
        kind,
        group.length ? group.filter((check) => check.passed).length / group.length : null,
      ];
    }),
  );
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
  return {
    page: frame.page,
    frameId: frame.frameId,
    width: frame.width,
    score: checks.filter((check) => check.passed).length / checks.length,
    scores,
    passed: !overflow && checks.every((check) => check.passed),
    overflow,
    checks,
  };
}
