import { describe, expect, it } from "vitest";

import {
  adpHeroTile,
  advancedTiles,
  gameStatLine,
  handOffPlayerId,
  heightLabel,
  hometownLine,
  lineTiles,
  normalizeProspectProfile,
  prospectMetaLine,
  prospectWeeklySeries,
  recruitingTiles,
  roundHeroTile,
} from "./prospectProfile";

describe("prospectProfile", () => {
  it("formats size and the header line from what is on file only", () => {
    expect(heightLabel(76)).toBe(`6'4"`);
    expect(heightLabel(null)).toBeNull();
    expect(prospectMetaLine(2027, { class_year: 3, height_in: 76, weight_lb: 220, hometown: null, school_logo_url: null })).toBe(`Class of 2027 · 6'4" · 220 lb`);
    expect(prospectMetaLine(2027, null)).toBe("Class of 2027");
  });

  it("leads with the stats that matter for his position", () => {
    const line = { passing: { yds: 3000, td: 25, int: 5, cmp: 200, att: 300 }, rushing: { yds: 200, td: 3, car: 50 } };
    const qb = lineTiles(line, "QB").map((t) => t.label);
    expect(qb.slice(0, 3)).toEqual(["Pass yds", "Pass TD", "INT"]);
    expect(lineTiles(line, "QB").find((t) => t.label === "Comp %")?.value).toBe("66.7%");
    expect(lineTiles({ receiving: { rec: 61, yds: 870, td: 7 } }, "WR").map((t) => t.label)).toEqual(["Rec", "Rec yds", "Rec TD", "Yds/rec"]);
    expect(lineTiles({ rushing: { yds: 900, td: 8 }, receiving: { rec: 20, yds: 150 } }, "RB")[0].label).toBe("Rush yds");
    expect(lineTiles({}, "QB")).toEqual([]);
  });

  it("builds one game line and the weekly series, skipping games with no scoring (no invented zeros)", () => {
    expect(gameStatLine({ passing: { yds: 312, td: 3, int: 1 }, rushing: { car: 4, yds: 20 } }, "QB")).toBe("312 pass yds · 3 pass TD · 1 INT · 4 car · 20 rush yds");
    const series = prospectWeeklySeries({
      season: 2026,
      games: [
        { week: 1, opponent: "A", fantasy_points: 18.2 },
        { week: 2, opponent: "B", fantasy_points: null },
        { week: 3, opponent: "C", fantasy_points: 0 },
      ],
    });
    expect(series?.weeks.map((w) => w.week)).toEqual([1, 3]);
    expect(prospectWeeklySeries(null)).toBeNull();
    expect(prospectWeeklySeries({ season: 2026, games: [{ week: 1, opponent: null, fantasy_points: null }] })).toBeNull();
  });

  it("shows advanced metrics as PPA and usage, nothing when absent", () => {
    const tiles = advancedTiles({ season: 2026, ppa: { avg: { all: 0.42, pass: 0.5 }, total: { all: 88.04 } }, usage: { overall: 0.31, pass: 0.5 } }, "QB");
    expect(tiles.map((t) => `${t.label}=${t.value}`)).toEqual(["PPA / play=+0.42", "PPA passing=+0.50", "Total PPA=+88.0", "Usage=31%", "Pass usage=50%"]);
    expect(advancedTiles(null, "QB")).toEqual([]);
  });

  it("recruiting, hometown, ADP and round tiles never fill in what is missing", () => {
    expect(recruitingTiles({ year: 2023, stars: 5, rating: 0.9998, national_rank: 1, high_school: "Newman", city: "New Orleans", state: "LA" }).map((t) => t.value)).toEqual(["5-star", "#1", "0.9998", "2023"]);
    expect(recruitingTiles(null)).toEqual([]);
    expect(hometownLine({ year: 2023, stars: 5, rating: null, national_rank: 1, high_school: "Newman", city: "New Orleans", state: "LA" }, null)).toBe("New Orleans, LA · Newman");
    expect(adpHeroTile(null)).toEqual({ label: "Rookie ADP", value: "—", note: "No ADP yet" });
    expect(adpHeroTile({ adp: 1.4, adp_formatted: "1.04", label: "1QB ADP", source: null }).value).toBe("1.04");
    expect(roundHeroTile(null, 0).note).toBe("No projection yet");
    expect(roundHeroTile(1.6, 5).value).toBe("2");
  });

  it("hands off to the NFL card only with a Sleeper id", () => {
    expect(handOffPlayerId({ sleeper_player_id: "12345" })).toBe("12345");
    expect(handOffPlayerId({ sleeper_player_id: null })).toBeNull();
  });

  it("defaults every list in the payload", () => {
    const body = normalizeProspectProfile({ ok: true });
    expect(body.seasons).toEqual([]);
    expect(body.weekly).toBeNull();
    expect(body.advanced).toBeNull();
    expect(normalizeProspectProfile(null).ok).toBe(false);
  });
});
