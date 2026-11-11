import { render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DashboardContent } from "./DashboardContent";
import { api, type DashboardResponse, type LeagueTeamRankingsResponse, type MatchupResponse, type MyTeamNeedsResponse } from "@/lib/api";

const SNAPSHOT: NonNullable<DashboardResponse["team_snapshot"]> = {
  wins: 3,
  losses: 5,
  ties: 0,
  health_flag: "Stable",
  key_injuries_summary: "",
  top_injury_impact_summary: "",
  top_injury_impact_players: [],
  injured_starters: 0,
  average_age: 26.4,
  power_rank: 11,
  power_rank_tied: false,
  franchise_rank: 1,
  franchise_rank_tied: false,
  starter_rank: 3,
  starter_rank_tied: false,
  bench_rank: 5,
  bench_rank_tied: false,
};

const DATA: DashboardResponse = {
  ok: true,
  quiet: true,
  quiet_reason: "",
  reason: "",
  items: [],
  team_snapshot: SNAPSHOT,
  entitlement: { is_premium: true, visible_count: 0, hidden_count: 0 },
};

const MATCHUP = {
  ok: true,
  week: 9,
  reason: "",
  my_team: { roster_id: "3", team_name: "Ringer", avatar_url: null },
  opponent: { roster_id: "5", team_name: "Rival FC", owner_name: "r", avatar_url: null },
  win_probability: { available: true, probability: 0.634, my_projected_total: 101.3, opponent_projected_total: 96 },
  suggested_moves: [
    { slot: "RB", start: { name: "Backup Back" }, over: { name: "Hurt Back" }, over_reason: "ruled_out", gain: 6.2, locked: false },
  ],
  open_slots: [],
} as unknown as MatchupResponse;

const NEEDS = {
  ok: true,
  reason: "",
  strengths: ["QB"],
  weaknesses: ["RB"],
  position_groups: [
    { position: "QB", classification: "covered", reasons: [], upgrade_opportunity: false, temporary_injury_pressure: false },
    { position: "RB", classification: "short_term_need", reasons: [], upgrade_opportunity: true, temporary_injury_pressure: false },
  ],
} as unknown as MyTeamNeedsResponse;

const RANKINGS = {
  ok: true,
  standings_available: true,
  teams: ["1", "2", "3"].map((id, index) => ({
    roster_id: id,
    wins: 1,
    losses: 1,
    standing_rank: index + 1,
    playoff_status: index === 2 ? "Outside the playoff line" : "In playoff position",
    power_rank: index + 1,
    average_age: 25 + index,
  })),
} as unknown as LeagueTeamRankingsResponse;

describe("TeamStatusHero on the Dashboard", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("shows matchup, lineup, standing and position rows from real responses, each labeled", async () => {
    vi.spyOn(api, "getLeagueMatchup").mockResolvedValue(MATCHUP);
    vi.spyOn(api, "getMyTeamNeeds").mockResolvedValue(NEEDS);
    vi.spyOn(api, "getTeamRankings").mockResolvedValue(RANKINGS);
    vi.spyOn(api, "getGamesSeasonSim").mockRejectedValue(new Error("offseason"));
    render(<DashboardContent leagueId="abc" leagueName="L" data={DATA} />);
    const hero = await screen.findByTestId("team-status-hero");
    await waitFor(() => expect(within(hero).getByText("vs Rival FC")).toBeInTheDocument());
    expect(within(hero).getByText("Your win chance")).toBeInTheDocument();
    expect(within(hero).getByText("63%")).toBeInTheDocument();
    expect(within(hero).getByText("101.3 - 96.0")).toBeInTheDocument();
    expect(within(hero).getByText("1 starter can't play (bye or out)")).toBeInTheDocument();
    expect(within(hero).getByText("Best swap: start Backup Back over Hurt Back (+6.2 pts)")).toBeInTheDocument();
    expect(within(hero).getByText("3rd of 3")).toBeInTheDocument();
    expect(within(hero).getByText("3-5")).toBeInTheDocument();
    expect(within(hero).getByTestId("team-status-position-RB")).toHaveAttribute("data-weakest", "true");
    expect(within(hero).getByTestId("team-status-position-QB")).not.toHaveAttribute("data-weakest");
    expect(within(hero).getByRole("link", { name: /Improve RB first/ })).toHaveAttribute("href", "/trade-hub/abc?name=L");
    // Tiles carry their own context from the same rankings response.
    await waitFor(() => expect(screen.getAllByText("of 3 teams").length).toBeGreaterThan(0));
    expect(screen.getByText("League avg 26.0")).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/\bNaN\b|undefined/);
  });

  it("degrades: offseason or failed requests hide the rows instead of showing zeros", async () => {
    vi.spyOn(api, "getLeagueMatchup").mockRejectedValue(new Error("x"));
    vi.spyOn(api, "getMyTeamNeeds").mockRejectedValue(new Error("x"));
    vi.spyOn(api, "getTeamRankings").mockRejectedValue(new Error("x"));
    vi.spyOn(api, "getGamesSeasonSim").mockRejectedValue(new Error("x"));
    render(<DashboardContent leagueId="abc" leagueName="L" data={{ ...DATA, team_snapshot: { ...SNAPSHOT, wins: 0, losses: 0, injured_starters: null } }} />);
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(screen.queryByTestId("team-status-hero")).toBeNull();
    expect(screen.queryByText("Your win chance")).toBeNull();
    expect(screen.queryByTestId("team-status-positions")).toBeNull();
  });
});
