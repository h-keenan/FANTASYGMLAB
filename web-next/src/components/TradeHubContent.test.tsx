import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TradeHubContent } from "./TradeHubContent";
import type { TradeAsset, TradeHubResponse, TradeIdea } from "@/lib/api";

function asset(overrides: Partial<TradeAsset>): TradeAsset {
  return {
    asset_type: "player",
    player_id: "p1",
    name: "Test Player",
    position: "RB",
    team: "SF",
    age: 25,
    score: 2000,
    tier: "starter",
    overall_rating: 88,
    ...overrides,
  };
}

function idea(overrides: Partial<TradeIdea>): TradeIdea {
  return {
    partner_team_name: "Rival GM",
    partner_team_avatar_url: null,
    partner_team_archetype_label: "Rebuilding",
    partner_trade_tendency: "Neutral",
    rationale: "Clear value upgrade at a position of need.",
    trade_gain: 800,
    confidence_label: "High",
    market_realism_label: "Realistic",
    reasoning_tags: ["Need-Based"],
    package: {
      send: [asset({ player_id: "my-rb", name: "My Running Back" })],
      receive: [asset({ player_id: "opp-wr", name: "Opp Wide Receiver", position: "WR" })],
      value_edge: "+800",
      confidence: "High",
    },
    category: "Headline Recommendation",
    value_edge_band: "Favorable",
    impact_tag: "high_impact",
    landed_gm_target_player_ids: [],
    send_score: 1200,
    receive_score: 2000,
    ...overrides,
  };
}

const RESPONSE: TradeHubResponse = {
  ok: true,
  reason: "",
  ideas: [idea({})],
  entitlement: { is_premium: false, approved_count: 1, visible_count: 1, hidden_count: 0, free_limit: 2 },
  team_strategy: "retool",
};

