import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import {
  BEGINNER_HELP,
  BEGINNER_LABELS,
  EXPERIENCE_TIERS,
  NEW_FANTASY_HELP,
  experienceCopy,
  levelForTier,
  normalizeExperienceLevel,
  normalizeExperienceTier,
  normalizePrimaryGoal,
  stanceForGoal,
  tierForLevel,
} from "./experienceCopy";

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
    expect(extract(mobile, "NEW_FANTASY_HELP")).toBe(extract(web, "NEW_FANTASY_HELP"));
    expect(extract(mobile, "EXPERIENCE_TIERS")).toBe(extract(web, "EXPERIENCE_TIERS"));
    expect(extract(mobile, "PRIMARY_GOALS")).toBe(extract(web, "PRIMARY_GOALS"));
  });

  it("maps tiers to the legacy level and back", () => {
    expect(levelForTier("new_fantasy")).toBe("beginner");
    expect(levelForTier("new_dynasty")).toBe("beginner");
    expect(levelForTier("veteran")).toBe("advanced");
    expect(tierForLevel("beginner")).toBe("new_dynasty");
    expect(tierForLevel("advanced")).toBe("veteran");
    expect(normalizeExperienceTier("veteran")).toBe("veteran");
    expect(normalizeExperienceTier("expert")).toBeNull();
    expect(normalizePrimaryGoal("rebuild")).toBe("rebuild");
    expect(normalizePrimaryGoal("tank")).toBeNull();
  });

  it("maps a goal to a Team Situation suggestion only for win now and rebuild", () => {
    expect(stanceForGoal("win_now")).toBe("competing");
    expect(stanceForGoal("rebuild")).toBe("rebuilding");
    expect(stanceForGoal("exploring")).toBeNull();
    expect(stanceForGoal(null)).toBeNull();
  });

  it("gives both beginner tiers the beginner captions, with plainer wording for new to fantasy", () => {
    const dynasty = experienceCopy("beginner", "new_dynasty");
    const fantasy = experienceCopy("beginner", "new_fantasy");
    expect(dynasty.help("powerRank")).toBe(BEGINNER_HELP.powerRank);
    expect(fantasy.help("powerRank")).toBe(NEW_FANTASY_HELP.powerRank);
    // A key without a plainer line falls back to the beginner caption.
    expect(fantasy.help("waiverValue")).toBe(BEGINNER_HELP.waiverValue);
    expect(fantasy.isNewToFantasy).toBe(true);
    expect(dynasty.isNewToFantasy).toBe(false);
    // Labels are shared by both beginner tiers.
    expect(fantasy.label("averageAge", "Avg Age")).toBe(BEGINNER_LABELS.averageAge);
  });

  it("never shows captions to a veteran, and ignores a tier that disagrees with the level", () => {
    expect(experienceCopy("advanced", "veteran").help("powerRank")).toBeNull();
    expect(experienceCopy("advanced", "new_fantasy").help("powerRank")).toBeNull();
    expect(experienceCopy(null, "new_fantasy").help("powerRank")).toBeNull();
  });

  it("onboarding and Settings share one set of labels", () => {
    expect(EXPERIENCE_TIERS.new_fantasy.label).toBe("New to fantasy");
    expect(EXPERIENCE_TIERS.new_dynasty.label).toBe("New to dynasty");
    expect(EXPERIENCE_TIERS.veteran.label).toBe("Dynasty veteran");
  });
});
