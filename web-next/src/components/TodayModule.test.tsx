import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TodayModule } from "./TodayModule";
import type { BriefingItem, DashboardResponse, ThisWeek } from "@/lib/api";

const THURSDAY = new Date(2026, 9, 22, 12);
const TUESDAY = new Date(2026, 9, 20, 12);

const WEEK: ThisWeek = {
  mode: "in_season",
  week: 7,
  next_action: null,
  rows: [
    { key: "lineup", status: "Check", tone: "risk", headline: "Check Matchup: Starter RB is out", why: "Bench RB can step in.", cta_label: "Review lineup", route: "matchup", player_id: "2" },
    { key: "waiver", status: "Add", tone: "waiver", headline: "Top add: Free Agent", why: "Fills RB2.", cta_label: "Claim a waiver", route: "waivers", player_id: "99" },
    { key: "trade", status: "Hold", tone: "neutral", headline: "Hold: no trade improves your team", why: "No offer clears the bar.", cta_label: null, route: null, player_id: "" },
  ],
};

function item(over: Partial<BriefingItem>): BriefingItem {
  return {
    category: "top_priority", headline: "Roster pressure at WR", reason: "Thin at WR.", supporting_context: null,
    destination: "my_team", route_player_id: "", route_player_name: "", route_player_position: "", route_player_team: "",
    route_player_tier: "", route_player_score: null, route_player_injury_status: "", mentioned_players: [],
    recommendation_narrative: null, presentation: null, recommendation_id: "r1", tier_label: "", ...over,
  };
}

function data(over: Partial<DashboardResponse> = {}): DashboardResponse {
  return {
    ok: true, quiet: false, quiet_reason: "", reason: "", items: [item({})], team_snapshot: null,
    entitlement: { is_premium: true, visible_count: 1, hidden_count: 0 }, this_week: WEEK, ...over,
  };
}

describe("TodayModule", () => {
  it("is one section with the week in the heading and the risk row before the card", () => {
    const { container } = render(<TodayModule data={data()} leagueId="abc" leagueName="L" now={THURSDAY} />);
    expect(screen.getByRole("heading", { name: "Today · Week 7" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "This week" })).toBeNull();
    expect(container.querySelectorAll("section")).toHaveLength(1);
    const text = container.textContent ?? "";
    expect(text.indexOf("Starter RB is out")).toBeLessThan(text.indexOf("Roster pressure at WR"));
    expect(screen.getByRole("link", { name: "Review lineup" })).toHaveAttribute("href", "/matchup/abc?name=L");
    expect(screen.getByRole("link", { name: "View all game plan items" })).toBeInTheDocument();
  });

  it("puts waivers under Later this week on game days, and in the main list on Tuesday", () => {
    const { container, rerender } = render(<TodayModule data={data()} leagueId="abc" leagueName="L" now={THURSDAY} />);
    const later = container.querySelector("[data-fgl-today-later]") as HTMLElement;
    expect(within(later).getByText("Top add: Free Agent")).toBeInTheDocument();
    expect(within(later).getByText("Hold: no trade improves your team")).toBeInTheDocument();
    rerender(<TodayModule data={data()} leagueId="abc" leagueName="L" now={TUESDAY} />);
    const later2 = container.querySelector("[data-fgl-today-later]") as HTMLElement;
    expect(within(later2).queryByText("Top add: Free Agent")).toBeNull();
    expect(screen.getByText("Top add: Free Agent")).toBeInTheDocument();
  });

  it("shows a trade idea once (row wins over the matching card)", () => {
    const week: ThisWeek = { ...WEEK, rows: [{ key: "trade", status: "Idea", tone: "trade", headline: "Deebo Samuel Sr.", why: "w", cta_label: "See the trade", route: "trade_hub", player_id: "1" }] };
    render(<TodayModule data={data({ this_week: week, items: [item({ headline: "Deebo Samuel Sr.", destination: "trade_hub" })] })} leagueId="a" leagueName="L" now={THURSDAY} />);
    expect(screen.getAllByText("Deebo Samuel Sr.")).toHaveLength(1);
  });

  it("shows the next action offseason and the Premium upsell", () => {
    const week: ThisWeek = { mode: "next_action", week: null, rows: [], next_action: { headline: "Connect a league", why: "Link Sleeper.", cta_label: "Connect a league", route: "connect_league" } };
    render(<TodayModule data={data({ this_week: week, items: [], entitlement: { is_premium: false, visible_count: 0, hidden_count: 2 } })} leagueId="a" leagueName="L" now={THURSDAY} />);
    expect(screen.getByRole("link", { name: "Connect a league" })).toHaveAttribute("href", "/connect-league");
    expect(screen.getByText(/2 more moves available on Premium/)).toBeInTheDocument();
  });

  it("reserves the trade row's space on the deferred first pass", () => {
    const { container } = render(
      <TodayModule data={data({ trade_ideas_deferred: true, this_week: { ...WEEK, rows: WEEK.rows.slice(0, 2) } })} leagueId="a" leagueName="L" now={THURSDAY} />,
    );
    expect(container.querySelector("[data-fgl-this-week-trade-pending]")).not.toBeNull();
  });

  it("shows the empty state only when nothing is real", () => {
    render(<TodayModule data={data({ items: [], this_week: null })} leagueId="a" leagueName="L" now={THURSDAY} />);
    expect(screen.getByText("No urgent roster issues right now.")).toBeInTheDocument();
  });
});
