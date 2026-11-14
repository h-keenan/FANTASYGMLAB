import { describe, expect, it } from "vitest";

import type { SimHistoryEntry, SimTeamHistoryMove } from "./simGame";
import { simCareerSeasonParts, simCareerSeasonTitle, simDraftSlotText, simHistoryText, simSeasonRecord, simTeamMoveText, simWhenLabel } from "./simHistory";

const base = { season: 1, year: null, week: 5, offseason: false, team_id: "3", team_name: "Bench Mob" };
const entry = (e: Partial<SimHistoryEntry> & { kind: SimHistoryEntry["kind"] }): SimHistoryEntry => ({ ...base, ...e }) as SimHistoryEntry;

describe("sim history text", () => {
  it("dates are a season and a week, in the game's own calendar", () => {
    expect(simWhenLabel({ season: 1, year: null, week: 5, offseason: false })).toBe("Week 5");
    expect(simWhenLabel({ season: 2, year: null, week: 5, offseason: false })).toBe("S2 · Week 5");
    expect(simWhenLabel({ season: 2, year: 2028, week: 5, offseason: false })).toBe("S2 2028 · Week 5");
    expect(simWhenLabel({ season: 1, year: 2027, week: 0, offseason: false })).toBe("S1 2027 draft");
    expect(simWhenLabel({ season: 1, year: null, week: 0, offseason: false })).toBe("Draft");
    expect(simWhenLabel({ season: 1, year: 2027, week: 9, offseason: true })).toBe("S1 2027 offseason");
  });
  it("draft slot and drafted sentence", () => {
    expect(simDraftSlotText(3, 31, true)).toBe("Round 3, pick 31 overall (auto)");
    expect(simDraftSlotText(undefined, 3)).toBe("");
    expect(simHistoryText(entry({ kind: "drafted", round: 3, pick: 31, draft: "league", week: 0 }))).toBe("Drafted by Bench Mob in the league draft: Round 3, pick 31 overall");
    expect(simHistoryText(entry({ kind: "drafted", round: 1, pick: 4, draft: "rookie", class_year: 2028, via: { team_id: "9", team_name: "Hail Marys" } }))).toBe(
      "Drafted by Bench Mob in 2028 rookie draft: Round 1, pick 4 overall (pick from Hail Marys)",
    );
  });
  it("moves read as sentences", () => {
    expect(simHistoryText(entry({ kind: "claimed", dropped: "Old Guy" }))).toBe("Claimed off waivers by Bench Mob (dropped Old Guy)");
    expect(simHistoryText(entry({ kind: "cut" }))).toBe("Cut by Bench Mob");
    expect(simHistoryText(entry({ kind: "traded", from_team: { team_id: "3", team_name: "Bench Mob" }, to_team: { team_id: "7", team_name: "Rats" }, with_assets: [{ id: "a", name: "Ace", pos: "WR" }] }))).toBe("Traded from Bench Mob to Rats for Ace");
    const move = (m: Partial<SimTeamHistoryMove>) => ({ season: 1, year: null, week: 2, offseason: false, ...m }) as SimTeamHistoryMove;
    expect(simTeamMoveText(move({ kind: "trade", with_team: { team_id: "7", team_name: "Rats" }, sent: [{ id: "a", name: "Ace", pos: "WR" }], received: [{ id: "b", name: "Bo", pos: "RB" }, { id: "p", name: "2028 round 2 pick", pos: null }] }))).toBe("Traded Ace to Rats for Bo, 2028 round 2 pick");
    expect(simTeamMoveText(move({ kind: "claim", added: { id: "a", name: "Ace", pos: "WR" }, dropped: { id: "b", name: "Bo", pos: "RB" } }))).toBe("Claimed Ace, dropped Bo");
    expect(simTeamMoveText(move({ kind: "drop", player: { id: "b", name: "Bo", pos: "RB" }, reason: "roster_limit" }))).toBe("Dropped Bo (roster limit)");
    expect(simSeasonRecord({ wins: 9, losses: 5, ties: 0 })).toBe("9-5");
    expect(simSeasonRecord({ wins: 9, losses: 4, ties: 1 })).toBe("9-4-1");
  });
});

describe("sim career season summary", () => {
  it("reads 'S3 2028 · 14 g · 212.4 pts · 15.2 avg · WR12' and drops what it does not know", () => {
    const base = { season: 3, year: 2028, season_label: "S3 2028", games: 14, points: 212.4, ppg: 15.2, pos: "WR", pos_rank: 12 };
    expect(simCareerSeasonTitle(base)).toBe("S3 2028");
    expect(simCareerSeasonParts(base).map((p) => p.text).join(" · ")).toBe("14 g · 212.4 pts · 15.2 avg · WR12");
    expect(simCareerSeasonParts({ ...base, pos: null, pos_rank: null, ppg: null }).map((p) => p.text)).toEqual(["14 g", "212.4 pts"]);
    expect(simCareerSeasonTitle({ season: 2, year: 2027 })).toBe("S2 2027");
  });
});
