import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import { fairnessBandColor } from "./tradeHubPresentation";
import { valueDirectionLabel as presentationLabel } from "./tradeAnalyzerPresentation";
import { badgeTone, bandForScore, TRADE_VALUE_BANDS, TRADE_VALUE_GOLDEN } from "./tradeValueBands.generated";

describe("shared trade value bands (generated from modules/trade_value_bands.py)", () => {
  it("replays the Python golden scores through the TS ladder", () => {
    for (const { score, id } of TRADE_VALUE_GOLDEN) expect(bandForScore(score).id, String(score)).toBe(id);
  });

  it("the analyzer fallback sentence is the shared ladder, never its own", () => {
    for (const { score } of TRADE_VALUE_GOLDEN) expect(presentationLabel(score)).toBe(bandForScore(score).direction_label);
  });

  it("badge colors come from the band's tone on every surface", () => {
    expect(fairnessBandColor("Favorable")).toBe("var(--color-success)");
    expect(fairnessBandColor("Fair")).toBe("var(--color-text-secondary)");
    expect(fairnessBandColor("Slight Overpay")).toBe("var(--color-warning)");
    expect(fairnessBandColor("Major Overpay")).toBe("var(--color-danger)");
    expect(fairnessBandColor("nonsense")).toBe("var(--color-text-secondary)");
    for (const band of TRADE_VALUE_BANDS) expect(badgeTone(band.badge)).toBe(band.color_token);
  });

  it("stays byte-identical to mobile's copy", () => {
    const web = readFileSync(path.resolve(__dirname, "tradeValueBands.generated.ts"), "utf8");
    const mobile = readFileSync(path.resolve(__dirname, "../../../mobile/src/lib/tradeValueBands.generated.ts"), "utf8");
    expect(mobile).toBe(web);
  });
});
