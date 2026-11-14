import { describe, expect, it } from "vitest";

import { waiversHeaderParts } from "./waiversHeader";

describe("waiversHeaderParts", () => {
  it("summarizes available, FAAB and team need in one line", () => {
    const parts = waiversHeaderParts({ available: 394, faabLabel: "FAAB", faab: "$81", need: "QB" });
    expect(parts.map((p) => p.text)).toEqual(["394 available", "$81 FAAB", "Need QB"]);
  });
  it("drops what is unknown and says covered plainly", () => {
    expect(waiversHeaderParts({ available: null, faabLabel: "FAAB", faab: "—", need: "—" })).toEqual([]);
    expect(waiversHeaderParts({ available: 3, faabLabel: "Waivers", faab: "Rolling", need: "Covered" }).map((p) => p.text)).toEqual(["3 available", "Rolling Waivers", "Needs covered"]);
  });
});
