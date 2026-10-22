import { describe, expect, it } from "vitest";

import type { PortfolioIndexResponse, PortfolioLeague, PortfolioLeagueResponse } from "@/lib/api";
import { composePortfolio } from "@/lib/portfolioProgress";

const INDEX: PortfolioIndexResponse = {
  ok: true,
  is_premium: true,
  lens: "Dynasty",
  leagues: [],
  failed_leagues: [],
  upsell: null,
  saved_leagues: [
    { league_id: "a", league_name: "Alpha" },
    { league_id: "b", league_name: "Bravo" },
    { league_id: "c", league_name: "Charlie" },
  ],
};

function row(leagueId: string, leagueName: string): PortfolioLeague {
  return {
    league_id: leagueId,
    league_name: leagueName,
    team_name: "Team",
    team_avatar_url: "",
    wins: 1,
    losses: 0,
    ties: 0,
    health_flag: "Stable",
    power_rank: 1,
    power_rank_tied: false,
    franchise_rank: 1,
    franchise_rank_tied: false,
    roster_value_rank: 1,
    roster_value_rank_tied: false,
    archetype: null,
    archetype_label: null,
    top_asset: null,
    top_item: null,
    top_items: [],
  } as PortfolioLeague;
}

function ok(league: PortfolioLeague): PortfolioLeagueResponse {
  return { ok: true, is_premium: true, lens: "Dynasty", league, failed_league: null, upsell: null };
}

describe("composePortfolio", () => {
  it("holds every saved league as pending before any row arrives", () => {
    const composed = composePortfolio(INDEX, {});
    expect(composed.pending.map((league) => league.league_id)).toEqual(["a", "b", "c"]);
    expect(composed.response.leagues).toEqual([]);
    expect(composed.settled).toBe(false);
    expect(composed.order).toEqual(["a", "b", "c"]);
  });

  it("shows rows as they land, keeps the rest pending, and keeps saved order", () => {
    const composed = composePortfolio(INDEX, {
      c: { status: "success", data: ok(row("c", "Charlie")) },
      a: { status: "pending" },
    });
    expect(composed.response.leagues.map((league) => league.league_id)).toEqual(["c"]);
    expect(composed.pending.map((league) => league.league_id)).toEqual(["a", "b"]);
    expect(composed.settled).toBe(false);
  });

  it("reports server-side failures and request errors as failed leagues, never drops them", () => {
    const composed = composePortfolio(INDEX, {
      a: { status: "success", data: ok(row("a", "Alpha")) },
      b: {
        status: "success",
        data: {
          ok: true,
          is_premium: true,
          lens: "Dynasty",
          league: null,
          failed_league: { league_id: "b", league_name: "Bravo", reason: "empty_roster" },
          upsell: null,
        },
      },
      c: { status: "error" },
    });
    expect(composed.settled).toBe(true);
    expect(composed.response.leagues.map((league) => league.league_id)).toEqual(["a"]);
    expect(composed.response.failed_leagues).toEqual([
      { league_id: "b", league_name: "Bravo", reason: "empty_roster" },
      { league_id: "c", league_name: "Charlie", reason: "unavailable" },
    ]);
  });

  it("passes a Free caller's upsell straight through with nothing pending", () => {
    const upsell = { title: "Portfolio is Premium", body: "Upgrade." };
    const composed = composePortfolio(
      { ...INDEX, is_premium: false, saved_leagues: [], upsell },
      {},
    );
    expect(composed.response.is_premium).toBe(false);
    expect(composed.response.upsell).toEqual(upsell);
    expect(composed.pending).toEqual([]);
    expect(composed.settled).toBe(true);
  });
});
