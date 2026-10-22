import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LeaguePulseCard, leaguePulseHighlights } from "./LeaguePulseCard";
import { api, type LeagueTeamRankingsResponse, type TeamRanking } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      getTeamRankings: vi.fn(),
    },
  };
});

function team(overrides: Partial<TeamRanking>): TeamRanking {
  return {
    roster_id: "1",
    team_name: "Test Team",
    owner_name: "Owner",
    owner_username: null,
    avatar_url: null,
    wins: 0,
    losses: 0,
    ties: 0,
    record_label: "0-0",
    points_for: 0,
    points_against: 0,
    standing_rank: null,
    win_pct_label: null,
    points_for_label: null,
    points_against_label: null,
    playoff_status: null,
    on_playoff_line: false,
    power_rank: null,
    power_rank_tied: false,
    power_score: null,
    franchise_rank: null,
    franchise_rank_tied: false,
    franchise_score: null,
    draft_capital_rank: null,
    draft_capital_rank_tied: false,
    draft_capital_score: null,
    pick_count: null,
    first_rounders: null,
    starter_rank: null,
    starter_rank_tied: false,
    starter_score: null,
    bench_rank: null,
    bench_rank_tied: false,
    bench_score: null,
    age_rank: null,
    age_rank_tied: false,
    average_age: null,
    strategy: null,
    strategy_label: null,
    archetype: null,
    archetype_label: null,
    archetype_explanation: null,
    archetype_strengths: [],
    archetype_risks: [],
    archetype_recommendations: [],
    trade_tendency: "Neutral",
    transaction_activity_count: 0,
    firsts_acquired: 0,
    firsts_sent: 0,
    current_streak: 0,
    team_badges: [],
    injured_starters: null,
    health_flag: null,
    ...overrides,
  };
}

function response(teams: TeamRanking[], overrides: Partial<LeagueTeamRankingsResponse> = {}): LeagueTeamRankingsResponse {
  return {
    ok: true,
    teams,
    reason: "",
    standings_available: false,
    standings_message: "",
    season: "",
    week_label: "",
    playoff_teams: null,
    ...overrides,
  };
}

beforeEach(() => {
  vi.mocked(api.getTeamRankings).mockReset();
});

describe("leaguePulseHighlights", () => {
  it("picks the real league-wide leader for each signal from an already-fetched team list", () => {
    const teams = [
      team({ roster_id: "1", team_name: "Quiet Co", transaction_activity_count: 2, current_streak: 0 }),
      team({ roster_id: "2", team_name: "Trade Machine", transaction_activity_count: 11, current_streak: -1 }),
      team({ roster_id: "3", team_name: "Hot Hand", transaction_activity_count: 4, current_streak: 4 }),
      team({ roster_id: "4", team_name: "Ice Cold", transaction_activity_count: 1, current_streak: -3 }),
    ];

    const highlights = leaguePulseHighlights(teams);

    expect(highlights).toEqual([
      expect.objectContaining({ label: "Most Active Manager", metric: "11 moves", team: expect.objectContaining({ team_name: "Trade Machine" }) }),
      expect.objectContaining({ label: "Hot Streak", metric: "W4", team: expect.objectContaining({ team_name: "Hot Hand" }) }),
      expect.objectContaining({ label: "Cold Streak", metric: "L3", team: expect.objectContaining({ team_name: "Ice Cold" }) }),
    ]);
  });

  it("omits a streak highlight when no team's current streak crosses the real 2-result threshold", () => {
    const teams = [
      team({ roster_id: "1", current_streak: 1, transaction_activity_count: 3 }),
      team({ roster_id: "2", current_streak: -1, transaction_activity_count: 0 }),
    ];

    const highlights = leaguePulseHighlights(teams);

    expect(highlights.map((h) => h.label)).toEqual(["Most Active Manager"]);
  });

  it("omits the Most Active highlight when every team has made zero moves", () => {
    const teams = [team({ roster_id: "1", transaction_activity_count: 0 }), team({ roster_id: "2", transaction_activity_count: 0 })];
    expect(leaguePulseHighlights(teams)).toEqual([]);
  });

  it("uses singular 'move' for a leader with exactly one move", () => {
    const highlights = leaguePulseHighlights([team({ transaction_activity_count: 1 })]);
    expect(highlights[0].metric).toBe("1 move");
  });
});

describe("LeaguePulseCard", () => {
  it("renders nothing while loading and nothing on fetch failure", async () => {
    vi.mocked(api.getTeamRankings).mockRejectedValue(new Error("down"));
    const { container } = render(<LeaguePulseCard leagueId="abc" />);
    expect(container).toBeEmptyDOMElement();
    await waitFor(() => expect(api.getTeamRankings).toHaveBeenCalledWith("abc"));
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when the league has no standout activity or streak yet", async () => {
    vi.mocked(api.getTeamRankings).mockResolvedValue(
      response([team({ transaction_activity_count: 0, current_streak: 0 })]),
    );
    const { container } = render(<LeaguePulseCard leagueId="abc" />);
    await waitFor(() => expect(api.getTeamRankings).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when the backend reports the endpoint isn't ready", async () => {
    vi.mocked(api.getTeamRankings).mockResolvedValue(response([], { ok: false, reason: "no_rankings_data" }));
    const { container } = render(<LeaguePulseCard leagueId="abc" />);
    await waitFor(() => expect(api.getTeamRankings).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("renders the real league-wide Most Active/Hot Streak/Cold Streak leaders from real fixture data", async () => {
    vi.mocked(api.getTeamRankings).mockResolvedValue(
      response([
        team({ roster_id: "1", team_name: "Trade Machine", transaction_activity_count: 11, current_streak: 0 }),
        team({ roster_id: "2", team_name: "Hot Hand", transaction_activity_count: 3, current_streak: 4 }),
        team({ roster_id: "3", team_name: "Ice Cold", transaction_activity_count: 2, current_streak: -3 }),
      ]),
    );
    render(<LeaguePulseCard leagueId="abc" />);

    await screen.findByText("League Activity");
    expect(screen.getByText("Trade Machine")).toBeInTheDocument();
    expect(screen.getByText("11 moves")).toBeInTheDocument();
    expect(screen.getByText("Hot Hand")).toBeInTheDocument();
    expect(screen.getByText("W4")).toBeInTheDocument();
    expect(screen.getByText("Ice Cold")).toBeInTheDocument();
    expect(screen.getByText("L3")).toBeInTheDocument();
  });

  it("refetches when the leagueId prop changes", async () => {
    vi.mocked(api.getTeamRankings).mockResolvedValue(response([team({ transaction_activity_count: 5 })]));
    const { rerender } = render(<LeaguePulseCard leagueId="abc" />);
    await waitFor(() => expect(api.getTeamRankings).toHaveBeenCalledWith("abc"));

    rerender(<LeaguePulseCard leagueId="xyz" />);
    await waitFor(() => expect(api.getTeamRankings).toHaveBeenCalledWith("xyz"));
    expect(api.getTeamRankings).toHaveBeenCalledTimes(2);
  });
});
