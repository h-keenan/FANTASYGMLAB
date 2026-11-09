import { describe, expect, it } from "vitest";

import type { CollegeProspect, DraftPickAsset } from "@/lib/api";
import { needPositionsFrom, prospectFit, rankByFit } from "./scoutingLens";

const prospect = (id: string, position: string, round: number | null, year = 2027): CollegeProspect => ({
  id, name: id, position, school: "X", draft_year: year,
  aggregate: { avg_grade: null, scout_count: round ? 3 : 0, avg_round_projection: round },
  my_report: null, on_watchlist: false,
});
const myPick = { pick_id: "2027:2:1", season: 2027, round: 2 } as DraftPickAsset;
const lens = { needPositions: needPositionsFrom([{ position: "WR", classification: "short_term_need", reasons: [], upgrade_opportunity: false, temporary_injury_pressure: false }, { position: "QB", classification: "covered", reasons: [], upgrade_opportunity: false, temporary_injury_pressure: false }]), myPicks: [myPick] };

describe("scoutingLens", () => {
  it("flags need and pick fit", () => {
    expect(prospectFit(prospect("a", "WR", 2.2), lens)).toEqual({ needsPosition: true, pickNote: "Fits your 2nd (2027)" });
    expect(prospectFit(prospect("b", "QB", 1), lens)).toEqual({ needsPosition: false, pickNote: null });
    expect(prospectFit(prospect("c", "WR", null), lens).pickNote).toBeNull();
    expect(prospectFit(prospect("d", "RB", 2, 2028), lens).pickNote).toBeNull();
  });
  it("ranks fits first, stable otherwise", () => {
    const list = [prospect("b", "QB", 1), prospect("n", "WR", 3), prospect("both", "WR", 2), prospect("z", "TE", 4)];
    expect(rankByFit(list, lens).map((p) => p.id)).toEqual(["both", "n", "b", "z"]);
  });
});
