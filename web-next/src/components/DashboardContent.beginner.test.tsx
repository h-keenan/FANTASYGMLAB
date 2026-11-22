import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach } from "vitest";
import { describe, expect, it, vi } from "vitest";

import { DashboardContent } from "./DashboardContent";
import { api, type DashboardResponse } from "@/lib/api";
import { experienceCopy } from "@/lib/experienceCopy";

// The Alerts section fetches on its own and needs the auth context; it has its own test (DashboardAlerts.test.tsx).
vi.mock("@/components/DashboardAlerts", () => ({ DashboardAlerts: () => <div data-testid="dashboard-alerts" /> }));

vi.mock("@/context/ExperienceLevelContext", () => ({
  useExperienceCopy: () => experienceCopy("beginner"),
  useExperienceLevel: () => ({ level: "beginner" }),
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

function expandHelp() {
  for (const b of screen.queryAllByRole("button", { name: /^About / })) fireEvent.click(b);
}

describe("DashboardContent for a beginner", () => {
  beforeEach(() => window.localStorage.clear());
  it("keeps the Do this now help; the rank-term glossary moved with the rank bars to My Team", async () => {
    render(<DashboardContent leagueId="abc" leagueName="Dynasty Overlords" data={FIXTURE} />);
    await screen.findByTestId("today-tiles");
    expandHelp();
    // The snapshot strip is one link (no "?" in it); the rank glossary lives on My Team.
    expect(screen.getByLabelText("Team summary").querySelectorAll("[data-info-mark]")).toHaveLength(0);
    expect(screen.queryByText(/What "This season" means/)).not.toBeInTheDocument();
    expect(screen.getByText(/^Today lists the roster moves/)).toBeInTheDocument(); // the Do this now help
  });

  it("tells a beginner no move is needed when nothing is urgent", async () => {
    const quiet: DashboardResponse = { ...FIXTURE, items: [], entitlement: { is_premium: true, visible_count: 0, hidden_count: 0 } };
    render(<DashboardContent leagueId="abc" leagueName="Dynasty Overlords" data={quiet} />);
    await screen.findByText("Nothing needs you this week");
    expandHelp();
    expect(screen.getByText(/No move is needed right now/)).toBeInTheDocument();
  });

  it("explains trades to a beginner on the Do this now \"?\" when a trade row is in it; the stance line moved off Today (GM Plan owns it)", async () => {
    const withIdea: DashboardResponse = {
      ...FIXTURE,
      items: [
        {
          ...FIXTURE.items[0],
          presentation: {
            trade_package: {
              send: [{ asset_type: "player", player_id: "1", name: "R. Walsh", position: "RB" }],
              receive: [{ asset_type: "player", player_id: "2", name: "C. Murray", position: "QB" }],
            },
            partner_team_name: "Team Iron",
          },
        } as unknown as DashboardResponse["items"][number],
      ],
    };
    render(<DashboardContent leagueId="abc" leagueName="Dynasty Overlords" data={withIdea} />);
    await screen.findByTestId("decision-trade");
    expandHelp();
    expect(screen.getByText(/who you give, who you get/)).toBeInTheDocument(); // the Do this now "?" carries the trade explainer
    expect(screen.queryByTestId("dashboard-stance-line")).not.toBeInTheDocument();
  });
});
