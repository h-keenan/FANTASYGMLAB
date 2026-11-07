import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { WaiversContent } from "./WaiversContent";
import { api } from "@/lib/api";
import type { DropSuggestion, NeedsModel, WaiverPlayer, WaiverPriorityAdd, WaiversResponse } from "@/lib/api";

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

const DROP_EFFECT = { lineup_points_ros: 4.2, lineup_points_per_week: 0.5, this_week: 0.4, value_delta: 1263, score: 1500, weeks: 9 };

const DROP_SUGGESTION: DropSuggestion = {
  status: "ok",
  add: { player_id: "p1", name: "Test Free Agent", position: "RB" },
  roster: { active_limit: 22, active_count: 22, open_spots: 0, is_full: true, reserve_slots: 3, reserve_used: 1, taxi_slots: 0, taxi_used: 0 },
  drop_required: true,
  drop: {
    player_id: "d1", name: "Dead Weight", position: "WR", team: "NYJ", age: 31, status: "Active", injury_status: "", value: 300,
    start_share: 0, usage_flag: null, reasons: ["never starts in your best lineup", "low trade/dynasty value"], effect: DROP_EFFECT, action: "drop",
  },
  alternatives: [
    {
      player_id: "d2", name: "Bench Guy", position: "TE", team: "DEN", age: 29, status: "Active", injury_status: "", value: 500,
      start_share: 0, usage_flag: null, reasons: ["never starts in your best lineup"], effect: { ...DROP_EFFECT, lineup_points_ros: 0, value_delta: 700 }, action: "drop",
    },
  ],
  no_good_drop: false,
  why: "Add Test Free Agent, drop Dead Weight.",
};

const NEEDS_MODEL: NeedsModel = {
  model_version: "roster-value-v1",
  needed_positions: ["WR"],
  biggest_need: "WR",
  weakest_position: "WR",
  no_need: false,
  headline: "Biggest need: WR — your WR3 is 8th of 12.",
  league_size: 12,
  basis: "in_season",
  dynasty: true,
  model_status: { degraded: false, reasons: [] },
  positions: [
    {
      position: "WR", tier: "primary", score: 1.6, starters: 3,
      weakest_slot: { slot: "WR3", rank: 8, of: 12, pct: 0.64, ppg: 9.1 }, slot_ranks: [],
      upgrade: { ppw: 1.2, ros: 10.8, name: "Pat Wire", player_id: "fa", ppg: 10.3 },
      healthy_count: 4, required_depth: 5, depth_short: 1, injured_starters: [], aging_starters: [], future_gap: false,
      reasons: ["WR3 is 8th of 12 in the league"],
    },
  ],
};

