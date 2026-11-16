import { describe, expect, it } from "vitest";

import { compactSummaryText } from "./compactModule";
import { injuryCoverageNote, injuryHistoryRows, injurySummaryParts, type InjuryRecordData } from "./playerDepthInjury";
import { pqvRealWorld } from "./pqvContext";
import { simOutLine, simPlayerStatusLabel, type SimStoryEntry } from "./simGame";
import { simStoryGroups, simStorySummaryParts, simStoryToneKey, simStoryWhen } from "./simStory";

const line = (e: Partial<SimStoryEntry> & Pick<SimStoryEntry, "kind" | "season" | "week" | "text">): SimStoryEntry => ({ year: 2026 + e.season - 1, season_label: `S${e.season} ${2026 + e.season - 1}`, tone: "neutral", ...e });

const story: SimStoryEntry[] = [
  line({ kind: "depth", season: 2, week: 0, text: "Lost the BAL QB1 starting job to R. Cole (rookie won the job)", tone: "bad" }),
  line({ kind: "season", season: 1, week: 99, text: "QB2 · 288.2 pts · 17 games", tone: "neutral" }),
  line({ kind: "injury", season: 1, week: 3, text: "Hamstring in Week 3: out 4 weeks", tone: "bad", injury: "Hamstring", weeks: 4 }),
  line({ kind: "season", season: 2, week: 99, text: "QB3 · did not play: behind R. Cole, J. Smith", tone: "bad" }),
];

describe("sim story presentation", () => {
  it("groups by season, newest first, the season line leading", () => {
    const groups = simStoryGroups(story);
    expect(groups.map((g) => g.label)).toEqual(["S2 2027", "S1 2026"]);
    expect(groups[0].entries.map((e) => e.kind)).toEqual(["season", "depth"]);
    expect(groups[1].entries.map((e) => e.kind)).toEqual(["season", "injury"]);
    expect(simStoryGroups(null)).toEqual([]);
  });
  it("tags a line with its week and tone", () => {
    expect(simStoryWhen({ kind: "injury", week: 3 })).toBe("Wk 3");
    expect(simStoryWhen({ kind: "depth", week: 0 })).toBe("Offseason");
    expect(simStoryWhen({ kind: "season", week: 99 })).toBe("Season");
    expect([simStoryToneKey("good"), simStoryToneKey("bad"), simStoryToneKey("neutral")]).toEqual(["success", "danger", "muted"]);
  });
  it("the collapsed summary leads with his latest season and counts what moved", () => {
    expect(compactSummaryText(simStorySummaryParts(story))).toBe("QB3 · did not play: behind R. Cole, J. Smith · 1 depth chart move · 1 injury");
    expect(simStorySummaryParts([])).toEqual([]);
  });
});

describe("injury_v display", () => {
  it("names the injury with the weeks out, and falls back to the old text without one", () => {
    expect(simOutLine({ out_weeks: 4, injury: "Hamstring" })).toBe("Hamstring · out 4 wks");
    expect(simOutLine({ out_weeks: 1, injury: "Ankle" })).toBe("Ankle · out 1 wk");
    expect(simOutLine({ out_weeks: 4 })).toBe("Out 4w");
    expect(simOutLine({ out_weeks: 0 })).toBe("Out");
    expect(simPlayerStatusLabel({ status: "out", out_weeks: 9, bye_week: null, injury: "Torn ACL" })).toEqual({ label: "Torn ACL · out 9 wks", tone: "danger" });
    expect(simPlayerStatusLabel({ status: "out", out_weeks: 9, bye_week: null })).toEqual({ label: "Out 9w", tone: "danger" });
  });
  it("the shared injury section reads a sim record: season labels, own coverage note", () => {
    const record: InjuryRecordData = {
      ok: true, current_season: 2027, since_season: 2026, career_games_missed: 7, source: "sim",
      current: { label: "Torn ACL", status: "Out", severity: "out", unavailable: true, body_part: "Torn ACL", practice: null, report: "Out 9 weeks more.", line: "Torn ACL · out 9 wks" },
      seasons: [
        { season: 2027, season_label: "S2 2027", games_missed: 4, stints: [{ start_week: 5, end_week: 8, games_missed: 4, injury: "Hamstring" }] },
        { season: 2026, season_label: "S1 2026", games_missed: 3, stints: [{ start_week: 3, end_week: 5, games_missed: 3, injury: null }] },
      ],
    };
    expect(injuryHistoryRows(record).map((r) => [r.seasonLabel, r.injury, r.games])).toEqual([["S2 2027", "Hamstring", "4 games"], ["S1 2026", "Injury (not specified)", "3 games"]]);
    expect(compactSummaryText(injurySummaryParts(record))).toBe("Torn ACL · out 9 wks · 4 games missed in 2027 · 7 career");
    expect(injuryCoverageNote(record)).toBe("From this game's own injury log.");
  });
  it("the sim turns the depth chart and injury sections on but never fetches the real ones", () => {
    const sim = pqvRealWorld(true);
    expect(sim.showDepthChart && sim.showInjuryHistory).toBe(true);
    expect(sim.fetchDepthChart || sim.fetchInjuryHistory).toBe(false);
    const real = pqvRealWorld(false);
    expect(real.fetchDepthChart && real.fetchInjuryHistory).toBe(true);
  });
});
