import { describe, expect, it } from "vitest";

import { compactAriaLabel, compactCount, compactParts, compactSummaryText, noticeDismissMs } from "./compactModule";

describe("compactModule", () => {
  it("drops empty parts and caps the line", () => {
    const parts = compactParts([{ key: "a", text: "R1 P2" }, null, false, "", { key: "b", text: "  " }, { key: "c", text: "need RB/WR" }]);
    expect(parts.map((p) => p.key)).toEqual(["a", "c"]);
    expect(compactParts(Array.from({ length: 9 }, (_, i) => ({ key: `k${i}`, text: `t${i}` }))).length).toBe(6);
  });
  it("reads as a dense summary and names the control", () => {
    const parts = compactParts([{ key: "a", text: "R1 P2" }, { key: "b", text: "You pick now" }, { key: "c", text: "need RB/WR" }]);
    expect(compactSummaryText(parts)).toBe("R1 P2 · You pick now · need RB/WR");
    expect(compactAriaLabel("Draft clock", parts, false)).toBe("Draft clock: R1 P2 · You pick now · need RB/WR. Expand");
    expect(compactAriaLabel("Draft clock", [], true)).toBe("Draft clock. Collapse");
  });
  it("counts in words", () => {
    expect(compactCount(0, "offer")).toBe("No offers");
    expect(compactCount(1, "offer")).toBe("1 offer");
    expect(compactCount(3, "move")).toBe("3 moves");
  });
  it("auto-dismiss rule: confirmations go in seconds, warnings later, errors never", () => {
    expect(noticeDismissMs("success")).toBe(4000);
    expect(noticeDismissMs("warning")).toBeGreaterThan(4000);
    expect(noticeDismissMs("danger")).toBeNull();
  });
});