describe("WaiversContent", () => {
  it("shows one bigger-upgrade chip with the lineup gain on the flagged top add, and none otherwise", () => {
    const flagged = priorityAdd({ name: "Big Upgrade", bigger_upgrade: true, lineup_ppw: 1.84 });
    const { unmount } = render(
      <WaiversContent leagueName="L" data={{ ...BASE_RESPONSE, priority_adds: [flagged] }} />,
    );
    expect(screen.getAllByText("Bigger than your need: +1.8 pts/wk")).toHaveLength(1);
    unmount();
    render(<WaiversContent leagueName="L" data={BASE_RESPONSE} />);
    expect(screen.queryByText(/Bigger than your need/)).toBeNull();
  });

  it("renders the league name, stat tiles, and the top Priority Add with FAAB range and confidence", () => {
    render(<WaiversContent leagueName="Dynasty Overlords" data={BASE_RESPONSE} />);

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

  it("links a Sleeper league straight to Sleeper so the claim is one tap away, and omits it for imported leagues", () => {
    const { unmount } = render(<WaiversContent leagueId="1312141796616187904" leagueName="L" data={BASE_RESPONSE} />);
    expect(screen.getByRole("link", { name: /Open your league in Sleeper/ })).toHaveAttribute(
      "href",
      "https://sleeper.com/leagues/1312141796616187904",
    );
    unmount();
    render(<WaiversContent leagueId="espn:42654852:2026" leagueName="L" data={BASE_RESPONSE} />);
    expect(screen.queryByRole("link", { name: /Open your league in Sleeper/ })).toBeNull();
  });

  it("shows the Current need framing from needed_positions", () => {
    render(<WaiversContent leagueName="Dynasty Overlords" data={BASE_RESPONSE} />);

    expect(screen.getByText(/Current need: RB \/ QB\./)).toBeInTheDocument();
  });

  it("says so (never a bare 'None') when the need model failed and there is no legacy need", () => {
    const noNeed: WaiversResponse = {
      ...BASE_RESPONSE,
      needed_positions: [],
      needs_model: null,
      model_status: { degraded: true, reasons: [{ code: "need_model_failed", message: "Needs could not be fully modeled." }] },
    };
    render(<WaiversContent leagueName="Dynasty Overlords" data={noNeed} />);

    expect(screen.getByTestId("needs-headline")).toHaveTextContent(/could not be fully modeled/);
    expect(screen.getByTestId("limited-data-note")).toHaveTextContent(/Limited data/);
    expect(screen.queryByText("None")).not.toBeInTheDocument();
  });

  it("surfaces the model's weakest position with the numbers behind it", () => {
    const withModel: WaiversResponse = { ...BASE_RESPONSE, needs_model: NEEDS_MODEL };
    render(<WaiversContent leagueName="Dynasty Overlords" data={withModel} />);

    expect(screen.getByTestId("needs-headline")).toHaveTextContent("Biggest need: WR — your WR3 is 8th of 12.");
    fireEvent.click(screen.getByRole("button", { name: /How we read your needs/ }));
    expect(screen.getByTestId("needs-breakdown")).toHaveTextContent(/WR3 · 8th of 12/);
    expect(screen.getByTestId("needs-breakdown")).toHaveTextContent(/Pat Wire \+1\.2 pts\/wk/);
  });

  it("says 'Covered' only when the model says no position needs help", () => {
    const covered: WaiversResponse = {
      ...BASE_RESPONSE,
      needs_model: { ...NEEDS_MODEL, biggest_need: null, no_need: true, needed_positions: [], headline: "No urgent need — your weakest spot is TE1 (3rd of 12)." },
    };
    render(<WaiversContent leagueName="Dynasty Overlords" data={covered} />);

    expect(screen.getByText("Covered")).toBeInTheDocument();
    expect(screen.getByTestId("needs-headline")).toHaveTextContent(/^No urgent need/);
  });

  it("shows 'Add X, drop Y' with the reasons, net effect and an alternative on the top card", () => {
    const data: WaiversResponse = {
      ...BASE_RESPONSE,
      priority_adds: [priorityAdd({ drop_suggestion: DROP_SUGGESTION })],
    };
    render(<WaiversContent leagueName="Dynasty Overlords" data={data} />);

    const box = screen.getByTestId("suggested-drop");
    expect(box).toHaveTextContent("Add Test Free Agent, drop Dead Weight");
    // 15 chars is over the narrow-tile threshold: shown as "F. Lastname", full name kept in title.
    expect(screen.getByTestId("swap-add")).toHaveTextContent("T. Free Agent");
    expect(screen.getByTestId("swap-add").querySelector('[title="Test Free Agent"]')).not.toBeNull();
    expect(screen.getByTestId("swap-drop")).toHaveTextContent("Dead Weight");
    expect(screen.getByTestId("swap-reasons")).toHaveTextContent("never starts in your best lineup");
    expect(screen.getByTestId("swap-effect")).toHaveTextContent("+4 pts / 9 wks");
    expect(screen.getByTestId("swap-effect")).toHaveTextContent("Value +1,263");
    expect(screen.getByTestId("swap-effect")).toHaveAttribute("aria-label", expect.stringContaining("+4 lineup pts over 9 weeks"));
    expect(screen.getByTestId("swap-alternatives")).toHaveTextContent("Bench Guy");
    fireEvent.click(screen.getByRole("button", { name: /Why this cut/ }));
    expect(screen.getByTestId("swap-why")).toHaveTextContent("+4 lineup pts over 9 weeks");
    fireEvent.click(screen.getByRole("button", { name: /Cut Bench Guy instead/ }));
    expect(screen.getByTestId("swap-drop")).toHaveTextContent("Bench Guy");
    expect(screen.getByTestId("swap-alternatives")).toHaveTextContent("Dead Weight");
  });

  it("collapses repeated drops to one line on the list rows, details one tap away", () => {
    const data: WaiversResponse = {
      ...BASE_RESPONSE,
      priority_adds: [
        priorityAdd({ drop_suggestion: DROP_SUGGESTION }),
        priorityAdd({ player_id: "p2", name: "Second Add", drop_suggestion: { ...DROP_SUGGESTION, add: { ...DROP_SUGGESTION.add, name: "Second Add" } } }),
      ],
    };
    render(<WaiversContent leagueName="Dynasty Overlords" data={data} />);

    const compact = screen.getByTestId("suggested-drop-compact");
    expect(compact).toHaveTextContent("Drop");
    expect(compact).toHaveTextContent("Dead Weight");
    expect(compact).toHaveTextContent("WR");
    expect(screen.queryByTestId("suggested-drop-details")).not.toBeInTheDocument();
    fireEvent.click(within(compact).getByRole("button", { name: /Why/ }));
    expect(screen.getByTestId("suggested-drop-details")).toHaveTextContent("never starts in your best lineup");
    expect(screen.getByTestId("suggested-drop-details")).toHaveTextContent("Add Second Add, drop Dead Weight");
  });

  it("lists the same cut the cards name, with the adds it is the cut for", () => {
    const data: WaiversResponse = {
      ...BASE_RESPONSE,
      priority_adds: [priorityAdd({ drop_suggestion: DROP_SUGGESTION })],
      droppable_players: {
        players: [{ ...DROP_SUGGESTION.drop!, named_for: ["Test Free Agent"] }],
        total: 1, protected_count: 3, candidates_checked: 5, locked_count: 0,
      },
    };
    render(<WaiversContent leagueName="Dynasty Overlords" data={data} />);

    const section = screen.getByTestId("droppable-players");
    expect(section).toHaveTextContent("Dead Weight");
    expect(section).toHaveTextContent("The cut when you add Test Free Agent");
    expect(section).not.toHaveTextContent(/Nobody on your roster is a free cut/);
  });

  it("says 'No good drop' honestly and names the cheapest cut", () => {
    const data: WaiversResponse = {
      ...BASE_RESPONSE,
      priority_adds: [
        priorityAdd({
          drop_suggestion: { ...DROP_SUGGESTION, drop: null, alternatives: [], no_good_drop: true, cheapest: DROP_SUGGESTION.drop, why: "No good drop for Test Free Agent." },
        }),
      ],
    };
    render(<WaiversContent leagueName="Dynasty Overlords" data={data} />);

    const box = screen.getByTestId("suggested-drop");
    expect(box).toHaveTextContent("No good drop");
    expect(box).toHaveTextContent("Cheapest cut: Dead Weight");
  });

  it("lists 'Players you could drop' and the Pro count for Free", () => {
    const data: WaiversResponse = {
      ...BASE_RESPONSE,
      droppable_players: { players: [DROP_SUGGESTION.drop!], total: 3, protected_count: 12, candidates_checked: 8, locked_count: 2 },
    };
    render(<WaiversContent leagueName="Dynasty Overlords" data={data} />);

    const section = screen.getByTestId("droppable-players");
    expect(section).toHaveTextContent("Dead Weight");
    expect(section).toHaveTextContent("+2 more with Pro");
  });

  it("shows the Pro upsell instead of the secondary board when not premium", () => {
    const free: WaiversResponse = { ...BASE_RESPONSE, entitlement: { is_premium: false } };
    render(<WaiversContent leagueName="Dynasty Overlords" data={free} />);

    expect(screen.getByText("Full waiver board and FAAB shortlist")).toBeInTheDocument();
  });

  it("shows the secondary board for Pro users when candidates exist", () => {
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

  it("shows the display-only usage flag chip and explanation on the top waiver target, and nothing when absent", () => {
    const flagged: WaiversResponse = {
      ...BASE_RESPONSE,
      priority_adds: [
        priorityAdd({
          usage_flag: {
            key: "role_expanding",
            label: "Role expanding",
            tone: "positive",
            explanation: "His role is growing: snap share is 70% over the last 4 games vs 53% before (+17 pts).",
          },
          usage_flag_status: "ok",
        }),
      ],
    };
    const { unmount } = render(<WaiversContent leagueName="Dynasty Overlords" data={flagged} />);
    expect(screen.getByTestId("waiver-usage-flag")).toHaveTextContent("Role expanding");
    expect(screen.getByText(/snap share is 70% over the last 4 games/)).toBeInTheDocument();
    unmount();
    render(<WaiversContent leagueName="Dynasty Overlords" data={BASE_RESPONSE} />);
    expect(screen.queryByTestId("waiver-usage-flag")).not.toBeInTheDocument();
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
