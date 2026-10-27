import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TradeAnalyzerContent } from "./TradeAnalyzerContent";
import type { DraftPickAsset, MyRosterResponse, RankedPlayer, TeamProfile, TradeVerdict } from "@/lib/api";
import { api } from "@/lib/api";
import { resetShareBlobCache } from "@/lib/useShareImage";

/**
 * This is a jsdom/testing-library substitute for live E2E (no Supabase/
 * Sleeper credentials in this environment) — it directly verifies the three
 * properties the task flagged as fixed three times tonight in Streamlit:
 * the give/receive matchup never shrinks to fit (width-fill grid class is
 * literally present), there is exactly one value bar (never duplicated),
 * and Confidence/Risk render as their own distinct rows.
 */

const VERDICT: TradeVerdict = {
  band: "ACCEPT",
  ui_verdict: "ACCEPT",
  confidence: "High confidence",
  rationale: "The package improves your side enough to take as offered.",
  value_summary: "You win on asset value",
  roster_summary: "Your lineup gets stronger at WR.",
  strategy_summary: "Fits your retool timeline.",
  risk_summary: "Minimal injury risk on either side.",
  counter_guidance: "",
  fit_total: 5,
  value_delta: 650,
  tone: "accept",
  counter_action: null,
  alternate_packages: [
    {
      label: "Ask for a sweetener too",
      send_assets: [
        { asset_type: "player", player_id: "send-1", name: "My RB", position: "RB", team: "SF", score: 1000 },
      ],
      receive_assets: [
        { asset_type: "player", player_id: "receive-1", name: "Their WR", position: "WR", team: "KC", score: 1700 },
      ],
      band: "ACCEPT",
      ui_verdict: "ACCEPT",
      confidence: "High confidence",
      value_delta: 700,
    },
  ],
};

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      postTradeAnalyzer: vi.fn(),
      recordTradeShare: vi.fn(() => Promise.resolve({})),
    },
  };
});

const renderAnalyzerCardBlob = vi.fn();
vi.mock("@/lib/shareCard/clientRender", () => ({
  renderAnalyzerCardBlob: (...args: unknown[]) => renderAnalyzerCardBlob(...args),
}));

function player(overrides: Partial<RankedPlayer>): RankedPlayer {
  return {
    player_id: "p1",
    name: "Test Player",
    position: "WR",
    team: "SF",
    age: 24,
    status: "Active",
    injury_status: null,
    tier: "starter",
    score: 1500,
    overall_rank: 12,
    position_rank: 4,
    rank_unavailable_reason: null,
    opportunity_label: null,
    overall_rating: 72,
    ...overrides,
  };
}

const MY_ROSTER: MyRosterResponse = {
  ok: true,
  roster: { roster_id: "1", players: ["send-1"] },
  reason: "",
};

const ROSTERS = [
  { roster_id: "1", owner_id: "u1", players: ["send-1"] },
  { roster_id: "2", owner_id: "u2", players: ["receive-1"] },
];

const TEAM_PROFILES: Record<string, TeamProfile> = {
  "2": {
    team_name: "Rival Team",
    owner_name: "Rival Owner",
    username: "rival",
    avatar_id: "",
    avatar_url: "",
    roster_id: "2",
    owner_id: "u2",
  },
};

const RANKINGS: RankedPlayer[] = [
  player({ player_id: "send-1", name: "My RB", position: "RB" }),
  player({ player_id: "receive-1", name: "Their WR", position: "WR" }),
];

function pick(overrides: Partial<DraftPickAsset>): DraftPickAsset {
  return {
    pick_id: "2027:1:1",
    label: "2027 Round 1",
    score: 800,
    season: 2027,
    round: 1,
    original_roster_id: "1",
    owner_roster_id: "1",
    original_team_name: "My Team",
    owner_team_name: "My Team",
    pick_tier: null,
    projected_pick_range: null,
    ...overrides,
  };
}

