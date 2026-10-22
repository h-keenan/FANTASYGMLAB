import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TradeFinderContent } from "./TradeFinderContent";
import { api } from "@/lib/api";
import type {
  DraftPickAsset,
  LineupPlayer,
  MyTeamResponse,
  TradeAsset,
  TradeFinderResponse,
  TradeIdea,
} from "@/lib/api";

/**
 * jsdom/testing-library substitute for live E2E (no Supabase/Sleeper
 * credentials in this environment) — verifies the real behaviors this page
 * adds on top of the shared TradeIdeaCardView (already covered by
 * TradeHubContent.test.tsx): the roster picker renders every roster player,
 * selecting one enables the Find button, searching calls
 * api.getTradeFinderIdeas with exactly the selected player_ids, and results
 * render via the same card Trade Hub uses.
 */

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      getTradeFinderIdeas: vi.fn(),
      getTeamStance: vi.fn(),
      getLeagueDraftPicks: vi.fn(),
    },
  };
});

function lineupPlayer(overrides: Partial<LineupPlayer>): LineupPlayer {
  return {
    player_id: "p1",
    name: "My Running Back",
    position: "RB",
    team: "SF",
    age: 25,
    status: "Active",
    injury_status: null,
    injury_label: "",
    ruled_out: false,
    tier: "starter",
    score: 2000,
    slot: "RB",
    suggested_starter: true,
    opportunity_label: null,
    overall_rating: 88,
    ...overrides,
  };
}

function asset(overrides: Partial<TradeAsset>): TradeAsset {
  return {
    asset_type: "player",
    player_id: "opp-wr",
    name: "Opp Wide Receiver",
    position: "WR",
    team: "KC",
    age: 24,
    score: 1800,
    tier: "starter",
    overall_rating: 82,
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
    trade_gain: 400,
    confidence_label: "High",
    market_realism_label: "Realistic",
    reasoning_tags: ["Need-Based"],
    package: {
      send: [asset({ asset_type: "player", player_id: "p1", name: "My Running Back", position: "RB" })],
      receive: [asset({})],
      value_edge: "+400",
      confidence: "High",
    },
    category: "",
    value_edge_band: "Favorable",
    impact_tag: "",
    landed_gm_target_player_ids: [],
    send_score: 1600,
    receive_score: 1800,
    ...overrides,
  };
}

function pick(overrides: Partial<DraftPickAsset>): DraftPickAsset {
  return {
    pick_id: "2027:1:1",
    label: "2027 Round 1",
    score: 4000,
    season: 2027,
    round: 1,
    original_roster_id: "1",
    owner_roster_id: "1",
    original_team_name: "Me",
    owner_team_name: "Me",
    pick_tier: "Mid 1st",
    projected_pick_range: "Mid 1st",
    ...overrides,
  };
}

function myTeam(overrides: Partial<MyTeamResponse>): MyTeamResponse {
  return {
    ok: true,
    starters: [lineupPlayer({})],
    bench: [lineupPlayer({ player_id: "p2", name: "Bench Guy", score: 500, overall_rating: 60 })],
    reason: "",
    ...overrides,
  };
}

