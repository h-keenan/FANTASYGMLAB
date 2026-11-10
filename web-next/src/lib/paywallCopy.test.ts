import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { annualSavingsPercent, parsePrice, proHighlights } from "./paywallCopy";
import { FALLBACK_PREMIUM_COMPARISON } from "./premiumComparison";

describe("paywallCopy", () => {
  it("parses store and Stripe price strings", () => {
    expect(parsePrice("$59.99")).toBe(59.99);
    expect(parsePrice("USD 9.99")).toBe(9.99);
    expect(parsePrice("1,299.00")).toBe(1299);
    expect(parsePrice("free")).toBeNull();
    expect(parsePrice(null)).toBeNull();
  });

  it("computes the annual saving from the two real prices, never inventing one", () => {
    expect(annualSavingsPercent("$9.99", "$59.99")).toBe(50);
    expect(annualSavingsPercent("$3.99", "$19.99")).toBe(58);
    expect(annualSavingsPercent("$9.99", "$129.99")).toBeNull(); // yearly costs more: no claim
    expect(annualSavingsPercent(undefined, "$59.99")).toBeNull();
  });

  it("builds highlight bodies from the server's enforced Free limits", () => {
    const rows = FALLBACK_PREMIUM_COMPARISON.map((r) =>
      r.key === "next_moves" ? { ...r, free: "Top 6" } : r,
    );
    const items = proHighlights(rows);
    expect(items).toHaveLength(3);
    expect(items[0].body).toContain("top 6");
    expect(items[1].body).toContain("first 2");
  });

  it("uses only canonical glossary names (no Next Moves / Game Plan / Premium)", () => {
    const text = JSON.stringify(proHighlights(FALLBACK_PREMIUM_COMPARISON));
    expect(text).not.toMatch(/Next Move|Game Plan|Premium/);
    expect(text).toContain("Today");
  });

  it("stays byte-identical to the mobile twin", () => {
    const mobile = readFileSync(path.join(__dirname, "../../../mobile/src/lib/paywallCopy.ts"), "utf8");
    expect(mobile).toBe(readFileSync(path.join(__dirname, "paywallCopy.ts"), "utf8"));
  });
});
