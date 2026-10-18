import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PortfolioContent } from "./PortfolioContent";
import type { BriefingItem, PortfolioLeague, PortfolioResponse } from "@/lib/api";

function briefingItem(overrides: Partial<BriefingItem>): BriefingItem {
  return {
    category: "top_priority",
    headline: "Trade away Test Player before Week 10",
    reason: "Value is trending down after a usage drop.",
    supporting_context: null,
    destination: "trade_hub",
    route_player_id: "4046",
    route_player_name: "Test Player",
    route_player_position: "RB",
    route_player_team: "SF",
    route_player_tier: "starter",
    route_player_score: 88,
    mentioned_players: [],
    recommendation_narrative: null,
    presentation: null,
    recommendation_id: "rec-1",
    tier_label: "Starter",
    ...overrides,
  };
}

function league(overrides: Partial<PortfolioLeague>): PortfolioLeague {
  return {
    league_id: "league-1",
    league_name: "Dynasty Overlords",
    team_name: "The Contenders",
    wins: 7,
    losses: 3,
    ties: 0,
    health_flag: "Stable",
    power_rank: 1,
    power_rank_tied: false,
    franchise_rank: 2,
    franchise_rank_tied: false,
    roster_value_rank: 1,
    roster_value_rank_tied: false,
    archetype: "contender",
    archetype_label: "Contender",
    top_asset: null,
    top_item: briefingItem({}),
    top_items: [
      briefingItem({}),
      briefingItem({
        category: "watch",
        headline: "Test Backup is questionable for Sunday",
        reason: "Listed questionable with a hamstring issue.",
        recommendation_id: "rec-2",
      }),
    ],
    ...overrides,
  };
}

const BASE_RESPONSE: PortfolioResponse = {
  ok: true,
  is_premium: true,
  lens: "Dynasty",
  leagues: [league({})],
  failed_leagues: [],
  upsell: null,
};

describe("PortfolioContent", () => {
  it("renders a league card with its record, rank, and every quick-glance signal", () => {
    render(<PortfolioContent data={BASE_RESPONSE} />);

    expect(screen.getByText(/The Contenders — Dynasty Overlords/)).toBeInTheDocument();
    // Top-3 shows the rank in the gold/silver/bronze pill badge, not
    // repeated in the record metadata line (mirrors modules/portfolio_page.py).
    expect(screen.getByText("7-3")).toBeInTheDocument();
    expect(screen.getByText("#1")).toBeInTheDocument();
    expect(screen.getByText("Value is trending down after a usage drop.")).toBeInTheDocument();
    expect(screen.getByText("Listed questionable with a hamstring issue.")).toBeInTheDocument();
    expect(screen.getByText("Top Priority")).toBeInTheDocument();
    expect(screen.getByText("Watch")).toBeInTheDocument();
    expect(screen.getByText("Open Dynasty Overlords Dashboard →")).toBeInTheDocument();
  });

  it("shows the Roster Power rank in the metadata line (not a badge) when rank is outside the top 3", () => {
    render(
      <PortfolioContent
        data={{ ...BASE_RESPONSE, leagues: [league({ power_rank: 7, power_rank_tied: true })] }}
      />,
    );

    expect(screen.getByText("7-3 · Roster Power T-7")).toBeInTheDocument();
  });

  it("renders a compact player card for a signal that names a player, not just text", () => {
    render(<PortfolioContent data={BASE_RESPONSE} />);

    // route_player_id/name on the top_priority item (see briefingItem()
    // defaults) should render through BriefingItemPlayers as an identity
    // chip, not just appear inside the headline/reason prose.
    expect(screen.getAllByText("Test Player").length).toBeGreaterThan(0);
  });

  it("hides a Watch item's raw pipe-delimited reason once its player chips render", () => {
    render(
      <PortfolioContent
        data={{
          ...BASE_RESPONSE,
          leagues: [
            league({
              top_item: briefingItem({
                category: "watch",
                reason: "Test Player (RB) - starter | Backup Guy (WR) - bench",
                mentioned_players: [
                  { player_id: "4046", name: "Test Player", position: "RB", team: "SF", player_tier: "starter" },
                ],
              }),
              top_items: [
                briefingItem({
                  category: "watch",
                  reason: "Test Player (RB) - starter | Backup Guy (WR) - bench",
                  mentioned_players: [
                    { player_id: "4046", name: "Test Player", position: "RB", team: "SF", player_tier: "starter" },
                  ],
                }),
              ],
            }),
          ],
        }}
      />,
    );

    expect(screen.queryByText(/Test Player \(RB\) - starter \| Backup Guy/)).not.toBeInTheDocument();
    expect(screen.getAllByText("Test Player").length).toBeGreaterThan(0);
  });

  it("shows the health flag badge only when it isn't Stable", () => {
    render(<PortfolioContent data={{ ...BASE_RESPONSE, leagues: [league({ health_flag: "Injury-hit" })] }} />);

    expect(screen.getByText("Injury-hit")).toBeInTheDocument();
  });

  it("shows the failed-leagues note without blanking the leagues that loaded", () => {
    render(
      <PortfolioContent
        data={{
          ...BASE_RESPONSE,
          failed_leagues: [{ league_id: "league-2", league_name: "Broken League", reason: "unavailable" }],
        }}
      />,
    );

    expect(screen.getByText(/Couldn't load 1 league right now: Broken League/)).toBeInTheDocument();
    expect(screen.getByText(/The Contenders — Dynasty Overlords/)).toBeInTheDocument();
  });

  it("shows the exact Premium upsell copy for a free account", () => {
    render(
      <PortfolioContent
        data={{
          ok: true,
          is_premium: false,
          lens: "Dynasty",
          leagues: [],
          failed_leagues: [],
          upsell: {
            title: "See every league at a glance",
            body:
              "Portfolio is a Premium feature — free accounts keep one saved league, so there's nothing to aggregate yet. " +
              "Upgrade to Premium to save every league you're in and see your record, rank, and top need or " +
              "opportunity across all of them in one place.",
          },
        }}
      />,
    );

    expect(screen.getByRole("heading", { name: "See every league at a glance" })).toBeInTheDocument();
    expect(
      screen.getByText(/free accounts keep one saved league, so there's nothing to aggregate yet/),
    ).toBeInTheDocument();
  });

  it("shows the no-saved-leagues empty state", () => {
    render(<PortfolioContent data={{ ...BASE_RESPONSE, leagues: [], failed_leagues: [] }} />);

    expect(screen.getByText("No saved leagues yet")).toBeInTheDocument();
  });
});
