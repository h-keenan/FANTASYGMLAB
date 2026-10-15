import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { LeagueRankingsContent } from "./LeagueRankingsContent";
import type { LeagueTeamRankingsResponse, PlayoffOddsResponse, TeamRanking } from "@/lib/api";
import { api } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      getLeaguePlayoffOdds: vi.fn(),
    },
  };
});

function team(overrides: Partial<TeamRanking>): TeamRanking {
  return {
    roster_id: "1",
    team_name: "Dynasty Overlords",
    owner_name: "coridian_",
    owner_username: "coridian_",
    avatar_url: null,
    wins: 7,
    losses: 2,
    ties: 0,
    record_label: "7-2",
    points_for: 1200.4,
    points_against: 1050.1,
    standing_rank: 1,
    win_pct_label: "77.8%",
    points_for_label: "1,200.4",
    points_against_label: "1,050.1",
    playoff_status: "Playoff seed #1",
    on_playoff_line: false,
    power_rank: 1,
    power_rank_tied: false,
    power_score: 8800,
    franchise_rank: 2,
    franchise_rank_tied: false,
    franchise_score: 9200,
    draft_capital_rank: 3,
    draft_capital_rank_tied: false,
    draft_capital_score: 450,
    pick_count: 8,
    first_rounders: 2,
    starter_rank: 1,
    starter_rank_tied: false,
    starter_score: 6400,
    bench_rank: 4,
    bench_rank_tied: false,
    bench_score: 2400,
    age_rank: 5,
    age_rank_tied: false,
    average_age: 25.4,
    strategy: "contender",
    strategy_label: "Contender",
    archetype: "juggernaut",
    archetype_label: "Juggernaut",
    archetype_explanation: null,
    archetype_strengths: [],
    archetype_risks: [],
    archetype_recommendations: [],
    trade_tendency: "Neutral",
    transaction_activity_count: 4,
    firsts_acquired: 1,
    firsts_sent: 0,
    current_streak: 2,
    team_badges: ["Hot Streak"],
    injured_starters: 0,
    health_flag: "Stable",
    ...overrides,
  };
}

const BASE_RESPONSE: LeagueTeamRankingsResponse = {
  ok: true,
  teams: [team({}), team({ roster_id: "2", team_name: "Rival Squad", power_rank: 2, standing_rank: 2 })],
  reason: "",
  standings_available: true,
  standings_message: "",
  season: "2026",
  week_label: "Through Week 9",
  playoff_teams: 6,
};

describe("LeagueRankingsContent", () => {
  it("renders the league name and every board's section heading", () => {
    render(<LeagueRankingsContent leagueId="L1" leagueName="My League" data={BASE_RESPONSE} />);

    expect(screen.getByRole("heading", { name: "My League" })).toBeInTheDocument();
    expect(screen.getByText("2026 Standings")).toBeInTheDocument();
    expect(screen.getByText("Playoff Odds")).toBeInTheDocument();
    expect(screen.getByText("Roster Power Rankings")).toBeInTheDocument();
    expect(screen.getByText("Franchise Value")).toBeInTheDocument();
    expect(screen.getByText("Draft Capital")).toBeInTheDocument();
    expect(screen.getByText("Starter Quality")).toBeInTheDocument();
    expect(screen.getByText("Bench Depth")).toBeInTheDocument();
    expect(screen.getAllByText("Dynasty Overlords").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Rival Squad").length).toBeGreaterThan(0);
  });

  it("shows the not-ready message instead of boards when there are no teams", () => {
    const empty: LeagueTeamRankingsResponse = { ...BASE_RESPONSE, teams: [], reason: "no_rankings_data" };
    render(<LeagueRankingsContent leagueId="L1" leagueName="My League" data={empty} />);

    expect(screen.getByText(/don't have enough roster data/)).toBeInTheDocument();
    expect(screen.queryByText("Roster Power Rankings")).not.toBeInTheDocument();
  });

  it("shows the Standings not-ready message when standings_available is false", () => {
    const notReady: LeagueTeamRankingsResponse = {
      ...BASE_RESPONSE,
      standings_available: false,
      standings_message: "Standings will populate once regular-season results are available.",
    };
    render(<LeagueRankingsContent leagueId="L1" leagueName="My League" data={notReady} />);

    expect(screen.getByText("Standings will populate once regular-season results are available.")).toBeInTheDocument();
  });

  it("gates Playoff Odds behind an explicit tap and renders results once calculated", async () => {
    const oddsResponse: PlayoffOddsResponse = {
      ok: true,
      reason: "",
      teams: [
        {
          roster_id: "1",
          team_name: "Dynasty Overlords",
          owner_name: "coridian_",
          avatar_url: null,
          record_label: "7-2",
          playoff_probability: 92.4,
          median_final_wins: 11,
          median_final_losses: 3,
          median_seed: 1,
          remaining_games: 5,
          clinched: false,
          eliminated: false,
        },
      ],
      weeks_remaining: 5,
      slope_fitted: true,
    };
    vi.mocked(api.getLeaguePlayoffOdds).mockResolvedValue(oddsResponse);

    render(<LeagueRankingsContent leagueId="L1" leagueName="My League" data={BASE_RESPONSE} />);

    const button = screen.getByRole("button", { name: "Calculate playoff odds" });
    expect(api.getLeaguePlayoffOdds).not.toHaveBeenCalled();

    fireEvent.click(button);

    await waitFor(() => expect(screen.getByText("92%")).toBeInTheDocument());
    expect(api.getLeaguePlayoffOdds).toHaveBeenCalledWith("L1");
  });

  it("shows a reason message instead of rows when playoff odds aren't ready", async () => {
    vi.mocked(api.getLeaguePlayoffOdds).mockResolvedValue({ ok: true, reason: "offseason", teams: [] });

    render(<LeagueRankingsContent leagueId="L1" leagueName="My League" data={BASE_RESPONSE} />);
    fireEvent.click(screen.getByRole("button", { name: "Calculate playoff odds" }));

    await waitFor(() =>
      expect(screen.getByText("Playoff odds will be available once the regular season begins.")).toBeInTheDocument(),
    );
  });
});
