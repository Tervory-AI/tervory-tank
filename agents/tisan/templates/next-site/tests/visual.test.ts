import { describe, it, expect } from "vitest";
import { validateFrames, type Frame } from "../visual/check";

const frame: Frame = {
  page: "/",
  frameId: "synthetic",
  width: 375,
  height: 900,
  tokens: { "--ink": "#001840" },
  elements: [
    {
      nodeId: "heading",
      selector: "h1",
      text: "Example",
      box: { x: 16, y: 32, width: 200, height: 40 },
      colours: { color: "--ink" },
    },
  ],
};
const pair = () => [structuredClone(frame), { ...structuredClone(frame), width: 1440 }];

describe("recorded frame completeness", () => {
  it("requires both exact viewport sizes for every page", () => {
    expect(validateFrames(pair())).toHaveLength(2);
    expect(() => validateFrames([frame])).toThrow("frame data incomplete");
    expect(() => validateFrames([frame, { ...frame, width: 390 }])).toThrow(
      "frame data incomplete",
    );
  });
  it.each([null, [], [{}], [null], [{ ...frame, incomplete: true }]])(
    "refuses incomplete data",
    (value) => {
      expect(() => validateFrames(value)).toThrow("frame data incomplete");
    },
  );
  it("refuses unresolved tokens, missing text and duplicate mappings", () => {
    const data = pair();
    data[0].tokens = {};
    expect(() => validateFrames(data)).toThrow("frame data incomplete");
    const missingText = pair();
    delete missingText[0].elements[0].text;
    expect(() => validateFrames(missingText)).toThrow("frame data incomplete");
    const duplicate = pair();
    duplicate[0].elements.push(duplicate[0].elements[0]);
    expect(() => validateFrames(duplicate)).toThrow("frame data incomplete");
  });
});
