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

describe("DashboardContent", () => {
  it("renders the league name, Game Plan cards, and Team Snapshot tiles from real fixture data", () => {
    render(<DashboardContent leagueId="abc" leagueName="Dynasty Overlords" data={FIXTURE} />);

    expect(screen.getByRole("heading", { name: "Dynasty Overlords" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Today" })).toBeInTheDocument();
    expect(screen.getByText("Trade for a top-12 RB before the deadline")).toBeInTheDocument();
    expect(screen.getByText("Test Back")).toBeInTheDocument();

    expect(screen.getByRole("heading", { name: "My Team" })).toBeInTheDocument();
    // The stat strip appears once at the top and is not repeated in Team Snapshot.
    expect(screen.getAllByText("Record")).toHaveLength(1);
    expect(screen.getAllByText("Power Rank")).toHaveLength(1);
    expect(screen.getByText("Starter Strength")).toBeInTheDocument();
    expect(screen.getByText("Bench Strength")).toBeInTheDocument();
    expect(screen.getByText("Injuries")).toBeInTheDocument();
    expect(screen.getByText("7-6")).toBeInTheDocument();
    expect(screen.getByText("#2")).toBeInTheDocument(); // power rank
    expect(screen.getByText("T-1")).toBeInTheDocument(); // franchise rank, tied

    expect(screen.getByText(/2 more moves available on Premium/)).toBeInTheDocument();
  });

  // coridian_, 2026-10-18: "you can just put them all under watch... to
  // make this much simpler and more streamlined" — Top Priority keeps its
  // own full card; every other category groups into one WatchListCard.
  it("groups every non-top_priority item into one WatchListCard, separate from Top Priority's own card", () => {
    const groupedFixture: DashboardResponse = {
      ...FIXTURE,
      items: [
        { ...FIXTURE.items[0], category: "top_priority", headline: "Headline trade", recommendation_id: "rec-top" },
        {
          ...FIXTURE.items[0],
          category: "watch",
          headline: "Ashton Jeanty trending down",
          reason: "Usage down 13%.",
          route_player_id: "",
          route_player_name: "",
          recommendation_id: "rec-watch",
        },
        {
          ...FIXTURE.items[0],
          category: "waiver_opportunity",
          headline: "Chimere Dike",
          reason: "Strong opportunity.",
          route_player_id: "",
          route_player_name: "",
          recommendation_id: "rec-waiver",
        },
      ],
    };
    render(<DashboardContent leagueId="abc" leagueName="Dynasty Overlords" data={groupedFixture} />);

    // All three headlines render somewhere on the page...
    expect(screen.getByText("Headline trade")).toBeInTheDocument();
    expect(screen.getByText("Ashton Jeanty trending down")).toBeInTheDocument();
    expect(screen.getByText("Chimere Dike")).toBeInTheDocument();
    // ...but Watch and Waiver Opportunity share one card, while Top
    // Priority gets its own — exactly 2 <article> cards total, not 3.
    expect(document.querySelectorAll("article")).toHaveLength(2);
    // Type tags, a real usage-drop indicator, and no placeholder copy.
    expect(screen.getByText("Trending")).toBeInTheDocument();
    expect(screen.getByText("Waiver")).toBeInTheDocument();
    expect(screen.getByText("↓ 13%")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Watchlist/ })).toBeInTheDocument();
    expect(document.body.textContent?.toLowerCase()).not.toContain("placeholder");
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

  it("orders modules: now strip, Trades, next moves, My Team, alerts, League Activity, More", () => {
    const data: DashboardResponse = {
      ...FIXTURE,
      entitlement: { ...FIXTURE.entitlement, free_limit: 1 },
      trade_window: { trade_deadline_week: 11, current_week: 9, trade_deadline_passed: false, message: "" },
      this_week: {
        mode: "in_season",
        week: 9,
        rows: [{ key: "lineup", status: "Set", tone: "positive", headline: "Lineup is set", why: "", cta_label: null, route: null, player_id: "" }],
        next_action: null,
      },
      items: [
        ...FIXTURE.items,
        { ...FIXTURE.items[0], category: "watch", headline: "Watch item", recommendation_id: "rec-2" },
      ],
    };
    const { container } = render(<DashboardContent leagueId="abc" leagueName="Dynasty Overlords" data={data} />);
    const html = container.innerHTML;
    const at = (marker: string) => html.indexOf(marker);
    const order = [
      at("dashboard-now-strip"),
      at("dashboard-trades-block"),
      at("game-plan-heading"),
      at("snapshot-heading"),
      at("watchlist-heading"),
      at("dashboard-more"),
    ];
    expect(order.every((i) => i > -1)).toBe(true);
    expect([...order].sort((x, y) => x - y)).toEqual(order);
    // Free caps are announced up front, from the server's number.
    expect(screen.getByText("Free: showing 1 of 3 next moves")).toBeInTheDocument();
  });

  it("shows the real trade deadline and the one primary Trades action", () => {
    const data: DashboardResponse = {
      ...FIXTURE,
      trade_window: { trade_deadline_week: 11, current_week: 9, trade_deadline_passed: false, message: "" },
    };
    render(<DashboardContent leagueId="abc" leagueName="Dynasty Overlords" data={data} />);
    expect(screen.getByText("2 wks left (Wk 11)")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Analyze a trade" })).toHaveAttribute("href", "/trade-analyzer/abc?name=Dynasty%20Overlords");
  });

  it("never invents a deadline: no window means no deadline chip", () => {
    render(<DashboardContent leagueId="abc" leagueName="Dynasty Overlords" data={FIXTURE} />);
    expect(screen.queryByText(/Trade deadline/i)).not.toBeInTheDocument();
  });

  it("says trades are closed after the deadline and hides the board link", () => {
    const data: DashboardResponse = {
      ...FIXTURE,
      trade_window: { trade_deadline_week: 11, current_week: 12, trade_deadline_passed: true, message: "x" },
    };
    render(<DashboardContent leagueId="abc" leagueName="Dynasty Overlords" data={data} />);
    expect(screen.getByText(/Trade deadline has passed/)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /More trade ideas/ })).not.toBeInTheDocument();
  });

  it("keeps the mini-games collapsed behind More", () => {
    render(<DashboardContent leagueId="abc" leagueName="Dynasty Overlords" data={FIXTURE} />);
    expect(screen.getByTestId("dashboard-more")).not.toHaveAttribute("open");
  });

  it("offers one shared glossary for the rank labels", () => {
    render(<DashboardContent leagueId="abc" leagueName="Dynasty Overlords" data={FIXTURE} />);
    expect(screen.getAllByRole("button", { name: /what do these mean/i })).toHaveLength(1);
  });
});
