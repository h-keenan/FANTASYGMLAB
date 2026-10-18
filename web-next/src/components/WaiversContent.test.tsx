import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { WaiversContent } from "./WaiversContent";
import type { WaiverPlayer, WaiverPriorityAdd, WaiversResponse } from "@/lib/api";

function player(overrides: Partial<WaiverPlayer>): WaiverPlayer {
  return {
    player_id: "p1",
    name: "Test Free Agent",
    position: "RB",
    team: "SF",
    age: 24,
    status: "Active",
    injury_status: null,
    tier: "backup",
    opportunity_label: "Backup With Upside",
    score: 1200,
    position_rank: 3,
    overall_rank: 40,
    stale_free_agent: false,
    injury_replacement_fit: false,
    injury_replacement_note: "",
    sleeper_trending_add: false,
    sleeper_trending_add_count: null,
    sleeper_trending_add_rank: null,
    opponent: null,
    opponent_is_home: null,
    opponent_defense_tier: null,
    overall_rating: 68,
    ...overrides,
  };
}

function priorityAdd(overrides: Partial<WaiverPriorityAdd>): WaiverPriorityAdd {
  return {
    ...player({}),
    recommendation_label: "Add",
    recommendation_tone: "opportunity",
    faab: { low_bid: 8, high_bid: 14, pct_low: 8, pct_high: 14, remaining: 100, dollars_known: true, label: "$8–$14 of $100 remaining" },
    confidence_label: "High",
    confidence_reason: "Matches a real roster need on this roster.",
    ...overrides,
  };
}

const BASE_RESPONSE: WaiversResponse = {
  ok: true,
  reason: "",
  players: [player({})],
  priority_adds: [priorityAdd({})],
  needed_positions: ["RB", "QB"],
  available_count: 42,
  avg_wire_score: 650,
  injured_starters: 1,
  injury_positions: ["RB"],
  stash_candidates: [],
  watchlist_candidates: [],
  faab_targets: [],
  entitlement: { is_premium: true },
};

describe("WaiversContent", () => {
  it("renders the league name, stat tiles, and the top Priority Add with FAAB range and confidence", () => {
    render(<WaiversContent leagueName="Dynasty Overlords" data={BASE_RESPONSE} />);

    expect(screen.getByRole("heading", { name: "Dynasty Overlords" })).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getAllByText("Test Free Agent").length).toBeGreaterThan(0);
    expect(screen.getByText("$8–$14")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Confidence: High" })).toBeInTheDocument();
  });

  it("preserves the exact waiver-claim disclosure", () => {
    render(<WaiversContent leagueName="Dynasty Overlords" data={BASE_RESPONSE} />);

    expect(
      screen.getByText(
        "FantasyDesk does not submit waiver claims for you — place the claim in your Sleeper league once you've decided.",
      ),
    ).toBeInTheDocument();
  });

  it("shows the Current need framing from needed_positions", () => {
    render(<WaiversContent leagueName="Dynasty Overlords" data={BASE_RESPONSE} />);

    expect(screen.getByText(/Current need: RB \/ QB\./)).toBeInTheDocument();
  });

  it("falls back to the no-need framing when needed_positions is empty", () => {
    const noNeed: WaiversResponse = { ...BASE_RESPONSE, needed_positions: [] };
    render(<WaiversContent leagueName="Dynasty Overlords" data={noNeed} />);

    expect(screen.getByText(/No primary positional need/)).toBeInTheDocument();
  });

  it("shows the Premium upsell instead of the secondary board when not premium", () => {
    const free: WaiversResponse = { ...BASE_RESPONSE, entitlement: { is_premium: false } };
    render(<WaiversContent leagueName="Dynasty Overlords" data={free} />);

    expect(screen.getByText("Full waiver board and FAAB shortlist")).toBeInTheDocument();
  });

  it("shows the secondary board for Premium users when candidates exist", () => {
    const premium: WaiversResponse = {
      ...BASE_RESPONSE,
      stash_candidates: [player({ player_id: "stash1", name: "Stash Target" })],
    };
    render(<WaiversContent leagueName="Dynasty Overlords" data={premium} />);

    expect(screen.getByText("Stash Candidates")).toBeInTheDocument();
    expect(screen.getByText("Stash Target")).toBeInTheDocument();
  });

  it("shows the roster-not-ready message instead of the board when `reason` is set", () => {
    const notReady: WaiversResponse = { ...BASE_RESPONSE, reason: "empty_roster", players: [], priority_adds: [] };
    render(<WaiversContent leagueName="Dynasty Overlords" data={notReady} />);

    expect(screen.getByText(/there's nothing to weigh adds against yet/)).toBeInTheDocument();
  });

  it("shows the no-priority-adds fallback when the board is empty for a real reason-less roster", () => {
    const empty: WaiversResponse = { ...BASE_RESPONSE, priority_adds: [] };
    render(<WaiversContent leagueName="Dynasty Overlords" data={empty} />);

    expect(screen.getByText(/No waiver option materially improves/)).toBeInTheDocument();
  });

  // coridian_, 2026-10-18: "our backend can read current ffa balance!"
  // — Sleeper's real waiver_budget/waiver_budget_used was already
  // computed server-side but never surfaced as its own field.
  it("shows a Your FAAB tile when the backend reports a remaining balance", () => {
    const withFaab: WaiversResponse = { ...BASE_RESPONSE, faab_remaining: 94, faab_initial: 100 };
    render(<WaiversContent leagueName="Dynasty Overlords" data={withFaab} />);

    expect(screen.getByText("Your FAAB")).toBeInTheDocument();
    expect(screen.getByText("$94")).toBeInTheDocument();
  });

  it("omits the Your FAAB tile when the backend has no balance to report", () => {
    render(<WaiversContent leagueName="Dynasty Overlords" data={BASE_RESPONSE} />);

    expect(screen.queryByText("Your FAAB")).not.toBeInTheDocument();
  });
});
