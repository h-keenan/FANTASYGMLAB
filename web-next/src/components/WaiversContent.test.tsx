import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { WaiversContent } from "./WaiversContent";
import { api } from "@/lib/api";
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

    expect(screen.getByText("Dynasty Overlords")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Waivers" })).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getAllByText("Test Free Agent").length).toBeGreaterThan(0);
    expect(screen.getByText("$8–$14")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Confidence: High" })).toBeInTheDocument();
  });

  it("preserves the exact waiver-claim disclosure", () => {
    render(<WaiversContent leagueName="Dynasty Overlords" data={BASE_RESPONSE} />);

    expect(screen.getByText("Place claims in Sleeper — we don't submit them.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /How Priority Adds rank/ }));
    expect(
      screen.getByText(
        /FantasyDesk does not submit waiver claims for you — place the claim in your Sleeper league once you've decided\./,
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

    expect(screen.getByText(/No primary need/)).toBeInTheDocument();
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

    expect(screen.getByText("Top Stash Candidates")).toBeInTheDocument();
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

    expect(screen.getByText(/No waiver option clearly helps/)).toBeInTheDocument();
  });

  // coridian_, 2026-10-18: "our backend can read current ffa balance!"
  // — Sleeper's real waiver_budget/waiver_budget_used was already
  // computed server-side but never surfaced as its own field.
  it("shows a Your FAAB tile when the backend reports a remaining balance", () => {
    const withFaab: WaiversResponse = { ...BASE_RESPONSE, faab_remaining: 94, faab_initial: 100 };
    render(<WaiversContent leagueName="Dynasty Overlords" data={withFaab} />);

    expect(screen.getByText("FAAB")).toBeInTheDocument();
    expect(screen.getByText("$94")).toBeInTheDocument();
  });

  it("shows the bid's why line on the top waiver target", () => {
    const withWhy: WaiversResponse = {
      ...BASE_RESPONSE,
      priority_adds: [
        priorityAdd({
          faab: {
            low_bid: 12,
            high_bid: 18,
            pct_low: 12,
            pct_high: 18,
            remaining: 100,
            dollars_known: true,
            label: "$12–$18 of $100 remaining",
            applicable: true,
            why: "3 teams need a RB and 2 of them have more FAAB than you.",
          },
        }),
      ],
    };
    render(<WaiversContent leagueName="Dynasty Overlords" data={withWhy} />);
    expect(screen.getByText("$12–$18")).toBeInTheDocument();
    expect(screen.getByText("3 teams need a RB and 2 of them have more FAAB than you.")).toBeInTheDocument();
  });

  it("never shows dollar bids in a non-FAAB league and handles a missing bid", () => {
    const rolling: WaiversResponse = {
      ...BASE_RESPONSE,
      waiver_mode: "rolling",
      faab_enabled: false,
      faab_remaining: null,
      priority_adds: [
        priorityAdd({
          faab: {
            low_bid: 0,
            high_bid: 0,
            pct_low: 0,
            pct_high: 0,
            remaining: null,
            dollars_known: false,
            label: "Rolling waivers — no FAAB bid",
            applicable: false,
            waiver_mode: "rolling",
            why: "Worth your waiver priority: he would start for you.",
          },
        }),
        priorityAdd({ player_id: "p2", name: "No Bid Player", faab: null }),
      ],
    };
    const { container } = render(<WaiversContent leagueName="Dynasty Overlords" data={rolling} />);
    expect(screen.getAllByText("Waiver claim").length).toBe(2);
    expect(screen.getByText("Rolling")).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/\$\d/);
    expect(container.textContent).not.toMatch(/0–0%/);
  });

  it("omits the FAAB balance when the backend has no balance to report", () => {
    render(<WaiversContent leagueName="Dynasty Overlords" data={BASE_RESPONSE} />);

    expect(screen.queryByText("$94")).not.toBeInTheDocument();
  });

  // Recommendation-compliance audit, Check 3 — CTA reachability: a GM Plan/
  // Dashboard waiver tile's CTA now carries ?playerId=, and this page must
  // actually surface/highlight that specific player, not just avoid
  // crashing when the param is present.
  describe("highlightPlayerId (GM Plan deep link)", () => {
    const withStash: WaiversResponse = {
      ...BASE_RESPONSE,
      stash_candidates: [player({ player_id: "stash1", name: "Stash Target" })],
    };

    it("marks no row as highlighted without a highlightPlayerId (current/before behavior)", () => {
      const { container } = render(<WaiversContent leagueName="Dynasty Overlords" data={withStash} />);
      expect(container.querySelector('[data-highlighted="true"]')).toBeNull();
    });

    it("highlights the specific free agent a GM Plan tile named, even outside Priority Adds", () => {
      const { container } = render(
        <WaiversContent leagueName="Dynasty Overlords" data={withStash} highlightPlayerId="stash1" />,
      );
      const highlighted = container.querySelector('[data-highlighted="true"]');
      expect(highlighted).not.toBeNull();
      expect(highlighted?.textContent).toContain("Stash Target");
    });

    it("highlights the Priority Add primary card when it is the named player", () => {
      const { container } = render(
        <WaiversContent leagueName="Dynasty Overlords" data={BASE_RESPONSE} highlightPlayerId="p1" />,
      );
      const highlighted = container.querySelector('[data-highlighted="true"]');
      expect(highlighted).not.toBeNull();
      expect(highlighted?.textContent).toContain("Test Free Agent");
    });

    it("surfaces a named free agent even when it would otherwise be cut from the visible preview list", () => {
      const manyAgents = Array.from({ length: 65 }, (_, i) => player({ player_id: `fa${i}`, name: `Agent ${i}` }));
      const targeted = player({ player_id: "deep1", name: "Deep Cut" });
      const withDeepTarget: WaiversResponse = { ...BASE_RESPONSE, players: [...manyAgents, targeted] };

      render(<WaiversContent leagueName="Dynasty Overlords" data={withDeepTarget} highlightPlayerId="deep1" />);

      expect(screen.getByText("Deep Cut")).toBeInTheDocument();
    });

    it("falls back gracefully (no crash, no highlight) when the playerId matches nothing on the board", () => {
      const { container } = render(
        <WaiversContent leagueName="Dynasty Overlords" data={BASE_RESPONSE} highlightPlayerId="does-not-exist" />,
      );
      expect(container.querySelector('[data-highlighted="true"]')).toBeNull();
      expect(screen.getAllByText("Test Free Agent").length).toBeGreaterThan(0);
    });
  });

  it("Explore tab shows the searchable free-agent list", () => {
    render(<WaiversContent leagueName="Dynasty Overlords" data={BASE_RESPONSE} />);
    expect(screen.queryByPlaceholderText("Search free agents")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "Explore" }));
    expect(screen.getByPlaceholderText("Search free agents")).toBeInTheDocument();
  });

  it("Watchlist tab lists GM Targets that are free agents", async () => {
    const spy = vi.spyOn(api, "getGmTargets").mockResolvedValue({
      ok: true,
      targets: [{ player_id: "fa1", source_surface: "x", created_at: null, untouchable: false }],
    } as Awaited<ReturnType<typeof api.getGmTargets>>);
    const data: WaiversResponse = {
      ...BASE_RESPONSE,
      players: [player({ player_id: "fa1", name: "Target Guy" }), player({ player_id: "fa2", name: "Other Guy" })],
    };
    render(<WaiversContent leagueName="Dynasty Overlords" data={data} leagueId="L1" />);
    fireEvent.click(screen.getByRole("tab", { name: "Watchlist" }));
    expect(await screen.findByText("Target Guy")).toBeInTheDocument();
    expect(screen.queryByText("Other Guy")).not.toBeInTheDocument();
    spy.mockRestore();
  });

  it("Explore lists free-agent defenders under DL/LB/DB only in IDP leagues", () => {
    const idp = [player({ player_id: "dl9", name: "Free Edge", position: "DL", score: 640, overall_rating: null })];
    const { unmount } = render(<WaiversContent leagueName="IDP" data={{ ...BASE_RESPONSE, idp_players: idp }} />);
    fireEvent.click(screen.getByRole("tab", { name: "Explore" }));
    expect(screen.queryByText("Free Edge")).not.toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "DL" } });
    expect(screen.getByText("Free Edge")).toBeInTheDocument();
    unmount();

    render(<WaiversContent leagueName="Std" data={BASE_RESPONSE} />);
    fireEvent.click(screen.getByRole("tab", { name: "Explore" }));
    expect(screen.queryByRole("option", { name: "DL" })).not.toBeInTheDocument();
  });
});
