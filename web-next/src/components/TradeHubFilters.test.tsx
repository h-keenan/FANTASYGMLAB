import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { TradeHubResponse, TradeIdea } from "@/lib/api";
import { TradeHubContent } from "@/components/TradeHubContent";
import { TradeHubFilters, TradeHubSkeleton } from "@/components/TradeHubFilters";
import { TradesTabBar } from "@/components/TradesTabBar";

vi.mock("@/components/ManagerTendenciesCard", () => ({ ManagerTendenciesCard: () => null }));
vi.mock("@/components/PlayerRow", () => ({
  PlayerIdentity: ({ name }: { name: string }) => <span>{name}</span>,
}));

function idea(name: string, impact: string, sendPos: string, category = ""): TradeIdea {
  return {
    partner_team_name: name,
    rationale: "Short reason. More detail follows.",
    trade_gain: 100,
    confidence_label: "High",
    market_realism_label: "Realistic",
    reasoning_tags: [],
    package: {
      send: [{ asset_type: "player", player_id: `s-${name}`, name: `Send ${name}`, position: sendPos, score: 100 }],
      receive: [{ asset_type: "player", player_id: `r-${name}`, name: `Get ${name}`, position: "WR", score: 200 }],
      value_edge: "+100",
      confidence: "High",
    },
    category,
    value_edge_band: "Fair",
    impact_tag: impact,
    landed_gm_target_player_ids: [],
    send_score: 100,
    receive_score: 200,
    recommendation_id: `id-${name}`,
  };
}

const DATA: TradeHubResponse = {
  ok: true,
  reason: "",
  ideas: [
    idea("Alpha", "buy_low", "RB", "Headline Recommendation"),
    idea("Bravo", "sell_high", "TE", "Age Optimization"),
    idea("Charlie", "", "QB"),
  ],
  entitlement: null,
  team_strategy: "retool",
};

describe("TradesTabBar", () => {
  it("renders the three trade tabs and marks the active one", () => {
    render(<TradesTabBar leagueId="1" leagueName="L" active="trade_finder" />);
    expect(screen.getAllByRole("tab").map((tab) => tab.textContent)).toEqual(["Trade Hub", "Trade Finder", "Trade Analyzer"]);
    expect(screen.getByRole("tab", { name: "Trade Finder" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "Trade Hub" })).toHaveAttribute("href", "/trade-hub/1?name=L");
  });
});

describe("TradeHubFilters", () => {
  it("shows All with a count and only the impact chips the board has", () => {
    render(<TradeHubFilters ideas={DATA.ideas} filter={{ impact: null, position: null }} onChange={() => {}} />);
    expect(screen.getByRole("button", { name: "All (3)" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Buy Low (1)" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sell High (1)" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /High Impact/ })).not.toBeInTheDocument();
    expect(screen.queryByText(/My Trades|Leagues/)).not.toBeInTheDocument();
  });
});

describe("TradeHubContent filtering and states", () => {
  it("tags cards from engine category and impact tag, and filters by chip and position", () => {
    render(<TradeHubContent leagueId="1" leagueName="L" data={DATA} />);
    expect(screen.getByText("Headline Recommendation")).toBeInTheDocument();
    expect(screen.getByText("Age Optimization")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Share Trade" })).toHaveLength(3);

    fireEvent.click(screen.getByRole("button", { name: "Buy Low (1)" }));
    expect(screen.getByText("Alpha")).toBeInTheDocument();
    expect(screen.queryByText("Bravo")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "All (3)" }));
    fireEvent.change(screen.getByLabelText("Positions"), { target: { value: "QB" } });
    expect(screen.getByText("Charlie")).toBeInTheDocument();
    expect(screen.queryByText("Alpha")).not.toBeInTheDocument();
  });

  it("offers a way back when filters match nothing", () => {
    render(<TradeHubContent leagueId="1" leagueName="L" data={DATA} />);
    fireEvent.click(screen.getByRole("button", { name: "Sell High (1)" }));
    fireEvent.change(screen.getByLabelText("Positions"), { target: { value: "QB" } });
    expect(screen.getByText("No ideas match these filters")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Show all" }));
    expect(screen.getByText("Alpha")).toBeInTheDocument();
  });

  it("shows an empty state with a next step when there are no ideas", () => {
    render(<TradeHubContent leagueId="1" leagueName="L" data={{ ...DATA, ideas: [] }} />);
    expect(screen.getByText("No trade ideas right now")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open Trade Finder/ })).toHaveAttribute("href", "/trade-finder/1?name=L");
  });

  it("keeps the tab strip in the deadline-passed state", () => {
    render(<TradeHubContent leagueId="1" leagueName="L" data={{ ...DATA, ideas: [], reason: "trade_deadline_passed" }} />);
    expect(screen.getByRole("tablist")).toBeInTheDocument();
  });

  it("renders a skeleton that reserves height", () => {
    render(<TradeHubSkeleton />);
    expect(screen.getByTestId("trade-hub-skeleton")).toHaveAttribute("aria-busy", "true");
  });
});
