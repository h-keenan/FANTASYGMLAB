import { describe, expect, it } from "vitest";
import { compactValueFontSize } from "@/lib/snapshotTileSizing";

const rem = (s: string) => parseFloat(s);

describe("compactValueFontSize", () => {
  it("keeps short values at full size", () => {
    expect(compactValueFontSize("+5.7")).toBe("1.25rem");
    expect(compactValueFontSize("#12")).toBe("1.25rem");
    expect(compactValueFontSize("—")).toBe("1.25rem");
  });
  it("steps down monotonically as values get longer", () => {
    const sizes = ["1", "12.3", "-6,862", "36,414", "43,276", "-12,345", "-123,456"].map(compactValueFontSize);
    for (let i = 1; i < sizes.length; i++) expect(rem(sizes[i])).toBeLessThanOrEqual(rem(sizes[i - 1]));
  });
  it("sizes 5-7 character values below the old fixed 1.25rem", () => {
    expect(rem(compactValueFontSize("36,414"))).toBeLessThan(1.25);
    expect(rem(compactValueFontSize("-6,862"))).toBeLessThan(1.25);
    expect(rem(compactValueFontSize("-12,345"))).toBeLessThanOrEqual(0.875);
  });
});