describe("TradeFinderContent", () => {
  beforeEach(() => {
    // No Team Situation declared, by default — the same "retool" behavior
    // every test below already expects. The dedicated test further down
    // overrides this to assert a declared stance's real strategy flows
    // through to the search call instead.
    vi.mocked(api.getTeamStance).mockResolvedValue({ ok: true, stance: "" });
    vi.mocked(api.getLeagueDraftPicks).mockResolvedValue({ ok: true, picks: [], reason: "" });
  });

  it("renders every roster player (starters + bench) in the picker", () => {
    render(<TradeFinderContent leagueId="123" leagueName="Dynasty Overlords" myTeam={myTeam({})} />);

    expect(screen.getByText("My Running Back")).toBeInTheDocument();
    expect(screen.getByText("Bench Guy")).toBeInTheDocument();
  });

  it("disables Find Realistic Trades until a player is selected", () => {
    render(<TradeFinderContent leagueId="123" leagueName="Dynasty Overlords" myTeam={myTeam({})} />);

    const button = screen.getByRole("button", { name: /Find Realistic Trades/ });
    expect(button).toBeDisabled();

    fireEvent.click(screen.getByText("My Running Back"));
    expect(button).not.toBeDisabled();
  });

  it("searches with exactly the selected player_ids and renders results via the shared trade-idea card", async () => {
    const response: TradeFinderResponse = { ok: true, ideas: [idea({})], reason: "", is_premium: true, upsell: null };
    vi.mocked(api.getTradeFinderIdeas).mockResolvedValue(response);

    render(<TradeFinderContent leagueId="123" leagueName="Dynasty Overlords" myTeam={myTeam({})} />);

    fireEvent.click(screen.getByText("My Running Back"));
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Find Realistic Trades/ }));
    });

    expect(api.getTradeFinderIdeas).toHaveBeenCalledWith("123", ["p1"], "retool", "Dynasty", { pickIds: [], returnPicks: false });
    expect(screen.getByText("Rival GM")).toBeInTheDocument();
    expect(screen.getByText("Favorable")).toBeInTheDocument();
    expect(screen.getByText("Opp Wide Receiver")).toBeInTheDocument();
  });

  it("searches under the caller's declared Team Situation strategy, not a hardcoded default", async () => {
    // Recommendation-compliance audit finding: this used to always search
    // under "retool" regardless of what the user declared in Team
    // Situation. A declared "Competing" stance maps (team_stance.
    // team_strategy_for_stance) to the real engine key "contender" —
    // GET .../team-stance already returns that mapped value as `strategy`.
    vi.mocked(api.getTeamStance).mockResolvedValue({ ok: true, stance: "competing", strategy: "contender" });
    const response: TradeFinderResponse = { ok: true, ideas: [idea({})], reason: "", is_premium: true, upsell: null };
    vi.mocked(api.getTradeFinderIdeas).mockResolvedValue(response);

    render(<TradeFinderContent leagueId="123" leagueName="Dynasty Overlords" myTeam={myTeam({})} />);
    // Flush the mount-time GET .../team-stance fetch before interacting,
    // so `strategy` has already updated from its "retool" default.
    await act(async () => {});

    fireEvent.click(screen.getByText("My Running Back"));
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Find Realistic Trades/ }));
    });

    expect(api.getTradeFinderIdeas).toHaveBeenCalledWith("123", ["p1"], "contender", "Dynasty", { pickIds: [], returnPicks: false });
  });

  it("lists only the caller's own picks and searches with a picks-only selection plus Picks back", async () => {
    vi.mocked(api.getLeagueDraftPicks).mockResolvedValue({
      ok: true,
      reason: "",
      picks: [
        pick({ pick_id: "2027:1:1", label: "2027 Round 1", owner_roster_id: "1", round: 1 }),
        pick({ pick_id: "2027:2:4", label: "2027 Round 2 (Other Team)", owner_roster_id: "1", round: 2 }),
        pick({ pick_id: "2027:1:2", label: "2027 Round 1 Rival", owner_roster_id: "2", round: 1 }),
      ],
    });
    const pickIdea = idea({
      package: {
        send: [asset({ asset_type: "pick", player_id: undefined, label: "2027 Round 1", round: "1" })],
        receive: [asset({})],
        value_edge: "+100",
        confidence: "High",
      },
    });
    vi.mocked(api.getTradeFinderIdeas).mockResolvedValue({
      ok: true,
      ideas: [pickIdea],
      reason: "",
      is_premium: true,
      upsell: null,
    });

    render(
      <TradeFinderContent leagueId="123" leagueName="Dynasty Overlords" myTeam={myTeam({ roster_id: "1" })} />,
    );
    await act(async () => {});

    expect(api.getLeagueDraftPicks).toHaveBeenCalledWith("123", "Dynasty");
    expect(screen.getByText("2027 Round 2 (Other Team)")).toBeInTheDocument();
    expect(screen.queryByText("2027 Round 1 Rival")).not.toBeInTheDocument();

    const button = screen.getByRole("button", { name: /Find Realistic Trades/ });
    expect(button).toBeDisabled();
    fireEvent.click(screen.getByText("2027 Round 1"));
    expect(button).not.toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Picks back" }));

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Find Realistic Trades/ }));
    });

    expect(api.getTradeFinderIdeas).toHaveBeenCalledWith("123", [], "retool", "Dynasty", {
      pickIds: ["2027:1:1"],
      returnPicks: true,
    });
    expect(screen.getByText("Rival GM")).toBeInTheDocument();
  });

  it("caps the pick selection at the server's per-search limit", async () => {
    vi.mocked(api.getLeagueDraftPicks).mockResolvedValue({
      ok: true,
      reason: "",
      picks: [1, 2, 3, 4, 5].map((n) =>
        pick({ pick_id: `202${n}:1:1`, label: `Pick ${n}`, season: 2020 + n, owner_roster_id: "1" }),
      ),
    });

    render(
      <TradeFinderContent leagueId="123" leagueName="Dynasty Overlords" myTeam={myTeam({ roster_id: "1" })} />,
    );
    await act(async () => {});

    for (const n of [1, 2, 3, 4]) fireEvent.click(screen.getByText(`Pick ${n}`));
    const fifth = screen.getByText("Pick 5").closest("button");
    expect(fifth).toBeDisabled();
    expect(screen.getByRole("button", { name: /Find Realistic Trades \(4\)/ })).toBeInTheDocument();
  });

  it("shows a no-results message when the search returns an empty idea list", async () => {
    const response: TradeFinderResponse = { ok: true, ideas: [], reason: "", is_premium: true, upsell: null };
    vi.mocked(api.getTradeFinderIdeas).mockResolvedValue(response);

    render(<TradeFinderContent leagueId="123" leagueName="Dynasty Overlords" myTeam={myTeam({})} />);

    fireEvent.click(screen.getByText("My Running Back"));
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Find Realistic Trades/ }));
    });

    expect(screen.getByText(/No realistic trades found for this selection/)).toBeInTheDocument();
  });

  it("shows the premium upsell instead of the builder once a Free caller searches", async () => {
    const response: TradeFinderResponse = {
      ok: true,
      ideas: [],
      reason: "",
      is_premium: false,
      upsell: { title: "Build and search for a trade", body: "Upgrade to Premium to unlock it." },
    };
    vi.mocked(api.getTradeFinderIdeas).mockResolvedValue(response);

    render(<TradeFinderContent leagueId="123" leagueName="Dynasty Overlords" myTeam={myTeam({})} />);

    fireEvent.click(screen.getByText("My Running Back"));
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Find Realistic Trades/ }));
    });

    expect(screen.getByRole("heading", { name: "Build and search for a trade" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Find Realistic Trades/ })).not.toBeInTheDocument();
  });

  describe("Find trades deep link (initialPlayerId)", () => {
    it("pre-selects a roster player and runs the search once, under the declared strategy", async () => {
      vi.mocked(api.getTeamStance).mockResolvedValue({ ok: true, stance: "competing", strategy: "contender" });
      vi.mocked(api.getTradeFinderIdeas).mockClear();
      vi.mocked(api.getTradeFinderIdeas).mockResolvedValue({ ok: true, ideas: [idea({})], reason: "", is_premium: true, upsell: null });

      render(<TradeFinderContent leagueId="123" leagueName="Dynasty Overlords" myTeam={myTeam({})} initialPlayerId="p2" />);
      await act(async () => {});

      expect(api.getTradeFinderIdeas).toHaveBeenCalledTimes(1);
      expect(api.getTradeFinderIdeas).toHaveBeenCalledWith("123", ["p2"], "contender", "Dynasty", { pickIds: [], returnPicks: false });
      expect(screen.getByText("Bench Guy").closest("button")).toHaveAttribute("aria-pressed", "true");
      expect(screen.getByText("Rival GM")).toBeInTheDocument();
    });

    it("shows the Premium upsell for a Free caller, same as a manual search", async () => {
      vi.mocked(api.getTradeFinderIdeas).mockResolvedValue({
        ok: true,
        ideas: [],
        reason: "",
        is_premium: false,
        upsell: { title: "Build and search for a trade", body: "Upgrade to Premium to unlock it." },
      });

      render(<TradeFinderContent leagueId="123" leagueName="Dynasty Overlords" myTeam={myTeam({})} initialPlayerId="p1" />);
      await act(async () => {});

      expect(screen.getByRole("heading", { name: "Build and search for a trade" })).toBeInTheDocument();
    });

    it("ignores a player who isn't on this roster", async () => {
      vi.mocked(api.getTradeFinderIdeas).mockClear();

      render(<TradeFinderContent leagueId="123" leagueName="Dynasty Overlords" myTeam={myTeam({})} initialPlayerId="someone-else" />);
      await act(async () => {});

      expect(api.getTradeFinderIdeas).not.toHaveBeenCalled();
      expect(screen.getByRole("button", { name: /Find Realistic Trades/ })).toBeDisabled();
    });
  });

  it("shows the roster-not-ready message instead of a picker when `reason` is set", () => {
    render(
      <TradeFinderContent
        leagueId="123"
        leagueName="Dynasty Overlords"
        myTeam={myTeam({ starters: [], bench: [], reason: "empty_roster" })}
      />,
    );

    expect(screen.getByText(/Your roster in this league looks empty/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Find Realistic Trades/ })).not.toBeInTheDocument();
  });
});

describe("TradeFinderContent trade deadline", () => {
  it("shows the deadline-passed state up front once the league's deadline has passed", () => {
    vi.mocked(api.getTeamStance).mockResolvedValue({ ok: true, stance: "" });
    vi.mocked(api.getLeagueDraftPicks).mockResolvedValue({ ok: true, picks: [], reason: "" });
    render(
      <TradeFinderContent
        leagueId="123"
        leagueName="Dynasty Overlords"
        myTeam={myTeam({
          trade_window: {
            trade_deadline_week: 11,
            current_week: 12,
            trade_deadline_passed: true,
            message: "Trade deadline has passed; trades reopen after the season.",
          },
        })}
      />,
    );
    expect(screen.getByText("Trade deadline has passed; trades reopen after the season.")).toBeInTheDocument();
    expect(screen.queryByText(/Find Realistic Trades/)).not.toBeInTheDocument();
  });
});
