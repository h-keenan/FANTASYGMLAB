import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { BEGINNER_HELP } from "./experienceCopy";
import { GLOSSARY } from "./glossary";

describe("GLOSSARY", () => {
  it("defines every jargon label the audit named, one sentence each", () => {
    for (const key of ["powerRank", "rosterPower", "franchiseRank", "starterStrength", "benchStrength", "ovr"] as const) {
      const entry = GLOSSARY[key];
      expect(entry.label.length).toBeGreaterThan(0);
      expect(entry.definition.trim().endsWith(".")).toBe(true);
    }
  });

  it("reuses the beginner help text so the two can never disagree", () => {
    expect(GLOSSARY.powerRank.definition).toBe(BEGINNER_HELP.powerRank);
    expect(GLOSSARY.franchiseRank.definition).toBe(BEGINNER_HELP.franchiseRank);
    expect(GLOSSARY.starterStrength.definition).toBe(BEGINNER_HELP.starterStrength);
    expect(GLOSSARY.ovr.definition).toBe(BEGINNER_HELP.overallRating);
  });

  it("stays identical to mobile's copy apart from the import line", () => {
    const body = (source: string) => source.split("\n").slice(1).join("\n");
    const web = readFileSync(path.resolve(__dirname, "glossary.ts"), "utf8");
    const mobile = readFileSync(path.resolve(__dirname, "../../../mobile/src/lib/glossary.ts"), "utf8");
    expect(body(mobile)).toBe(body(web));
  });
});
