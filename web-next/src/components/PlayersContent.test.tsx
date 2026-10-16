import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PlayersContent } from "./PlayersContent";
import type { DraftPickAsset, LeagueRankingsResponse, RankedPlayer } from "@/lib/api";

function pick(overrides: Partial<DraftPickAsset>): DraftPickAsset {
  return {
    pick_id: "2027:1:1",
    label: "2027 1st",
    score: 4200,
    season: 2027,
    round: 1,
    original_roster_id: "1",
    owner_roster_id: "1",
    original_team_name: "Dynasty Overlords",
    owner_team_name: "Dynasty Overlords",
    pick_tier: "Premium",
    projected_pick_range: "Picks 1-4",
    projection_confidence: 0.72,
    ...overrides,
  };
}

function player(overrides: Partial<RankedPlayer>): RankedPlayer {
  return {
    player_id: "p1",
    name: "Alpha Receiver",
    position: "WR",
    team: "SF",
    age: 22,
    status: "Active",
    injury_status: null,
    tier: "starter",
    score: 1500,
    overall_rank: 1,
    position_rank: 1,
    rank_unavailable_reason: null,
    opportunity_label: null,
    overall_rating: 90,
    ...overrides,
  };
}

const DATA: LeagueRankingsResponse = {
  ok: true,
  players: [
    player({ player_id: "a", name: "Alpha Receiver", position: "WR", age: 22, injury_status: null }),
    player({ player_id: "b", name: "Beta Back", position: "RB", age: 30, injury_status: "Questionable", score: 1200 }),
    player({ player_id: "c", name: "Gamma Kicker", position: "K", age: 26, status: "Inactive", score: 800 }),
  ],
};

describe("PlayersContent", () => {
  it("renders every player in the pool by default", () => {
    render(<PlayersContent leagueId="league1" leagueName="Dynasty Overlords" data={DATA} />);

    expect(screen.getByRole("heading", { name: "Dynasty Overlords" })).toBeInTheDocument();
    expect(screen.getByText("Alpha Receiver")).toBeInTheDocument();
    expect(screen.getByText("Beta Back")).toBeInTheDocument();
    expect(screen.getByText("Gamma Kicker")).toBeInTheDocument();
    expect(screen.getByText("3 matching players.")).toBeInTheDocument();
  });

  it("filters by search text", () => {
    render(<PlayersContent leagueId="league1" leagueName="Dynasty Overlords" data={DATA} />);

    fireEvent.change(screen.getByPlaceholderText("Search players"), { target: { value: "beta" } });

    expect(screen.getByText("Beta Back")).toBeInTheDocument();
    expect(screen.queryByText("Alpha Receiver")).not.toBeInTheDocument();
    expect(screen.getByText("1 matching player.")).toBeInTheDocument();
  });

  it("filters by position", () => {
    render(<PlayersContent leagueId="league1" leagueName="Dynasty Overlords" data={DATA} />);

    const [positionSelect] = screen.getAllByRole("combobox");
    fireEvent.change(positionSelect, { target: { value: "K" } });

    expect(screen.getByText("Gamma Kicker")).toBeInTheDocument();
    expect(screen.queryByText("Alpha Receiver")).not.toBeInTheDocument();
  });

  it("links each row's Compare CTA into Player Compare with the right player id", () => {
    render(<PlayersContent leagueId="league1" leagueName="Dynasty Overlords" data={DATA} />);

    const links = screen.getAllByRole("link", { name: "Compare" });
    expect(links[0]).toHaveAttribute("href", "/player-compare/league1?a=a&name=Dynasty%20Overlords");
  });

  it("shows the empty-filter message when nothing matches", () => {
    render(<PlayersContent leagueId="league1" leagueName="Dynasty Overlords" data={DATA} />);

    fireEvent.change(screen.getByPlaceholderText("Search players"), { target: { value: "nonexistent" } });

    expect(screen.getByText("No players match this search and filter combination.")).toBeInTheDocument();
  });

  it("hides the Players/Picks toggle and roster-status facet when no picks or rosters are given", () => {
    render(<PlayersContent leagueId="league1" leagueName="Dynasty Overlords" data={DATA} />);

    expect(screen.queryByText("Picks")).not.toBeInTheDocument();
    expect(screen.queryByText("Any roster status")).not.toBeInTheDocument();
  });

  describe("Picks view", () => {
    const PICKS: DraftPickAsset[] = [
      pick({ pick_id: "2027:1:1", owner_team_name: "Dynasty Overlords" }),
      pick({ pick_id: "2028:1:1", season: 2028, owner_roster_id: "2", owner_team_name: "Rival Squad", label: "2028 1st" }),
    ];

    it("shows the Players/Picks toggle once picks are given, defaulting to Players", () => {
      render(<PlayersContent leagueId="league1" leagueName="Dynasty Overlords" data={DATA} picks={PICKS} />);

      expect(screen.getByText("Alpha Receiver")).toBeInTheDocument();
      expect(screen.queryByText("2027 1st")).not.toBeInTheDocument();
    });

    it("switches to Picks and shows every pick, grouped by season with owner context", () => {
      render(<PlayersContent leagueId="league1" leagueName="Dynasty Overlords" data={DATA} picks={PICKS} />);

      fireEvent.click(screen.getByText("Picks"));

      expect(screen.queryByText("Alpha Receiver")).not.toBeInTheDocument();
      expect(screen.getByText("2027 1st")).toBeInTheDocument();
      expect(screen.getByText("2028 1st")).toBeInTheDocument();
      expect(screen.getByText(/Rival Squad/)).toBeInTheDocument();
    });
  });

  describe("roster-status facet", () => {
    const ROSTERS = [
      { roster_id: 1, players: ["a"] },
      { roster_id: 2, players: ["b"] },
    ];

    it("stays hidden without roster data even when picks are present", () => {
      render(
        <PlayersContent
          leagueId="league1"
          leagueName="Dynasty Overlords"
          data={DATA}
          picks={[pick({})]}
        />,
      );

      expect(screen.queryByText("Any roster status")).not.toBeInTheDocument();
    });

    it("filters to rostered players using the union of every roster's players array", () => {
      render(<PlayersContent leagueId="league1" leagueName="Dynasty Overlords" data={DATA} rosters={ROSTERS} />);

      const selects = screen.getAllByRole("combobox");
      const rosterSelect = selects[selects.length - 1];
      fireEvent.change(rosterSelect, { target: { value: "Rostered" } });

      expect(screen.getByText("Alpha Receiver")).toBeInTheDocument();
      expect(screen.getByText("Beta Back")).toBeInTheDocument();
      expect(screen.queryByText("Gamma Kicker")).not.toBeInTheDocument();
    });

    it("filters to available (unrostered) players", () => {
      render(<PlayersContent leagueId="league1" leagueName="Dynasty Overlords" data={DATA} rosters={ROSTERS} />);

      const selects = screen.getAllByRole("combobox");
      const rosterSelect = selects[selects.length - 1];
      fireEvent.change(rosterSelect, { target: { value: "Available" } });

      expect(screen.queryByText("Alpha Receiver")).not.toBeInTheDocument();
      expect(screen.queryByText("Beta Back")).not.toBeInTheDocument();
      expect(screen.getByText("Gamma Kicker")).toBeInTheDocument();
    });
  });
});
