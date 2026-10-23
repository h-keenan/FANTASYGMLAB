import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { BEGINNER_HELP, BEGINNER_LABELS, experienceCopy, normalizeExperienceLevel } from "./experienceCopy";

describe("experienceCopy", () => {
  it("gives a beginner every helper line and the spelled-out labels", () => {
    const copy = experienceCopy("beginner");
    expect(copy.isBeginner).toBe(true);
    for (const key of Object.keys(BEGINNER_HELP) as Array<keyof typeof BEGINNER_HELP>) {
      expect(copy.help(key)).toBe(BEGINNER_HELP[key]);
    }
    expect(copy.label("averageAge", "Avg Age")).toBe("Average Age");
    expect(copy.label("yourFaab", "Your FAAB")).toBe("Your Waiver Budget (FAAB)");
  });

  it.each([
    ["advanced", "advanced" as const],
    ["unset (null)", null],
  ])("keeps today's terse copy for %s", (_name, level) => {
    const copy = experienceCopy(level);
    expect(copy.isBeginner).toBe(false);
    for (const key of Object.keys(BEGINNER_HELP) as Array<keyof typeof BEGINNER_HELP>) {
      expect(copy.help(key)).toBeNull();
    }
    for (const key of Object.keys(BEGINNER_LABELS) as Array<keyof typeof BEGINNER_LABELS>) {
      expect(copy.label(key, "current label")).toBe("current label");
    }
    expect(copy.verdictHelp("ACCEPT")).toBeNull();
    expect(copy.impactTagHelp("sell_high")).toBeNull();
  });

  it("maps Trade Analyzer ui_verdict values and Trade Hub impact tags for a beginner", () => {
    const copy = experienceCopy("beginner");
    expect(copy.verdictHelp("ACCEPT")).toBe(BEGINNER_HELP.verdictAccept);
    expect(copy.verdictHelp("counter")).toBe(BEGINNER_HELP.verdictCounter);
    expect(copy.verdictHelp("DECLINE")).toBe(BEGINNER_HELP.verdictDecline);
    expect(copy.verdictHelp("FAIR")).toBe(BEGINNER_HELP.verdictFair);
    expect(copy.verdictHelp("SOMETHING ELSE")).toBeNull();
    expect(copy.verdictHelp(undefined)).toBeNull();
    expect(copy.impactTagHelp("sell_high")).toBe(BEGINNER_HELP.impactSellHigh);
    expect(copy.impactTagHelp("buy_low")).toBe(BEGINNER_HELP.impactBuyLow);
    expect(copy.impactTagHelp("high_impact")).toBe(BEGINNER_HELP.impactHighImpact);
    expect(copy.impactTagHelp("")).toBeNull();
  });

  it("normalizes anything other than beginner/advanced to null", () => {
    expect(normalizeExperienceLevel("beginner")).toBe("beginner");
    expect(normalizeExperienceLevel("advanced")).toBe("advanced");
    expect(normalizeExperienceLevel("expert")).toBeNull();
    expect(normalizeExperienceLevel(undefined)).toBeNull();
    expect(normalizeExperienceLevel(null)).toBeNull();
  });

  it("stays byte-identical to mobile's copy map", () => {
    const extract = (source: string, name: string) => {
      const start = source.indexOf(`export const ${name} = {`);
      const end = source.indexOf("} as const;", start);
      expect(start).toBeGreaterThanOrEqual(0);
      expect(end).toBeGreaterThan(start);
      return source.slice(start, end);
    };
    const web = readFileSync(path.resolve(__dirname, "experienceCopy.ts"), "utf8");
    const mobile = readFileSync(path.resolve(__dirname, "../../../mobile/src/lib/experienceCopy.ts"), "utf8");
    expect(extract(mobile, "BEGINNER_HELP")).toBe(extract(web, "BEGINNER_HELP"));
    expect(extract(mobile, "BEGINNER_LABELS")).toBe(extract(web, "BEGINNER_LABELS"));
    expect(extract(mobile, "PLAIN_COPY")).toBe(extract(web, "PLAIN_COPY"));
  });
});
