import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DashboardContent } from "./DashboardContent";
import { collapsedModuleProblems } from "@/components/ui/assertCompactInformative";
import { api, type DashboardResponse } from "@/lib/api";

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

/** Open a CompactModule by its collapsed header (the accessible name starts with the title). */
function expandModule(title: RegExp | string) {
  fireEvent.click(screen.getByRole("button", { name: typeof title === "string" ? new RegExp(`^${title}`) : title }));
}

describe("DashboardContent", () => {
  beforeEach(() => window.localStorage.clear());

  it("renders the league name, Game Plan cards, and Team Snapshot tiles from real fixture data", async () => {
    render(<DashboardContent leagueId="abc" leagueName="Dynasty Overlords" data={FIXTURE} />);

    expect(screen.getByRole("heading", { name: "Dynasty Overlords" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "This week" })).toBeInTheDocument();
    expect(screen.getByText("Trade for a top-12 RB before the deadline")).toBeInTheDocument();

    // My Team is one compact module: its collapsed summary carries the ranks; the tiles open on tap.
    expect(screen.getByRole("button", { name: /^My Team: .*Power/ })).toBeInTheDocument();
    expandModule("My Team");
    // Record lives once, in the "Your team right now" hero, not repeated in the tiles.
    expect(screen.getByRole("heading", { name: "Your team right now" })).toBeInTheDocument();
    expect(await screen.findAllByText("Record")).toHaveLength(1);
    expect(screen.getAllByText("Power Rank")).toHaveLength(1);
    expect(screen.getByText("Starter Strength")).toBeInTheDocument();
    expect(screen.getByText("Bench Strength")).toBeInTheDocument();
    expect(screen.getByText("Injured starters")).toBeInTheDocument();
    expect(screen.getByText("7-6")).toBeInTheDocument();
    expect(screen.getByText("#2")).toBeInTheDocument(); // power rank
    expect(screen.getByText("T-1")).toBeInTheDocument(); // franchise rank, tied

    expect(screen.getByText(/2 more moves? on Pro/)).toBeInTheDocument();
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
    expandModule("Watchlist");
    expect(screen.getAllByText(/Ashton Jeanty trending down/).length).toBeGreaterThan(0);
    expect(screen.getByText("Chimere Dike")).toBeInTheDocument();
    // ...but Watch and Waiver Opportunity share one card, while Top
    // Priority gets its own — exactly 2 <article> cards total, not 3.
    expect(document.querySelectorAll("article")).toHaveLength(2);
    // Type tags, a real usage-drop indicator, and no placeholder copy.
    expect(screen.getByText("Trending")).toBeInTheDocument();
    expect(screen.getByText("Waiver")).toBeInTheDocument();
    expect(screen.getByText("Usage is down 13% recently.")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-watchlist")).toBeInTheDocument();
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

  it("orders modules: needs attention, this week, trade ideas, My Team, alerts, League Activity, More", () => {
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
      at("game-plan-heading"),
      at("dashboard-trades-block"),
      at('aria-label="Team summary"'),
      at("dashboard-watchlist"),
      at("dashboard-more"),
    ];
    expect(order.every((i) => i > -1)).toBe(true);
    expect([...order].sort((x, y) => x - y)).toEqual(order);
    // Free caps are one compact upsell row (no separate free-limit note).
    expect(screen.getByTestId("more-moves-upsell")).toBeInTheDocument();
  });

  it("shows the real trade deadline chip and trade ideas as one count line with a Trade Hub link", () => {
    const data: DashboardResponse = {
      ...FIXTURE,
      trade_window: { trade_deadline_week: 11, current_week: 9, trade_deadline_passed: false, message: "" },
      items: [
        {
          ...FIXTURE.items[0],
          presentation: { trade_package: { send: [], receive: [] } },
        } as unknown as DashboardResponse["items"][number],
      ],
    };
    render(<DashboardContent leagueId="abc" leagueName="Dynasty Overlords" data={data} />);
    expect(screen.getByText(/Deadline 2 wks left \(Wk 11\)/)).toBeInTheDocument();
    expect(screen.queryByTestId("dashboard-now-strip")).toBeNull();
    const block = screen.getByTestId("dashboard-trades-block");
    expect(block.textContent).toMatch(/1 trade idea/);
    expect(within(block).getByRole("link")).toHaveAttribute("href", "/trade-hub/abc?name=Dynasty%20Overlords");
    // No idea cards on the Dashboard: the give/get package is not rendered here.
    expect(within(block).queryByRole("heading", { level: 3 })).not.toBeInTheDocument();
  });

  it("lists urgent items once under Needs attention, linking to GM Plan / Matchup", () => {
    const data: DashboardResponse = {
      ...FIXTURE,
      trade_window: { trade_deadline_week: 11, current_week: 11, trade_deadline_passed: false, message: "" },
      this_week: {
        mode: "in_season",
        week: 11,
        rows: [{ key: "lineup", status: "Out", tone: "risk", headline: "Starter ruled out", why: "Replace him", cta_label: "Fix", route: "matchup", player_id: "" }],
        next_action: null,
      },
    };
    render(<DashboardContent leagueId="abc" leagueName="Dynasty Overlords" data={data} />);
    const block = screen.getByTestId("dashboard-needs-attention");
    expect(within(block).getByRole("heading", { name: "Needs attention" })).toBeInTheDocument();
    expect(within(block).getByText("Starter ruled out")).toBeInTheDocument();
    expect(within(block).getByText(/Trade deadline: This week/)).toBeInTheDocument();
    expect(within(block).getByRole("link", { name: /Starter ruled out/ })).toHaveAttribute("href", "/matchup/abc?name=Dynasty+Overlords");
    expect(within(block).getByRole("link", { name: /Trade deadline/ })).toHaveAttribute("href", "/gm-plan/abc?name=Dynasty%20Overlords");
    // Shown once: the at-a-glance strip drops the lineup and deadline chips.
    expect(screen.getAllByText("Starter ruled out")).toHaveLength(1);
    expect(screen.queryByText("Trade deadline")).not.toBeInTheDocument();
  });

  it("treats the server's top-priority non-trade tile as urgent and shows it once", () => {
    render(<DashboardContent leagueId="abc" leagueName="Dynasty Overlords" data={FIXTURE} />);
    const block = screen.getByTestId("dashboard-needs-attention");
    expect(within(block).getByText("Trade for a top-12 RB before the deadline")).toBeInTheDocument();
    expect(screen.getAllByText("Trade for a top-12 RB before the deadline")).toHaveLength(1);
  });

  it("shows no Needs attention list when nothing is urgent", () => {
    render(<DashboardContent leagueId="abc" leagueName="Dynasty Overlords" data={{ ...FIXTURE, items: [] }} />);
    expect(screen.queryByTestId("dashboard-needs-attention")).not.toBeInTheDocument();
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
    expect(screen.getByTestId("dashboard-trades-block").textContent).toMatch(/Trade deadline has passed/);
  });

  it("no collapsed module on Today is an empty header (module template rule)", () => {
    const { container } = render(<DashboardContent leagueId="abc" leagueName="Dynasty Overlords" data={FIXTURE} />);
    expect(container.querySelectorAll('button[aria-expanded="false"]').length).toBeGreaterThan(1);
    expect(collapsedModuleProblems(container)).toEqual([]);
  });

  it("keeps the mini-games collapsed behind More", () => {
    render(<DashboardContent leagueId="abc" leagueName="Dynasty Overlords" data={FIXTURE} />);
    expect(within(screen.getByTestId("dashboard-more")).getByRole("button", { name: /^More/ })).toHaveAttribute("aria-expanded", "false");
  });

  it("offers one shared glossary for the rank labels", () => {
    render(<DashboardContent leagueId="abc" leagueName="Dynasty Overlords" data={FIXTURE} />);
    expandModule("My Team");
    expect(screen.getAllByRole("button", { name: /what do these mean/i })).toHaveLength(1);
  });

  it("shows the direction check-in the server asks for, on the real Dashboard only (not the sample preview)", async () => {
    const spy = vi.spyOn(api, "getDirectionCheckin").mockResolvedValue({
      ok: true, show: true, reason: "", moment: "midseason", moment_key: "2026:midseason", stance: "balanced", stance_label: "Balanced",
      options: [{ value: "competing", label: "Competing" }], headline: "Midseason: still Balanced?", body: "Does Balanced still describe your team?",
    });
    try {
      const { unmount } = render(<DashboardContent leagueId="abc" leagueName="Dynasty Overlords" data={FIXTURE} />);
      expect(await screen.findByTestId("direction-checkin")).toHaveTextContent("Midseason: still Balanced?");
      expect(spy).toHaveBeenCalledWith("abc");
      unmount();
      spy.mockClear();
      render(<DashboardContent leagueId="abc" leagueName="Sample" data={FIXTURE} sample={{ onBlockedLink: () => {} }} />);
      expect(spy).not.toHaveBeenCalled();
      expect(screen.queryByTestId("direction-checkin")).not.toBeInTheDocument();
    } finally {
      spy.mockRestore();
    }
  });
});
