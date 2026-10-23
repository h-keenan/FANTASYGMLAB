import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DashboardContent } from "./DashboardContent";
import type { DashboardResponse } from "@/lib/api";
import { experienceCopy } from "@/lib/experienceCopy";

vi.mock("@/context/ExperienceLevelContext", () => ({
  useExperienceCopy: () => experienceCopy("beginner"),
}));

const FIXTURE: DashboardResponse = {
  ok: true,
  quiet: false,
  quiet_reason: "",
  reason: "",
  items: [
    {
      category: "top_priority",
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
      route_player_injury_status: "",
      mentioned_players: [],
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

describe("DashboardContent for a beginner", () => {
  it("explains rank terms in short lines under the strip, not inside the 4-column tiles", () => {
    render(<DashboardContent leagueId="abc" leagueName="Dynasty Overlords" data={FIXTURE} />);
    const strip = screen.getByLabelText("Team summary");
    const lines = Array.from(strip.querySelectorAll("p[data-beginner-help]")).map((p) => p.textContent);
    expect(lines.some((l) => l?.startsWith("Power Rank: "))).toBe(true);
    expect(lines.some((l) => l?.startsWith("Average Age: "))).toBe(true);
    expect(screen.getByText(/^Today lists the roster moves/)).toBeInTheDocument();
  });

  it("tells a beginner no move is needed when nothing is urgent", () => {
    const quiet: DashboardResponse = { ...FIXTURE, items: [], entitlement: { is_premium: true, visible_count: 0, hidden_count: 0 } };
    render(<DashboardContent leagueId="abc" leagueName="Dynasty Overlords" data={quiet} />);
    expect(screen.getByText(/No move is needed right now/)).toBeInTheDocument();
  });
});
