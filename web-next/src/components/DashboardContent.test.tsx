import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DashboardContent } from "./DashboardContent";
import type { DashboardResponse } from "@/lib/api";

const FIXTURE: DashboardResponse = {
  ok: true,
  quiet: false,
  quiet_reason: "",
  reason: "",
  items: [
    {
      category: "Top Priority",
      headline: "Trade for a top-12 RB before the deadline",
      reason: "Your roster is bottom-third at RB with no clear bench answer.",
      supporting_context: null,
      destination: "trade_hub",
      route_player_id: "4046",
      route_player_name: "Test Back",
      route_player_position: "RB",
      route_player_team: "SF",
      route_player_tier: "starter",
      route_player_score: 88.4,
      recommendation_narrative: null,
      presentation: null,
      recommendation_id: "rec-1",
      tier_label: "Top Priority",
    },
  ],
  team_snapshot: {
    wins: 7,
    losses: 6,
    ties: 0,
    health_flag: "Stable",
    key_injuries_summary: "",
    top_injury_impact_summary: "",
    top_injury_impact_players: [],
    injured_starters: 0,
    average_age: 26.4,
    power_rank: 2,
    power_rank_tied: false,
    franchise_rank: 1,
    franchise_rank_tied: true,
    starter_rank: 3,
    starter_rank_tied: false,
    bench_rank: 5,
    bench_rank_tied: false,
  },
  entitlement: { is_premium: false, visible_count: 1, hidden_count: 2 },
};

describe("DashboardContent", () => {
  it("renders the league name, Game Plan cards, and Team Snapshot tiles from real fixture data", () => {
    render(<DashboardContent leagueId="abc" leagueName="Dynasty Overlords" data={FIXTURE} />);

    expect(screen.getByRole("heading", { name: "Dynasty Overlords" })).toBeInTheDocument();
    expect(screen.getByText("Today's Game Plan")).toBeInTheDocument();
    expect(screen.getByText("Trade for a top-12 RB before the deadline")).toBeInTheDocument();
    expect(screen.getByText("Test Back")).toBeInTheDocument();

    expect(screen.getByText("Team Snapshot")).toBeInTheDocument();
    expect(screen.getByText("7-6")).toBeInTheDocument();
    expect(screen.getByText("#2")).toBeInTheDocument(); // power rank
    expect(screen.getByText("T-1")).toBeInTheDocument(); // franchise rank, tied

    expect(screen.getByText(/2 more moves available on Premium/)).toBeInTheDocument();
  });

  it("shows the quiet-state copy instead of Game Plan cards when there's nothing urgent", () => {
    const quietFixture: DashboardResponse = {
      ...FIXTURE,
      quiet: true,
      items: [],
      entitlement: { is_premium: true, visible_count: 0, hidden_count: 0 },
    };
    render(<DashboardContent leagueId="abc" leagueName="Dynasty Overlords" data={quietFixture} />);

    expect(screen.getByText("No urgent roster issues right now.")).toBeInTheDocument();
  });
});