describe("TradeHubContent", () => {
  it("renders a trade idea card with partner, fairness pill, value edge, and give/get assets", () => {
    render(<TradeHubContent leagueId="123" leagueName="Dynasty Overlords" data={RESPONSE} />);

    expect(screen.getByRole("heading", { name: "Dynasty Overlords" })).toBeInTheDocument();
    expect(screen.getByText("Rival GM")).toBeInTheDocument();
    expect(screen.getByText("Favorable")).toBeInTheDocument();
    expect(screen.getByText("+800")).toBeInTheDocument();
    expect(screen.getByText("My Running Back")).toBeInTheDocument();
    expect(screen.getByText("Opp Wide Receiver")).toBeInTheDocument();
    // Circular OVR gauge renders the real rating.
    expect(screen.getAllByText("88").length).toBeGreaterThan(0);
  });

  it("shows the low-confidence note on the card face without opening details", () => {
    const lowConfidence: TradeHubResponse = { ...RESPONSE, ideas: [idea({ confidence_label: "Low" })] };
    render(<TradeHubContent leagueId="123" leagueName="Dynasty Overlords" data={lowConfidence} />);

    expect(screen.getByText("More dependent on partner preference and market fit.")).toBeInTheDocument();
    expect(screen.queryByText("Why this works")).not.toBeInTheDocument();
  });

  it("reveals rationale and confidence/realism rings only after Review package is clicked", () => {
    render(<TradeHubContent leagueId="123" leagueName="Dynasty Overlords" data={RESPONSE} />);

    expect(screen.queryByText("Why this works")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Review package/ }));
    expect(screen.getByText("Why this works")).toBeInTheDocument();
    expect(screen.getByText(/Confidence · High/)).toBeInTheDocument();
    expect(screen.getByText(/Realism · Realistic/)).toBeInTheDocument();
  });

  it("shows the Premium upsell banner when ideas are hidden", () => {
    const gated: TradeHubResponse = {
      ...RESPONSE,
      entitlement: { is_premium: false, approved_count: 5, visible_count: 2, hidden_count: 3, free_limit: 2 },
    };
    render(<TradeHubContent leagueId="123" leagueName="Dynasty Overlords" data={gated} />);

    expect(screen.getByText("3 more trade ideas available on Premium.")).toBeInTheDocument();
  });

  // Logic/valuation audit, 2026-10-18: Trade Hub applies a team-strategy
  // age-curve adjustment to player value that Waivers/Dashboard/PQV's
  // plain valuation pipeline doesn't — nothing in the UI explained why the
  // same player could show a different number across tabs.
  it("names the strategy these values were generated under", () => {
    const contender: TradeHubResponse = { ...RESPONSE, team_strategy: "fringe_contender" };
    render(<TradeHubContent leagueId="123" leagueName="Dynasty Overlords" data={contender} />);

    expect(screen.getByText("Fringe Contender")).toBeInTheDocument();
  });

  // coridian_, screenshot: "there's no explanation of what retool means...
  // people's natural inclination when they don't know what something is
  // on a phone is probably to tap it."
  it("reveals a plain-language explanation of the strategy on tap", () => {
    render(<TradeHubContent leagueId="123" leagueName="Dynasty Overlords" data={RESPONSE} />);

    expect(screen.queryByText(/middle ground/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /What does this mean\?/ }));
    expect(screen.getByText(/middle ground/)).toBeInTheDocument();
  });

  it("shows the roster-not-ready message instead of an empty board when `reason` is set", () => {
    const notReady: TradeHubResponse = { ok: true, reason: "empty_roster", ideas: [], entitlement: null, team_strategy: "" };
    render(<TradeHubContent leagueId="123" leagueName="Dynasty Overlords" data={notReady} />);

    expect(screen.getByText(/Your roster in this league looks empty/)).toBeInTheDocument();
  });

  it("shows a no-ideas message when the board is empty for a real reason-less roster", () => {
    const empty: TradeHubResponse = { ok: true, reason: "", ideas: [], entitlement: null, team_strategy: "retool" };
    render(<TradeHubContent leagueId="123" leagueName="Dynasty Overlords" data={empty} />);

    expect(screen.getByText(/No trade ideas right now/)).toBeInTheDocument();
  });

  // Recommendation-compliance audit, Check 3 — CTA reachability: a GM Plan/
  // Dashboard trade tile's CTA now carries ?playerId= (the headline idea's
  // receive-side player), and this page must actually surface/highlight
  // the one idea that's about, not just avoid crashing on the param.
  describe("highlightPlayerId (GM Plan deep link)", () => {
    const twoIdeas: TradeHubResponse = {
      ...RESPONSE,
      ideas: [
        idea({ partner_team_name: "Rival GM", package: { ...idea({}).package, receive: [asset({ player_id: "opp-wr", name: "Opp Wide Receiver", position: "WR" })] } }),
        idea({
          partner_team_name: "Other GM",
          rationale: "A completely different idea.",
          package: {
            send: [asset({ player_id: "my-te", name: "My Tight End", position: "TE" })],
            receive: [asset({ player_id: "their-qb", name: "Their Quarterback", position: "QB" })],
            value_edge: "+300",
            confidence: "Medium",
          },
        }),
      ],
    };

    it("leaves every idea collapsed and unmarked without a highlightPlayerId (current/before behavior)", () => {
      const { container } = render(<TradeHubContent leagueId="123" leagueName="Dynasty Overlords" data={twoIdeas} />);
      expect(container.querySelector('[data-highlighted="true"]')).toBeNull();
      expect(screen.queryByText("A completely different idea.")).not.toBeInTheDocument();
    });

    it("highlights and auto-expands only the idea naming the given player id", () => {
      const { container } = render(
        <TradeHubContent leagueId="123" leagueName="Dynasty Overlords" data={twoIdeas} highlightPlayerId="their-qb" />,
      );

      const highlighted = container.querySelectorAll('[data-highlighted="true"]');
      expect(highlighted).toHaveLength(1);
      expect(highlighted[0].textContent).toContain("Other GM");
      // Auto-expanded: its rationale shows without clicking "Review package".
      expect(screen.getByText("A completely different idea.")).toBeInTheDocument();
      // The non-matching idea stays collapsed.
      expect(screen.queryByText("Clear value upgrade at a position of need.")).not.toBeInTheDocument();
    });

    it("matches a send-side (give-away) player id too, not just the receive side", () => {
      const { container } = render(
        <TradeHubContent leagueId="123" leagueName="Dynasty Overlords" data={twoIdeas} highlightPlayerId="my-te" />,
      );
      const highlighted = container.querySelectorAll('[data-highlighted="true"]');
      expect(highlighted).toHaveLength(1);
      expect(highlighted[0].textContent).toContain("Other GM");
    });

    it("falls back gracefully (no crash, nothing highlighted) when the playerId matches no idea", () => {
      const { container } = render(
        <TradeHubContent leagueId="123" leagueName="Dynasty Overlords" data={twoIdeas} highlightPlayerId="does-not-exist" />,
      );
      expect(container.querySelector('[data-highlighted="true"]')).toBeNull();
      expect(screen.getByText("Rival GM")).toBeInTheDocument();
      expect(screen.getByText("Other GM")).toBeInTheDocument();
    });
  });
});

describe("TradeHubContent trade deadline", () => {
  it("shows the deadline-passed state instead of a board after the trade deadline", () => {
    const passed: TradeHubResponse = { ...RESPONSE, ideas: [], reason: "trade_deadline_passed" };
    render(<TradeHubContent leagueId="123" leagueName="Dynasty Overlords" data={passed} />);
    expect(screen.getByText("Trade deadline has passed; trades reopen after the season.")).toBeInTheDocument();
  });
});
