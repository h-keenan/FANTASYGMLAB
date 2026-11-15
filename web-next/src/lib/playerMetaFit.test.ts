import { describe, expect, it } from "vitest";

import { estimateMetaWidth, fitMetaParts, metaPartsFromStrings, type MetaPart } from "./playerMetaFit";

const parts: MetaPart[] = [
  { key: "team", text: "BAL" },
  { key: "age", text: "Age 26" },
  { key: "bye", text: "Bye 13" },
  { key: "proj", text: "PROJ 17.8" },
];
const keys = (p: MetaPart[]) => p.map((x) => x.key);

describe("fitMetaParts", () => {
  it("keeps everything when it fits or the width is unknown", () => {
    expect(keys(fitMetaParts(parts, 400))).toEqual(["team", "age", "bye", "proj"]);
    expect(keys(fitMetaParts(parts, null))).toEqual(["team", "age", "bye", "proj"]);
  });
  it("drops age first, then team, then bye; never PROJ", () => {
    const full = estimateMetaWidth(parts, 12);
    expect(keys(fitMetaParts(parts, full - 1))).toEqual(["team", "bye", "proj"]);
    expect(keys(fitMetaParts(parts, estimateMetaWidth(parts.filter((p) => p.key !== "age"), 12) - 1))).toEqual(["bye", "proj"]);
    expect(keys(fitMetaParts(parts, 10))).toEqual(["proj"]);
  });
  it("never drops a bye that is soon (warning tone)", () => {
    const soon = parts.map((p) => (p.key === "bye" ? { ...p, tone: "warning" } : p));
    expect(keys(fitMetaParts(soon, 10))).toEqual(["bye", "proj"]);
  });
  it("labels the plain strings", () => {
    expect(keys(metaPartsFromStrings(["BAL", "Age 26", "BYE 13"]))).toEqual(["team", "age", "bye"]);
  });
});
