import { describe, expect, it } from "vitest";

import { anchorShift, visibleBottom } from "./fixedAnchor";

describe("fixed bottom anchor", () => {
  it("visible bottom is the largest non-keyboard reading", () => {
    expect(visibleBottom(800, 800, { height: 500, offsetTop: 0 })).toBe(800);
    expect(visibleBottom(540, 540, { height: 800, offsetTop: 0 })).toBe(800);
  });
  it("leaves a healthy dock alone and shifts a stale one by the gap", () => {
    expect(anchorShift(800, 800, 0)).toBe(0);
    expect(anchorShift(799.4, 800, 0)).toBe(0);
    expect(anchorShift(540, 800, 0)).toBe(260);
    expect(anchorShift(800, 800, 260)).toBe(260); // already corrected: stays
    expect(anchorShift(900, 800, 260)).toBe(160);
  });
  it("gives up (0) on an absurd reading", () => {
    expect(anchorShift(0, 9000, 0)).toBe(0);
  });
});
