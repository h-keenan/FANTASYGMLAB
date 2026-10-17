import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { GmPlanContent } from "./GmPlanContent";
import type { GmPlanResponse, GmPlanTradeItem, TradeAsset } from "@/lib/api";

function asset(overrides: Partial<TradeAsset>): TradeAsset {
  return {
    asset_type: "player",
    player_id: "p1",
    name: "Test Player",
    position: "RB",
    team: "SF",
    age: 25,
    score: 2000,
    overall_rating: 88,
    ...overrides,
  };
}

function tradeItem(overrides: Partial<GmPlanTradeItem>): GmPlanTradeItem {
  return {
    partner_team_name: "Rival GM",
    my_player: "My Running Back",
    their_player: "Opp Wide Receiver",
    my_player_id: "my-rb",
    their_player_id: "opp-wr",
    their_player_injury_display: "",
    rationale: "Fits your declared rebuild.",
    trade_confidence_label: "Strong",
    priority: 1,
    send_assets: [asset({ player_id: "my-rb", name: "My Running Back" })],
    receive_assets: [asset({ player_id: "opp-wr", name: "Opp Wide Receiver", position: "WR" })],
    trade_gain: 237,
    source: "modules.trade_ideas / modules.trade_hub_engine.generate_trade_idea_records_cached",
    ...overrides,
  };
}

const BASE_RESPONSE: GmPlanResponse = {
  ok: true,
  quiet: false,
  reason: "",
  is_premium: true,
  upsell: null,
  season_phase: "trade_deadline_approach",
  season_phase_label: "Trade Deadline Approaching",
  team_stance: "rebuilding",
  team_stance_label: "Rebuilding",
  headline: "The trade market is most active right now.",
  focus_areas: [
    {
      key: "standing",
      title: "Where You Stand",
      status: "signal_found",
      watch_for: "",
      items: [
        { label: "Roster Power", rank: 3, total_teams: 12, tied: false, source: "x" },
        { label: "Bench Depth", rank: 11, total_teams: 12, tied: false, source: "x", relative_weak_spot: true },
        { label: "Record", wins: 6, losses: 3, ties: 0, source: "x" },
      ],
    },
    {
      key: "trade_opportunities",
      title: "Trade Opportunities",
      framing: "Prioritize offers that add youth and future draft capital.",
      status: "signal_found",
      watch_for: "",
      items: [tradeItem({})],
    },
    {
      key: "roster_construction",
      title: "Roster Construction",
      status: "signal_found",
      watch_for: "",
      items: [
        {
          label: "Injury Exposure",
          health_flag: "Major Starter Absence",
          injured_starters: 1,
          injury_need_positions: ["TE"],
          injured_players: [
            {
              asset_type: "player",
              player_id: "7",
              name: "My Player 7",
              position: "TE",
              team: "KC",
              injury_status: "Out",
              player_tier: "Core",
            },
          ],
          summary: "My Player 7 (TE, KC) - Out",
          source: "modules.trade_analyzer_fit.roster_injury_context",
        },
      ],
    },
  ],
};

