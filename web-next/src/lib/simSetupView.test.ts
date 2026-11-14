import { describe, expect, it } from "vitest";

import { simSetupBody, simSetupDefaults } from "@/lib/simGame";
import {
  SIM_DIFFICULTY_CARDS,
  SIM_SETUP_TABS,
  simSetupCardSummaries,
  simSetupChips,
  simSetupHeadline,
  simSetupLineupLabel,
} from "@/lib/simSetupView";

const base = simSetupDefaults(null);

describe("simSetupView", () => {
  it("offers Quick start then Customize", () => {
    expect(SIM_SETUP_TABS.map((t) => t.key)).toEqual(["quick", "custom"]);
  });

  it("describes the lineup from the toggles", () => {
    expect(simSetupLineupLabel({ superflex: false, includeK: false, includeDef: false })).toBe("Standard lineup");
    expect(simSetupLineupLabel({ superflex: true, includeK: true, includeDef: true })).toBe("Superflex lineup + K + DEF");
  });

  it("headline and chips follow the options (quick-start defaults, then a customised league)", () => {
    expect(simSetupHeadline(base)).toBe("12 teams, half PPR, standard lineup + K. Redraft, one season, normal AI.");
    const custom = { ...base, teams: 14, scoring: "ppr" as const, tePremium: 0.5, superflex: true, mode: "dynasty" as const, seasons: 10 };
    expect(simSetupChips(custom)).toEqual(["14 teams", "PPR, TE +0.5", "Superflex lineup + K", "Dynasty, 10 seasons"]);
    expect(simSetupHeadline(custom)).toContain("Dynasty, up to 10 seasons");
  });

  it("a league import takes size, scoring and lineup from the league", () => {
    const s = { ...base, start: "league" as const };
    expect(simSetupChips(s).slice(0, 3)).toEqual(["Your league", "Its scoring", "Its lineup"]);
    expect(simSetupCardSummaries(s).league).toBe("Set by your league");
    expect(simSetupCardSummaries(s).start).toBe("From your Sleeper league");
  });

  it("card summaries carry the team name and difficulty descriptor", () => {
    const sum = simSetupCardSummaries({ ...base, difficulty: "hard", irSlots: 2 }, "Blitz Brigade");
    expect(sum.start).toBe("Fresh league, Blitz Brigade");
    expect(sum.difficulty).toBe("Hard: cutthroat");
    expect(sum.extras).toBe("8 bench, 2 IR");
  });

  it("has a descriptor for every difficulty", () => {
    for (const level of ["easy", "normal", "hard"] as const) expect(SIM_DIFFICULTY_CARDS[level].detail.length).toBeGreaterThan(10);
  });

  it("the presentation layer never changes the create payload", () => {
    expect(simSetupBody(base)).toMatchObject({ difficulty: "normal", teams: 12, scoring: "half", mode: "redraft" });
  });
});
