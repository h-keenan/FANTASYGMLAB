import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DashboardContent } from "./DashboardContent";
import { collapsedModuleProblems } from "@/components/ui/assertCompactInformative";
import { api, type DashboardResponse } from "@/lib/api";

// The Alerts section fetches on its own and needs the auth context; it has its own test (DashboardAlerts.test.tsx).
vi.mock("@/components/DashboardAlerts", () => ({ DashboardAlerts: () => <div data-testid="dashboard-alerts" /> }));

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

const TRADE_PRESENTATION = {
  trade_package: {
    send: [{ asset_type: "player", player_id: "1", name: "R. Walsh", position: "RB", team: "SF", tier: "starter" }],
    receive: [{ asset_type: "player", player_id: "2", name: "C. Murray", position: "QB", team: "NE", tier: "starter" }],
    value_edge: "Slight edge",
    confidence: "Medium",
  },
  partner_team_name: "Team Iron",
  trade_gain: 450,
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
    expect(screen.getByRole("heading", { name: "Do this now · 1" })).toBeInTheDocument();
    // The row is one short line (about six words); the full reason sits behind its tap.
    expect(screen.getByText("Trade for a top-12 RB before…")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("decision-item-toggle"));
    expect(screen.getByTestId("decision-full-title")).toHaveTextContent("Trade for a top-12 RB before the deadline");

    // One snapshot strip (Standing / Playoffs / Team rank) that opens My Team; the rank bars live there now.
    const strip = await screen.findByTestId("today-tiles");
    expect(strip).toHaveAttribute("href", expect.stringContaining("/my-team/abc"));
    expect(screen.getByTestId("today-tile-standing")).toHaveTextContent("7-6");
    expect(screen.getByTestId("today-tile-rank")).toHaveTextContent("#2"); // power rank
    expect(screen.queryByTestId("stat-strip-toggle")).not.toBeInTheDocument();
    expect(screen.queryByText("Starter Strength")).not.toBeInTheDocument();
    // Plan ahead is gone from Today (GM Plan / Waivers / Trade Hub stay reachable from their own entry points).
    expect(screen.queryByText("Plan ahead")).not.toBeInTheDocument();

    expect(screen.getByText(/2 more moves? on Pro/)).toBeInTheDocument();
  });

  it("labels the page with its age when the API served last-known provider data", () => {
    const stale = new Date(Date.now() - 20 * 60_000).toISOString();
    render(<DashboardContent leagueId="abc" leagueName="Dynasty Overlords" data={{ ...FIXTURE, sleeper_data_as_of: stale }} />);
    expect(screen.getByTestId("freshness-label")).toHaveTextContent(/League data as of 2\dm ago \(may be behind\)/);
  });

  it("shows no age label for live data", () => {
    render(<DashboardContent leagueId="abc" leagueName="Dynasty Overlords" data={FIXTURE} />);
    expect(screen.queryByText(/League data as of/)).toBeNull();
  });

  it("shows the quiet-state copy instead of Game Plan cards when there's nothing urgent", async () => {
    const quietFixture: DashboardResponse = {
      ...FIXTURE,
      quiet: true,
      items: [],
      entitlement: { is_premium: true, visible_count: 0, hidden_count: 0 },
    };
    render(<DashboardContent leagueId="abc" leagueName="Dynasty Overlords" data={quietFixture} />);

    expect(await screen.findByText("Nothing needs you this week")).toBeInTheDocument();
  });

  it("orders modules: do this now (best trade is one of its rows), standing line, alerts; no More", async () => {
    const data: DashboardResponse = {
      ...FIXTURE,
      entitlement: { ...FIXTURE.entitlement, free_limit: 1 },
      trade_window: { trade_deadline_week: 11, current_week: 9, trade_deadline_passed: false, message: "" },
      items: [...FIXTURE.items, { ...FIXTURE.items[0], category: "top_priority", headline: "Swap idea", recommendation_id: "rec-t", presentation: TRADE_PRESENTATION } as unknown as DashboardResponse["items"][number]],
    };
    const { container } = render(<DashboardContent leagueId="abc" leagueName="Dynasty Overlords" data={data} />);
    await screen.findByTestId("today-tiles");
    const html = container.innerHTML;
    const at = (marker: string) => html.indexOf(marker);
    const order = [at("decision-queue-heading"), at("decision-trade"), at("today-tiles"), at("dashboard-alerts")];
    expect(order.every((i) => i > -1)).toBe(true);
    expect([...order].sort((x, y) => x - y)).toEqual(order);
    // League activity, the mini-games and League type moved off Today (League tab / My Team).
    expect(at("dashboard-more")).toBe(-1);
    // Free caps are one compact upsell row (no separate free-limit note).
    expect(screen.getByTestId("more-moves-upsell")).toBeInTheDocument();
  });

  it("puts the best trade in Do this now as one row (receive avatar, short reason, Send offer) that opens Trade Hub", async () => {
    const data: DashboardResponse = {
      ...FIXTURE,
      trade_window: { trade_deadline_week: 11, current_week: 9, trade_deadline_passed: false, message: "" },
      items: [{ ...FIXTURE.items[0], presentation: TRADE_PRESENTATION } as unknown as DashboardResponse["items"][number]],
    };
    render(<DashboardContent leagueId="abc" leagueName="Dynasty Overlords" data={data} />);
    const row = await screen.findByTestId("decision-trade");
    expect(row).toHaveTextContent("Get a QB from Team Iron");
    const button = within(row).getByTestId("decision-primary");
    expect(button).toHaveTextContent("Send offer");
    expect(button).toHaveAttribute("href", expect.stringContaining("/trade-hub/abc"));
    // Its tap shows what you send and get, and the gain, in green-safe wording (never a negative figure).
    fireEvent.click(within(row).getByTestId("decision-trade-toggle"));
    expect(screen.getByTestId("decision-trade-detail")).toHaveTextContent("Send R. Walsh · Get C. Murray · +450 value");
    // The old standalone trade card is gone (one place), and no trades tile.
    expect(screen.queryByTestId("today-trade-idea")).not.toBeInTheDocument();
    expect(screen.queryByTestId("today-tile-trades")).not.toBeInTheDocument();
  });

  it("never headlines a trade that costs value: a negative idea is hidden, the best positive one leads, nothing is red", async () => {
    const neg = { ...TRADE_PRESENTATION, trade_gain: -125 };
    const mk = (presentation: typeof TRADE_PRESENTATION, id: string) => ({ ...FIXTURE.items[0], presentation, recommendation_id: id }) as unknown as DashboardResponse["items"][number];
    const only = render(<DashboardContent leagueId="abc" leagueName="Dynasty Overlords" data={{ ...FIXTURE, items: [mk(neg, "n")] }} />);
    await screen.findByTestId("today-tiles");
    expect(screen.queryByTestId("decision-trade")).not.toBeInTheDocument();
    expect(only.container.textContent).not.toMatch(/-125/);
    only.unmount();
    render(<DashboardContent leagueId="abc" leagueName="Dynasty Overlords" data={{ ...FIXTURE, items: [mk(neg, "n"), mk(TRADE_PRESENTATION, "p")] }} />);
    fireEvent.click(await screen.findByTestId("decision-trade-toggle"));
    expect(await screen.findByTestId("decision-trade-detail")).toHaveTextContent("+450 value");
  });

  it("lists urgent items once in the Decision Queue, linking to GM Plan / Matchup", () => {
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
    const block = screen.getByTestId("decision-queue");
    expect(within(block).getByRole("heading", { name: /^Do this now/ })).toBeInTheDocument();
    expect(within(block).getByText("Starter ruled out")).toBeInTheDocument();
    expect(within(block).getByText(/Trade deadline: This week/)).toBeInTheDocument();
    expect(within(screen.getByTestId("decision-lineup")).getByTestId("decision-primary")).toHaveAttribute("href", "/matchup/abc?name=Dynasty+Overlords");
    expect(within(screen.getByTestId("decision-deadline")).getByTestId("decision-primary")).toHaveAttribute("href", "/gm-plan/abc?name=Dynasty%20Overlords");
    // Shown once: the queue owns the lineup issue, nothing else repeats it.
    expect(screen.getAllByText("Starter ruled out")).toHaveLength(1);
  });

  it("treats the server's top-priority non-trade tile as a queue decision and shows it once", () => {
    render(<DashboardContent leagueId="abc" leagueName="Dynasty Overlords" data={FIXTURE} />);
    const block = screen.getByTestId("decision-queue");
    expect(within(block).getByText("Trade for a top-12 RB before…")).toBeInTheDocument();
    expect(screen.getAllByText(/Trade for a top-12 RB/)).toHaveLength(1);
  });

  it("caps Do this now at five rows and sends the rest to the GM Plan with See all (N)", () => {
    const many: DashboardResponse = {
      ...FIXTURE,
      items: Array.from({ length: 7 }, (_, i) => ({ ...FIXTURE.items[0], headline: `Decision ${i}`, recommendation_id: `r${i}`, route_player_score: 50 - i })),
    };
    render(<DashboardContent leagueId="abc" leagueName="Dynasty Overlords" data={many} />);
    const block = screen.getByTestId("decision-queue");
    expect(within(block).getAllByTestId("decision-primary")).toHaveLength(5);
    expect(within(block).getByRole("heading", { name: /^Do this now · 7/ })).toBeInTheDocument();
    expect(within(block).getByTestId("decision-see-all")).toHaveTextContent("See all (7)");
    expect(within(block).getByTestId("decision-see-all")).toHaveAttribute("href", "/gm-plan/abc?name=Dynasty%20Overlords");
  });

  it("shows no decision rows when nothing is urgent", async () => {
    render(<DashboardContent leagueId="abc" leagueName="Dynasty Overlords" data={{ ...FIXTURE, items: [] }} />);
    expect(await screen.findByText("Nothing needs you this week")).toBeInTheDocument();
    expect(screen.queryByTestId("decision-primary")).not.toBeInTheDocument();
  });

  it("never invents a deadline: no window means no deadline chip", () => {
    render(<DashboardContent leagueId="abc" leagueName="Dynasty Overlords" data={FIXTURE} />);
    expect(screen.queryByText(/Trade deadline/i)).not.toBeInTheDocument();
  });

  it("has no trade row after the deadline", async () => {
    const data: DashboardResponse = {
      ...FIXTURE,
      trade_window: { trade_deadline_week: 11, current_week: 12, trade_deadline_passed: true, message: "x" },
    };
    render(<DashboardContent leagueId="abc" leagueName="Dynasty Overlords" data={data} />);
    await screen.findByTestId("today-tiles");
    expect(screen.queryByTestId("today-tile-trades")).not.toBeInTheDocument();
    expect(screen.queryByTestId("decision-trade")).not.toBeInTheDocument();
  });

  it("turns each lineup problem into its own one-line row (avatar, reason, Swap) and puts the best move on the matchup card", async () => {
    const player = (id: string, name: string, pos: string, injury = "") => ({ player_id: id, name, position: pos, team: "NE", tier: "starter", slot: pos, points: 10, projection_status: null, injury_label: injury });
    const spy = vi.spyOn(api, "getLeagueMatchup").mockResolvedValue({
      ok: true,
      week: 10,
      reason: "",
      my_team: { roster_id: "1", team_name: "Gridiron Gurus", avatar_url: null, starters: [], real_starters: [], open_slots: [], real_empty_slots: [], has_live_data: false },
      opponent: { team_name: "Shiesty", owner_name: null, avatar_url: null, starters: [], real_starters: [], open_slots: [], real_empty_slots: [], has_live_data: false },
      win_probability: { available: true, probability: 0.03, my_projected_total: 109.7, opponent_projected_total: 136.9 },
      suggested_moves: [
        { slot: "RB", start: player("s1", "Sam Ortiz", "RB"), over: player("o1", "Jordan Reyes", "RB", "Out"), over_reason: "ruled_out", gain: 11.2, locked: false },
        { slot: "WR", start: player("s2", "Dre Kline", "WR"), over: player("o2", "Marcus Bell", "WR", "Questionable"), over_reason: null, gain: 9.8, locked: false },
        { slot: "QB", start: player("s3", "Cal Murray", "QB"), over: player("o3", "Tyler Voss", "QB", "Doubtful"), over_reason: "ruled_out", gain: 14.1, locked: true },
      ],
    } as unknown as Awaited<ReturnType<typeof api.getLeagueMatchup>>);
    vi.spyOn(api, "getMyTeamNeeds").mockRejectedValue(new Error("x"));
    vi.spyOn(api, "getTeamRankings").mockRejectedValue(new Error("x"));
    try {
      render(<DashboardContent leagueId="abc" leagueName="Dynasty Overlords" data={{ ...FIXTURE, items: [] }} />);
      const rows = await screen.findAllByTestId("decision-lineup");
      // The locked move (his game started) is never offered; biggest gain first.
      expect(rows).toHaveLength(2);
      expect(rows[0]).toHaveTextContent("Reyes out, start Ortiz");
      expect(rows[0]).toHaveTextContent("+11.2 projected");
      expect(rows[1]).toHaveTextContent("Bell questionable, start Kline");
      expect(within(rows[0]).getByTestId("decision-primary")).toHaveTextContent("Swap");
      expect(within(rows[0]).getByTestId("decision-primary")).toHaveAttribute("href", expect.stringContaining("plan=swap&out=o1&in=s1"));
      // Its tap shows the replacement as a player card.
      fireEvent.click(within(rows[0]).getByTestId("decision-lineup-toggle"));
      expect(within(rows[0]).getByTestId("decision-player")).toHaveTextContent("Sam Ortiz");
      // The matchup card's one best-move line opens the planner on the same swap.
      const move = screen.getByTestId("today-matchup-move");
      expect(move).toHaveTextContent("Start Ortiz over Reyes (+11.2)");
      expect(move).toHaveAttribute("href", expect.stringContaining("plan=swap&out=o1&in=s1"));
      // Each fact once: the lineup problems are not repeated as a Lineup module, and nothing says "nothing needs you".
      expect(screen.queryByText(/Nothing needs you/)).not.toBeInTheDocument();
      // The matchup ring card: win chance, scores, trailing chip; tap opens the detail.
      const card = screen.getByTestId("today-matchup");
      expect(card).toHaveTextContent("WK 10 · VS SHIESTY");
      expect(card).toHaveTextContent("109.7 vs 136.9");
      expect(screen.getByTestId("today-matchup-chip")).toHaveTextContent("trailing 27.2");
      expect(within(card).getByRole("button")).toHaveAttribute("aria-expanded", "false");
    } finally {
      spy.mockRestore();
    }
  });

  it("does not claim nothing needs you over injured starters", async () => {
    render(<DashboardContent leagueId="abc" leagueName="Dynasty Overlords" data={{ ...FIXTURE, items: [], team_snapshot: { ...FIXTURE.team_snapshot!, injured_starters: 3 } }} />);
    expect(await screen.findByText("No better lineup swaps")).toBeInTheDocument();
    expect(screen.getByText(/3 starters are injured, but no bench player projects higher/)).toBeInTheDocument();
    expect(screen.queryByText("Nothing needs you this week")).not.toBeInTheDocument();
  });

  it("no collapsed module on Today is an empty header (module template rule)", () => {
    const { container } = render(<DashboardContent leagueId="abc" leagueName="Dynasty Overlords" data={FIXTURE} />);
    expect(container.querySelectorAll('button[aria-expanded="false"]').length).toBeGreaterThan(1);
    expect(collapsedModuleProblems(container)).toEqual([]);
  });

  it("keeps League activity, Guess the Player and League type off Today", () => {
    render(<DashboardContent leagueId="abc" leagueName="Dynasty Overlords" data={FIXTURE} />);
    expect(screen.queryByTestId("dashboard-more")).not.toBeInTheDocument();
    expect(screen.queryByText("League type")).not.toBeInTheDocument();
    for (const id of ["more-league-activity", "more-guess-player", "more-name-match"]) expect(screen.queryByTestId(id)).not.toBeInTheDocument();
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