function renderPage() {
  return render(
    <TradeAnalyzerContent
      leagueId="league-1"
      leagueName="Dynasty Overlords"
      myRoster={MY_ROSTER}
      rankings={RANKINGS}
      picks={[]}
      rosters={ROSTERS}
      teamProfiles={TEAM_PROFILES}
    />,
  );
}

describe("TradeAnalyzerContent", () => {
  it("shows the not-ready message instead of the builder when the roster can't be resolved", () => {
    render(
      <TradeAnalyzerContent
        leagueId="league-1"
        leagueName="Dynasty Overlords"
        myRoster={{ ok: true, roster: null, reason: "empty_roster" }}
        rankings={[]}
        picks={[]}
        rosters={[]}
        teamProfiles={{}}
      />,
    );

    expect(screen.getByText(/Your roster in this league looks empty/)).toBeInTheDocument();
  });

  it("renders the Trade Hub / Trade Finder / Trade Analyzer tri-tab switcher", () => {
    renderPage();
    expect(screen.getByRole("tab", { name: "Trade Hub" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Trade Finder" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Trade Analyzer", selected: true })).toBeInTheDocument();
  });

  it("adds a player from the search results into the active side's panel", () => {
    renderPage();

    // Default active side is "send"; the search pool is scoped to my own
    // roster, so only "My RB" (on roster "1") is a candidate.
    fireEvent.click(screen.getByText("My RB"));

    expect(screen.getByRole("button", { name: "Remove My RB" })).toBeInTheDocument();
  });

  it("analyzes a built package and renders the verdict with the width-fill grid, a single value bar, and confidence/risk rows", async () => {
    vi.mocked(api.postTradeAnalyzer).mockResolvedValue({ ok: true, verdict: VERDICT, reason: "" });
    renderPage();

    fireEvent.click(screen.getByText("My RB"));
    fireEvent.click(screen.getByRole("button", { name: /You receive/ }));
    fireEvent.click(screen.getByText("Their WR"));

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Analyze Trade" }));
    });

    expect(api.postTradeAnalyzer).toHaveBeenCalledWith(
      "league-1",
      expect.objectContaining({ sendPlayerIds: ["send-1"], receivePlayerIds: ["receive-1"] }),
    );

    expect(await screen.findByText("Reviewed package")).toBeInTheDocument();
    expect(screen.getAllByText("ACCEPT").length).toBeGreaterThan(0);

    // The exact bug fixed three times tonight: the give/receive matchup grid
    // must declare `minmax(0,1fr)` columns, never shrink-to-fit/max-content.
    const matchupGrid = document.querySelector('[class*="minmax(0,1fr)_1.5rem_minmax(0,1fr)"]');
    expect(matchupGrid).not.toBeNull();

    // Single value bar — never a second meter duplicating the same number.
    expect(document.querySelectorAll(".lean-bar-track").length).toBe(1);

    expect(screen.getByRole("img", { name: "Confidence: High confidence" })).toBeInTheDocument();
    expect(screen.getByText("Minimal injury risk on either side.")).toBeInTheDocument();
    expect(screen.getByText("Ask for a sweetener too")).toBeInTheDocument();
  });

  it("shows a lineup-hole warning and a direction-matched rationale heading (coridian_ 2026-10-27)", async () => {
    vi.mocked(api.postTradeAnalyzer).mockResolvedValue({
      ok: true,
      verdict: {
        ...VERDICT,
        band: "COUNTER",
        ui_verdict: "COUNTER",
        tone: "counter",
        confidence: "Moderate confidence",
        value_delta: -379,
        rationale: "Leaves you without a startable RB in Week 8. Falls short: it pays a raw-value premium.",
        rationale_label: "Why it needs changes",
        lineup_warnings: [
          {
            code: "no_startable_position",
            position: "RB",
            severity: "critical",
            headline: "Leaves you without a startable RB in Week 8",
            detail: "You have 1 startable RB now and 2 RB slots to fill.",
          },
        ],
      },
      reason: "",
    });
    renderPage();
    fireEvent.click(screen.getByText("My RB"));
    fireEvent.click(screen.getByRole("button", { name: /You receive/ }));
    fireEvent.click(screen.getByText("Their WR"));
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Analyze Trade" }));
    });

    const warnings = await screen.findByTestId("lineup-warnings");
    expect(warnings).toHaveTextContent("Leaves you without a startable RB in Week 8");
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("Why it needs changes")).toBeInTheDocument();
    expect(screen.queryByText("Why this works")).not.toBeInTheDocument();
  });

  it("shows the lineup model's points, the one trade score and the computed confidence", async () => {
    vi.mocked(api.postTradeAnalyzer).mockResolvedValue({
      ok: true,
      verdict: {
        ...VERDICT,
        band: "DECLINE",
        ui_verdict: "DECLINE",
        tone: "decline",
        confidence: "High confidence",
        confidence_pct: 93.4,
        value_delta: -379,
        trade_score: -1704,
        rationale_label: "Why it doesn't work",
        lineup_model: {
          trade_score: -1704,
          confidence_pct: 93.4,
          confidence_label: "High confidence",
          explanation:
            "You lose ~7.6 pts/week at RB for 10 weeks unless you pick up Waiver Runner (~6.5 ppg, worth ~65 pts); net -76 lineup pts over Weeks 8-17 (-6.0 this week).",
          posture: "retool",
          weights: { now: 1.15, future: 1 },
          weeks: { first: 8, last: 17, count: 10 },
          points: { ros_before: 992.1, ros_after: 916.2, ros_delta: -75.9, per_week_delta: -7.59, this_week_delta: -6, future_delta: -40 },
          worst_position: "RB",
          pickup: { player_id: "fa", name: "Waiver Runner", position: "RB", expected_ppg: 6.5, points_recovered_ros: 65 },
          waiver_pool_used: true,
          uncertainty: { sigma_points: 30, estimate_sigma_points: 20 },
          win_now_delta: -2500,
          future_delta: 800,
        },
      },
      reason: "",
    });
    renderPage();
    fireEvent.click(screen.getByText("My RB"));
    fireEvent.click(screen.getByRole("button", { name: /You receive/ }));
    fireEvent.click(screen.getByText("Their WR"));
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Analyze Trade" }));
    });

    const block = await screen.findByTestId("lineup-model");
    expect(block).toHaveTextContent("-76 lineup pts over Weeks 8-17 (-6 this week)");
    expect(block).toHaveTextContent("pick up Waiver Runner");
    expect(block).toHaveTextContent("Trade score");
    expect(screen.getByText("High confidence (93%)")).toBeInTheDocument();
  });

  describe("Players' Add to Trade quick-add (quickAddPlayerId)", () => {
    it("pre-populates You Receive with a player owned by another team, and selects that team", () => {
      render(
        <TradeAnalyzerContent
          leagueId="league-1"
          leagueName="Dynasty Overlords"
          myRoster={MY_ROSTER}
          rankings={RANKINGS}
          picks={[]}
          rosters={ROSTERS}
          teamProfiles={TEAM_PROFILES}
          quickAddPlayerId="receive-1"
        />,
      );

      expect(screen.getByRole("button", { name: "Remove Their WR" })).toBeInTheDocument();
      // Then the builder flips to the still-empty "You send" side and
      // focuses the search, so the next tap picks the counter-asset.
      expect(screen.getByText("You send")).toHaveStyle({ color: "var(--color-accent)" });
      expect(screen.getByPlaceholderText("Search your roster")).toHaveFocus();
      // The owning team stays selected for when the user returns to
      // "You receive" ("Rival Team · Rival Owner" is its pill label).
      fireEvent.click(screen.getByText("You receive"));
      expect(screen.getByPlaceholderText(/Search Rival Team/)).toBeInTheDocument();
    });

    it("pre-populates You Send (not Receive) for a player already on the user's own roster", () => {
      render(
        <TradeAnalyzerContent
          leagueId="league-1"
          leagueName="Dynasty Overlords"
          myRoster={MY_ROSTER}
          rankings={RANKINGS}
          picks={[]}
          rosters={ROSTERS}
          teamProfiles={TEAM_PROFILES}
          quickAddPlayerId="send-1"
        />,
      );

      expect(screen.getByRole("button", { name: "Remove My RB" })).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Remove Their WR" })).not.toBeInTheDocument();
      // Flipped to the empty "You receive" side, searching every other team.
      expect(screen.getByText("You receive")).toHaveStyle({ color: "var(--color-accent)" });
      expect(screen.getByPlaceholderText("Search players to receive")).toHaveFocus();
    });

    it("fails open to the plain builder when the player id is missing/stale or on no roster in this league", () => {
      render(
        <TradeAnalyzerContent
          leagueId="league-1"
          leagueName="Dynasty Overlords"
          myRoster={MY_ROSTER}
          rankings={RANKINGS}
          picks={[]}
          rosters={ROSTERS}
          teamProfiles={TEAM_PROFILES}
          quickAddPlayerId="not-a-real-player"
        />,
      );

      expect(screen.getByText("Queue send and receive assets, then Analyze.")).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: /Remove/ })).not.toBeInTheDocument();
    });
  });

  describe("Build the counter for a pick-type counter_action (Revision 21)", () => {
    it("renders the button and removes the exact pick from You send when the server suggests removing it", async () => {
      const sendPick = pick({ pick_id: "2027:1:1", label: "2027 Round 1" });
      const verdictWithPickCounter: TradeVerdict = {
        ...VERDICT,
        ui_verdict: "COUNTER",
        tone: "counter",
        counter_guidance: "Remove 2027 Round 1 from your outgoing side.",
        counter_action: {
          action: "remove_from_send",
          player_id: sendPick.pick_id,
          asset_type: "pick",
          label: "2027 Round 1",
        },
        alternate_packages: [],
      };
      vi.mocked(api.postTradeAnalyzer).mockResolvedValue({ ok: true, verdict: verdictWithPickCounter, reason: "" });

      render(
        <TradeAnalyzerContent
          leagueId="league-1"
          leagueName="Dynasty Overlords"
          myRoster={MY_ROSTER}
          rankings={RANKINGS}
          picks={[sendPick]}
          rosters={ROSTERS}
          teamProfiles={TEAM_PROFILES}
        />,
      );

      // Default active side is "send" — switch asset type to Picks and add it.
      fireEvent.click(screen.getByRole("button", { name: "Picks" }));
      fireEvent.click(screen.getByText("2027 Round 1"));
      expect(screen.getByRole("button", { name: "Remove 2027 Round 1" })).toBeInTheDocument();

      await act(async () => {
        fireEvent.click(screen.getByRole("button", { name: "Analyze Trade" }));
      });

      const counterButton = await screen.findByRole("button", { name: "Build the counter →" });
      fireEvent.click(counterButton);

      // The pick-type action used to be silently unsupported (the button
      // only rendered/applied for asset_type "player") — this is the fix:
      // the exact pick the server named is gone from You send afterward.
      expect(screen.queryByRole("button", { name: "Remove 2027 Round 1" })).not.toBeInTheDocument();
    });
  });

  describe("Share (client-side template card)", () => {
    afterEach(() => {
      resetShareBlobCache();
      vi.unstubAllGlobals();
      vi.restoreAllMocks();
      renderAnalyzerCardBlob.mockReset();
      vi.mocked(api.recordTradeShare).mockClear();
      Reflect.deleteProperty(navigator, "share");
      Reflect.deleteProperty(navigator, "canShare");
      Reflect.deleteProperty(navigator, "clipboard");
    });

    async function analyze() {
      vi.mocked(api.postTradeAnalyzer).mockResolvedValue({ ok: true, verdict: VERDICT, reason: "" });
      renderPage();
      fireEvent.click(screen.getByText("My RB"));
      fireEvent.click(screen.getByRole("button", { name: /You receive/ }));
      fireEvent.click(screen.getByText(/Rival Team/));
      fireEvent.click(screen.getByText("Their WR"));
      await act(async () => {
        fireEvent.click(screen.getByRole("button", { name: "Analyze Trade" }));
      });
      await screen.findByText("Reviewed package");
    }

    async function analyzeAndShare() {
      renderAnalyzerCardBlob.mockResolvedValue(new Blob(["png"], { type: "image/png" }));
      const fetchSpy = vi.fn();
      vi.stubGlobal("fetch", fetchSpy);
      await analyze();
      const analyzeCalls = vi.mocked(api.postTradeAnalyzer).mock.calls.length;
      // The PNG is pre-rendered once the result is on screen.
      await waitFor(() => expect(renderAnalyzerCardBlob).toHaveBeenCalled());
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 0));
      });
      await act(async () => {
        fireEvent.click(screen.getByRole("button", { name: "Share" }));
      });
      // The card is a template of the on-screen analysis: no second analyze
      // (no quota use), and no request to any share-card server route.
      expect(vi.mocked(api.postTradeAnalyzer).mock.calls.length).toBe(analyzeCalls);
      const urls = fetchSpy.mock.calls.map((c) => String(c[0]));
      expect(urls.filter((u) => u.includes("share-card") || u.includes("trade-analyzer"))).toEqual([]);
    }

    it("draws the card from the on-screen data and shares the PNG file through the OS sheet", async () => {
      const share = vi.fn().mockResolvedValue(undefined);
      Object.assign(navigator, { share, canShare: () => true });
      await analyzeAndShare();
      expect(renderAnalyzerCardBlob).toHaveBeenCalledTimes(1);
      const params = renderAnalyzerCardBlob.mock.calls[0][0];
      expect(params.partnerName).toBe("Rival Team");
      expect(params.verdict).toEqual(expect.objectContaining({ band: "ACCEPT", value_delta: 650 }));
      expect(params.sendAssets.map((a: { name: string }) => a.name)).toEqual(["My RB"]);
      expect(params.receiveAssets.map((a: { name: string }) => a.name)).toEqual(["Their WR"]);
      const arg = share.mock.calls[0][0];
      expect(arg.files[0]).toBeInstanceOf(File);
      expect(arg.files[0].type).toBe("image/png");
      expect(api.recordTradeShare).toHaveBeenCalledTimes(1);
    });

    it("copies the image to the clipboard when the browser cannot share files", async () => {
      const write = vi.fn().mockResolvedValue(undefined);
      Object.assign(navigator, { clipboard: { write } });
      vi.stubGlobal("ClipboardItem", class { constructor(public items: unknown) {} });
      await analyzeAndShare();
      expect(write).toHaveBeenCalledTimes(1);
      expect(await screen.findByText("Copied!")).toBeInTheDocument();
      expect(api.recordTradeShare).toHaveBeenCalledTimes(1);
    });

    it("downloads the PNG when neither share nor clipboard-image is available", async () => {
      URL.createObjectURL = vi.fn(() => "blob:x");
      URL.revokeObjectURL = vi.fn();
      const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
      await analyzeAndShare();
      expect(click).toHaveBeenCalledTimes(1);
      expect(api.recordTradeShare).toHaveBeenCalledTimes(1);
    });

    it("falls back to sharing text when the card cannot be drawn", async () => {
      const share = vi.fn().mockResolvedValue(undefined);
      Object.assign(navigator, { share, canShare: () => true });
      renderAnalyzerCardBlob.mockRejectedValue(new Error("no canvas"));
      await analyze();
      await act(async () => {
        fireEvent.click(screen.getByRole("button", { name: "Share" }));
      });
      expect((await screen.findByRole("status")).textContent).toMatch(/Couldn't build the image on this device.*Sharing text instead/);
      await waitFor(() => expect(share).toHaveBeenCalled());
      expect(share.mock.calls[0][0].files).toBeUndefined();
      expect(share.mock.calls[0][0].text).toContain("ACCEPT");
    });
  });
});
