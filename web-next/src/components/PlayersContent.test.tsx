import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PlayersContent } from "./PlayersContent";
import type { LeagueRankingsResponse, RankedPlayer } from "@/lib/api";

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
});