describe("GmPlanContent", () => {
  it("renders the hero phase/stance badges, headline, and league name", () => {
    render(<GmPlanContent leagueName="Dynasty Overlords" data={BASE_RESPONSE} />);

    expect(screen.getByRole("heading", { name: "Dynasty Overlords" })).toBeInTheDocument();
    expect(screen.getByText("Trade Deadline Approaching")).toBeInTheDocument();
    expect(screen.getByText("Rebuilding")).toBeInTheDocument();
    expect(screen.getByText("The trade market is most active right now.")).toBeInTheDocument();
  });

  it("links to Team Situation, labeled by whether a stance is already declared", () => {
    render(<GmPlanContent leagueId="league-1" leagueName="Dynasty Overlords" data={BASE_RESPONSE} />);

    expect(screen.getByRole("link", { name: /Change your Team Situation/ })).toHaveAttribute(
      "href",
      "/team-situation/league-1?name=Dynasty%20Overlords",
    );

    const undeclared: GmPlanResponse = { ...BASE_RESPONSE, team_stance: "", team_stance_label: "" };
    render(<GmPlanContent leagueId="league-1" leagueName="Dynasty Overlords" data={undeclared} />);
    expect(screen.getByRole("link", { name: /Declare your Team Situation/ })).toBeInTheDocument();
  });

  it("omits the Team Situation link when no leagueId is passed", () => {
    render(<GmPlanContent leagueName="Dynasty Overlords" data={BASE_RESPONSE} />);
    expect(screen.queryByRole("link", { name: /Team Situation/ })).not.toBeInTheDocument();
  });

  it("renders Where You Stand facts including a flagged weak spot", () => {
    render(<GmPlanContent leagueName="Dynasty Overlords" data={BASE_RESPONSE} />);

    expect(screen.getByText("Roster Power: 3 of 12")).toBeInTheDocument();
    expect(screen.getByText("Bench Depth: 11 of 12")).toBeInTheDocument();
    expect(screen.getByText("Relative weak spot in this league.")).toBeInTheDocument();
    expect(screen.getByText("Record: 6-3")).toBeInTheDocument();
  });

  it("renders a trade opportunity's give/get player identity and value delta", () => {
    render(<GmPlanContent leagueName="Dynasty Overlords" data={BASE_RESPONSE} />);

    expect(screen.getByText("Rival GM")).toBeInTheDocument();
    expect(screen.getByText("My Running Back")).toBeInTheDocument();
    expect(screen.getByText("Opp Wide Receiver")).toBeInTheDocument();
    expect(screen.getByText("+237")).toBeInTheDocument();
    // Circular OVR gauge renders the real rating for both sides.
    expect(screen.getAllByText("88").length).toBeGreaterThan(0);
  });

  it("falls back to plain give/get text when a trade idea has no asset detail", () => {
    const textOnly: GmPlanResponse = {
      ...BASE_RESPONSE,
      focus_areas: BASE_RESPONSE.focus_areas.map((area) =>
        area.key === "trade_opportunities"
          ? { ...area, items: [tradeItem({ send_assets: [], receive_assets: [], trade_gain: null })] }
          : area,
      ),
    };
    render(<GmPlanContent leagueName="Dynasty Overlords" data={textOnly} />);

    expect(screen.getByText("My Running Back → Opp Wide Receiver")).toBeInTheDocument();
  });

  it("renders the roster injury-exposure fact with real player identity", () => {
    render(<GmPlanContent leagueName="Dynasty Overlords" data={BASE_RESPONSE} />);

    expect(screen.getByText("Major Starter Absence: TE")).toBeInTheDocument();
    expect(screen.getByText("My Player 7")).toBeInTheDocument();
    expect(screen.getByText("Out")).toBeInTheDocument();
  });

  it("shows an honest no-signal message instead of a fabricated recommendation", () => {
    const noSignal: GmPlanResponse = {
      ...BASE_RESPONSE,
      focus_areas: BASE_RESPONSE.focus_areas.map((area) =>
        area.key === "trade_opportunities"
          ? { ...area, status: "no_signal", items: [], watch_for: "No specific trade opportunities surfaced this week." }
          : area,
      ),
    };
    render(<GmPlanContent leagueName="Dynasty Overlords" data={noSignal} />);

    expect(screen.getByText("No specific trade opportunities surfaced this week.")).toBeInTheDocument();
  });

  it("shows the link-account message instead of an empty plan when `reason` is set", () => {
    const notReady: GmPlanResponse = {
      ok: true,
      quiet: true,
      reason: "no_sleeper_username_linked",
      focus_areas: [],
      is_premium: true,
      upsell: null,
    };
    render(<GmPlanContent leagueName="Dynasty Overlords" data={notReady} />);

    expect(screen.getByText("Link your Sleeper account to see a GM Plan for this league.")).toBeInTheDocument();
  });

  it("shows a quiet message when there are no focus areas at all for a reason-less response", () => {
    const quiet: GmPlanResponse = { ok: true, quiet: true, reason: "", focus_areas: [], is_premium: true, upsell: null };
    render(<GmPlanContent leagueName="Dynasty Overlords" data={quiet} />);

    expect(screen.getByText(/We don't have enough to build a GM Plan/)).toBeInTheDocument();
  });

  it("shows the premium upsell instead of a plan for a Free caller", () => {
    const locked: GmPlanResponse = {
      ok: true,
      quiet: true,
      reason: "",
      focus_areas: [],
      is_premium: false,
      upsell: { title: "Your season-arc roadmap", body: "Upgrade to Premium to unlock it." },
    };
    render(<GmPlanContent leagueName="Dynasty Overlords" data={locked} />);

    expect(screen.getByRole("heading", { name: "Your season-arc roadmap" })).toBeInTheDocument();
    expect(screen.queryByText(/We don't have enough to build a GM Plan/)).not.toBeInTheDocument();
  });
});
