import { describe, expect, it } from "vitest";

import { simDynastyHistoryView, simDynastySummaryView, type SimDynastySummary } from "@/lib/simGame";

const history = {
  champions: [
    { season_no: 1, year: 2026, team_id: "7", name: "Rivals", is_you: false },
    { season_no: 2, year: 2027, team_id: "3", name: "My Team", is_you: true },
    { season_no: 3, year: 2028, team_id: "7", name: "Rivals", is_you: false },
  ],
  title_leaders: [
    { team_id: "7", name: "Rivals", titles: 2, is_you: false },
    { team_id: "3", name: "My Team", titles: 1, is_you: true },
  ],
  best_record: { year: 2028, team_id: "7", name: "Rivals", record: "14-0" },
  most_points: { year: 2027, team_id: "3", name: "My Team", pf: 2101.4 },
};

describe("long dynasty league history", () => {
  it("lists champions newest first, marks you, and gives leaders and records", () => {
    const v = simDynastyHistoryView(history);
    expect(v.champions.map((c) => c.label)).toEqual(["S3 2028: Rivals", "S2 2027: My Team (you)", "S1 2026: Rivals"]);
    expect(v.champions[1].you).toBe(true);
    expect(v.leaders).toEqual(["Rivals 2 titles", "My Team (you) 1 title"]);
    expect(v.records).toEqual(["Best record: Rivals 14-0 (2028)", "Most points: My Team 2101 (2027)"]);
    expect(v.summary).toBe("3 champions");
  });

  it("is empty and safe for saves without history", () => {
    expect(simDynastyHistoryView(undefined)).toEqual({ champions: [], leaders: [], records: [], summary: "No champions yet" });
    const d = { mode: "dynasty", seasons_total: 20, seasons_played: 12, start_year: 2026, complete: false, titles: 0, playoff_trips: 0, avg_finish: null, wins: 0, losses: 0, best_season: null, by_year: [], picks_held: 0 } as SimDynastySummary;
    const view = simDynastySummaryView(d);
    expect(view.seasonsLine).toBe("12 of 20 seasons played");
    expect(view.history.champions).toEqual([]);
  });
});
