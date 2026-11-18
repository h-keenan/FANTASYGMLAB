import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { GmPlanContent } from "./GmPlanContent";
import type {
  GmPlanResponse,
  GmPlanTradeItem,
  GmTarget,
  LineupPlayer,
  MyTeamResponse,
  RankedPlayer,
  TeamStanceResponse,
  TradeAsset,
} from "@/lib/api";
import { api } from "@/lib/api";
import { trackFeatureUse } from "@/lib/analytics";

/** Modules are collapsed with a real summary; open every one (nested too) to assert on the bodies. */
function expandAll() {
  for (let pass = 0; pass < 3; pass += 1) {
    for (const b of document.querySelectorAll('button[aria-expanded="false"][aria-label$=". Expand"]')) fireEvent.click(b);
  }
}

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

vi.mock("@/lib/analytics", () => ({
  trackFeatureUse: vi.fn(),
  trackUse: vi.fn(),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      setTeamStance: vi.fn().mockResolvedValue({ ok: true, stance: "competing" }),
      addGmTarget: vi.fn().mockResolvedValue({ ok: true, reason: "" }),
      setGmTargetUntouchable: vi.fn().mockResolvedValue({ ok: true, reason: "" }),
      removeGmTarget: vi.fn().mockResolvedValue({ ok: true, reason: "" }),
    },
  };
});

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

function lineupPlayer(overrides: Partial<LineupPlayer>): LineupPlayer {
  return {
    player_id: "p1",
    name: "Test Player",
    position: "WR",
    team: "SF",
    age: 24,
    status: "Active",
    injury_status: null,
    injury_label: "",
    ruled_out: false,
    tier: "starter",
    score: 1500,
    slot: "WR1",
    suggested_starter: true,
    opportunity_label: null,
    overall_rating: 72,
    ...overrides,
  };
}

function gmTarget(overrides: Partial<GmTarget>): GmTarget {
  return {
    player_id: "p1",
    source_surface: "team_stance",
    created_at: "2026-10-01T00:00:00Z",
    untouchable: false,
    ...overrides,
  };
}

function rankedPlayer(overrides: Partial<RankedPlayer>): RankedPlayer {
  return {
    player_id: "p1",
    name: "Test Target",
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
    opportunity_label: "Lead Receiver",
    overall_rating: 72,
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

const STANCE: TeamStanceResponse = { ok: true, stance: "rebuilding", strategy: "rebuild" };
const MY_TEAM: MyTeamResponse = {
  ok: true,
  starters: [lineupPlayer({})],
  bench: [lineupPlayer({ player_id: "p2", name: "Bench Guy", position: "RB" })],
  reason: "",
};

describe("GmPlanContent", () => {
  it("renders the league name and the numbered action steps (a generic trade step without a declared stance)", () => {
    render(<GmPlanContent leagueName="Dynasty Overlords" data={BASE_RESPONSE} />);

    expect(screen.getByRole("heading", { name: "GM Plan" })).toBeInTheDocument();
    expect(screen.getByTestId("plan-step-trades")).toHaveTextContent("Review your trade ideas");
  });

  it("renders Where You Stand facts including a flagged weak spot", () => {
    render(<GmPlanContent initialTab="trades" leagueName="Dynasty Overlords" data={BASE_RESPONSE} />);

    expect(screen.getByText("Roster Power: 3 of 12")).toBeInTheDocument();
    expect(screen.getByText("Bench Depth: 11 of 12")).toBeInTheDocument();
    expect(screen.getByText("Relative weak spot in this league.")).toBeInTheDocument();
    expect(screen.getByText("Record: 6-3")).toBeInTheDocument();
  });

  it("renders a trade opportunity's give/get player identity and value delta", () => {
    render(<GmPlanContent leagueName="Dynasty Overlords" data={BASE_RESPONSE} />);
    fireEvent.click(screen.getByTestId("plan-trade-row").querySelector("button")!);

    expect(screen.getAllByText("Rival GM").length).toBeGreaterThan(0);
    expect(screen.getByText("My Running Back")).toBeInTheDocument();
    expect(screen.getByText("Opp Wide Receiver")).toBeInTheDocument();
    expect(screen.getByText("You gain +237")).toBeInTheDocument();
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
    const row = screen.getByTestId("plan-trade-row");
    expect(row).toHaveTextContent("Rival GM");
    expect(row).not.toHaveTextContent("You gain");
  });

  it("renders the roster injury-exposure fact with real player identity", () => {
    render(<GmPlanContent initialTab="trades" leagueName="Dynasty Overlords" data={BASE_RESPONSE} />);

    expect(screen.getByText("Major Starter Absence: TE")).toBeInTheDocument();
    expect(screen.getByText("My Player 7")).toBeInTheDocument();
    expect(screen.getByTestId("player-chip-out")).toBeInTheDocument();
  });

  it("renders Team Outlook facts as compact rows that open on tap to show why", () => {
    const withOutlook: GmPlanResponse = {
      ...BASE_RESPONSE,
      focus_areas: [
        ...BASE_RESPONSE.focus_areas,
        {
          key: "team_outlook",
          title: "Team Outlook",
          framing: "Your ages, needs, picks and the league's trade partners, read together.",
          status: "signal_found",
          watch_for: "",
          items: [
            {
              outlook_topic: "age",
              label: "Age",
              headline: "Aging core: A. Cook near the cliff",
              why: ["1 on your roster is past the age cliff for their position: A. Cook (RB, 30)", "Your core averages 28.4 years vs the league's 26.5 (1.9 older)"],
              players: [{ player_id: "1", name: "Aaron Cook", position: "RB", team: "DET" }],
              tone: "muted",
            },
          ],
        },
      ],
    };
    render(<GmPlanContent initialTab="trades" leagueName="Dynasty Overlords" data={withOutlook} />);
    expandAll();
    const row = screen.getByTestId("plan-outlook-row");
    expect(row).toHaveTextContent("Aging core: A. Cook near the cliff");
    expect(screen.queryByText(/Your core averages 28.4/)).toBeNull();
    fireEvent.click(row.querySelector("button")!);
    expect(row.querySelector("button")).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText(/Your core averages 28.4/)).toBeInTheDocument();
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
    render(<GmPlanContent initialTab="trades" leagueName="Dynasty Overlords" data={noSignal} />);
    expandAll();

    expect(screen.getAllByText("No specific trade opportunities surfaced this week.").length).toBeGreaterThan(0);
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

    expect(screen.getByText("Not enough to build a GM Plan yet.")).toBeInTheDocument();
  });

  it("shows the premium upsell instead of a plan for a Free caller", () => {
    const locked: GmPlanResponse = {
      ok: true,
      quiet: true,
      reason: "",
      focus_areas: [],
      is_premium: false,
      upsell: { title: "Your season-arc roadmap", body: "Upgrade to Pro to unlock it." },
    };
    render(<GmPlanContent leagueName="Dynasty Overlords" data={locked} />);

    expect(screen.getByRole("heading", { name: "Your season-arc roadmap" })).toBeInTheDocument();
    expect(screen.queryByText("Not enough to build a GM Plan yet.")).not.toBeInTheDocument();
    // A real regression this PR fixes: PremiumUpsellCard renders its own
    // <main> by default, and this component already has its own — nesting
    // one inside the other is invalid HTML. `bare` must be passed here.
    expect(screen.getAllByRole("main")).toHaveLength(1);
  });

  // Revision 20 (2026-10-18): Team Situation + Watchlist merged in.
  describe("Team Situation section", () => {
    it("renders the declared stance option when teamStance is passed", () => {
      render(
        <GmPlanContent
          leagueId="league-1"
          leagueName="Dynasty Overlords"
          data={BASE_RESPONSE}
          teamStance={STANCE}
          myTeam={MY_TEAM}
          targets={[]}
          rankings={{ ok: true, players: [] }}
        />,
      );
      expandAll();

      expect(screen.getByRole("tab", { name: /^Rebuilding/, selected: true })).toBeInTheDocument();
      expect(screen.getByText("Prioritize youth and future draft capital")).toBeInTheDocument();
    });

    it("calls setTeamStance when a different stance is picked", () => {
      render(
        <GmPlanContent
          leagueId="league-1"
          leagueName="Dynasty Overlords"
          data={BASE_RESPONSE}
          teamStance={STANCE}
          myTeam={MY_TEAM}
          targets={[]}
          rankings={{ ok: true, players: [] }}
        />,
      );
      expandAll();

      fireEvent.click(screen.getByRole("tab", { name: /^Competing/ }));

      expect(api.setTeamStance).toHaveBeenCalledWith("league-1", "competing");
    });

    it("omits the section entirely when no teamStance is passed", () => {
      render(<GmPlanContent leagueName="Dynasty Overlords" data={BASE_RESPONSE} />);
      expect(screen.queryByText("Team Situation")).not.toBeInTheDocument();
    });
  });

  describe("Protected Players section", () => {
    it("lists roster players and groups an already-untouchable one as protected", () => {
      render(
        <GmPlanContent
          initialTab="core"
          leagueId="league-1"
          leagueName="Dynasty Overlords"
          data={BASE_RESPONSE}
          teamStance={STANCE}
          myTeam={MY_TEAM}
          targets={[gmTarget({ untouchable: true })]}
          rankings={{ ok: true, players: [] }}
        />,
      );

      fireEvent.click(screen.getByText(/more players? on your roster/));
      expect(screen.getByText("Test Player")).toBeInTheDocument();
      expect(screen.getByText("Bench Guy")).toBeInTheDocument();
      expect(screen.getByText("Rest of Roster")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Protected" })).toBeInTheDocument();
    });

    it("adds a GM Target then marks it untouchable when protecting a player not yet tracked", async () => {
      render(
        <GmPlanContent
          initialTab="core"
          leagueId="league-1"
          leagueName="Dynasty Overlords"
          data={BASE_RESPONSE}
          teamStance={STANCE}
          myTeam={MY_TEAM}
          targets={[]}
          rankings={{ ok: true, players: [] }}
        />,
      );

      fireEvent.click(screen.getByText(/more players? on your roster/));
      fireEvent.click(screen.getAllByRole("button", { name: "Protect" })[0]);

      expect(api.addGmTarget).toHaveBeenCalledWith("league-1", "p1", "team_stance");
      await screen.findByRole("button", { name: "Protected" });
      expect(api.setGmTargetUntouchable).toHaveBeenCalledWith("league-1", "p1", true);
      // Audit finding, 2026-10-20: gm_target_added (already in TRACKED_EVENTS,
      // already labeled on the Founder Analytics dashboard) had no caller
      // anywhere in web-next -- this is the real "save a GM Target" action.
      expect(trackFeatureUse).toHaveBeenCalledWith("gm_target_added", { leagueId: "league-1", dedupe: false });
    });

    it("does not fire gm_target_added when the add itself fails", async () => {
      vi.mocked(api.addGmTarget).mockResolvedValueOnce({ ok: false, reason: "not_available" });
      render(
        <GmPlanContent
          initialTab="core"
          leagueId="league-1"
          leagueName="Dynasty Overlords"
          data={BASE_RESPONSE}
          teamStance={STANCE}
          myTeam={MY_TEAM}
          targets={[]}
          rankings={{ ok: true, players: [] }}
        />,
      );

      fireEvent.click(screen.getByText(/more players? on your roster/));
      fireEvent.click(screen.getAllByRole("button", { name: "Protect" })[0]);

      // Reverted back to "Protect" (not "Protected") once the failed add settles.
      await screen.findAllByRole("button", { name: "Protect" });
      expect(screen.queryByRole("button", { name: "Protected" })).not.toBeInTheDocument();
      expect(trackFeatureUse).not.toHaveBeenCalledWith("gm_target_added", expect.anything());
    });

    it("shows a no-roster message when the league has no roster players", () => {
      render(
        <GmPlanContent
          initialTab="core"
          leagueId="league-1"
          leagueName="Dynasty Overlords"
          data={BASE_RESPONSE}
          teamStance={STANCE}
          myTeam={{ ok: true, starters: [], bench: [], reason: "empty_roster" }}
          targets={[]}
          rankings={{ ok: true, players: [] }}
        />,
      );

      expect(screen.getByText("No roster players found for this league.")).toBeInTheDocument();
    });

    it("omits the section entirely when no myTeam is passed", () => {
      render(<GmPlanContent leagueName="Dynasty Overlords" data={BASE_RESPONSE} />);
      expect(screen.queryByText("Protected Players")).not.toBeInTheDocument();
    });
  });

  describe("Watching section", () => {
    it("shows only non-untouchable targets (Protected Players already covers untouchable ones)", () => {
      render(
        <GmPlanContent
          initialTab="watching"
          leagueId="league-1"
          leagueName="Dynasty Overlords"
          data={BASE_RESPONSE}
          teamStance={STANCE}
          myTeam={MY_TEAM}
          targets={[
            gmTarget({ player_id: "p1", untouchable: true, source_surface: "player_quick_view" }),
            gmTarget({ player_id: "p9", untouchable: false, source_surface: "player_quick_view" }),
          ]}
          rankings={{
            ok: true,
            players: [rankedPlayer({ player_id: "p1", name: "Protected Player" }), rankedPlayer({ player_id: "p9", name: "Watched Player" })],
          }}
        />,
      );

      expect(screen.getByText("Watched Player")).toBeInTheDocument();
      expect(screen.queryByText("Protected Player")).not.toBeInTheDocument();
    });

    it("links each watched target to Player Compare and shows its origin", () => {
      render(
        <GmPlanContent
          initialTab="watching"
          leagueId="league-1"
          leagueName="Dynasty Overlords"
          data={BASE_RESPONSE}
          teamStance={STANCE}
          myTeam={MY_TEAM}
          targets={[gmTarget({ player_id: "p9", source_surface: "player_quick_view" })]}
          rankings={{ ok: true, players: [rankedPlayer({ player_id: "p9", name: "Watched Player" })] }}
        />,
      );

      expect(screen.getByRole("link", { name: "Compare" })).toHaveAttribute(
        "href",
        "/player-compare/league-1?a=p9&name=Dynasty%20Overlords",
      );
      expect(screen.getByText(/Added from Player Quick View/)).toBeInTheDocument();
    });

    describe("removing a target (instant, with an Undo toast)", () => {
      const renderWatching = () =>
        render(
          <GmPlanContent
            initialTab="watching"
            leagueId="league-1"
            leagueName="Dynasty Overlords"
            data={BASE_RESPONSE}
            teamStance={STANCE}
            myTeam={MY_TEAM}
            targets={[gmTarget({ player_id: "p9" })]}
            rankings={{ ok: true, players: [rankedPlayer({ player_id: "p9", name: "Watched Player" })] }}
          />,
        );

      afterEach(() => {
        vi.useRealTimers();
      });

      it("removes the row at once, shows Undo, and only calls removeGmTarget when the toast expires", () => {
        vi.useFakeTimers();
        vi.mocked(api.removeGmTarget).mockClear();
        renderWatching();

        fireEvent.click(screen.getByRole("button", { name: "Remove" }));

        expect(screen.queryByText("Watched Player")).not.toBeInTheDocument();
        expect(screen.getByRole("status")).toHaveTextContent(/Removed Watched Player/);
        expect(api.removeGmTarget).not.toHaveBeenCalled();
        act(() => {
          vi.advanceTimersByTime(6000);
        });
        expect(api.removeGmTarget).toHaveBeenCalledWith("league-1", "p9");
      });

      it("Undo brings the row back and never calls the API", () => {
        vi.useFakeTimers();
        vi.mocked(api.removeGmTarget).mockClear();
        renderWatching();

        fireEvent.click(screen.getByRole("button", { name: "Remove" }));
        fireEvent.click(screen.getByRole("button", { name: "Undo" }));
        act(() => {
          vi.advanceTimersByTime(10000);
        });

        expect(screen.getByText("Watched Player")).toBeInTheDocument();
        expect(api.removeGmTarget).not.toHaveBeenCalled();
      });
    });

    it("shows an empty-watchlist message when there's nothing to watch", () => {
      render(
        <GmPlanContent
          initialTab="watching"
          leagueId="league-1"
          leagueName="Dynasty Overlords"
          data={BASE_RESPONSE}
          teamStance={STANCE}
          myTeam={MY_TEAM}
          targets={[]}
          rankings={{ ok: true, players: [] }}
        />,
      );

      expect(screen.getByText(/Nothing here yet/)).toBeInTheDocument();
    });

    it("omits the section entirely when no rankings are passed", () => {
      render(<GmPlanContent leagueName="Dynasty Overlords" data={BASE_RESPONSE} />);
      expect(screen.queryByRole("heading", { name: "Watchlist" })).not.toBeInTheDocument();
    });
  });
});

describe("GmPlanContent concept structure", () => {
  const WINDOW = { trade_deadline_week: 11, current_week: 6, trade_deadline_passed: false, message: "" };
  const withWindow = (trade_window: GmPlanResponse["trade_window"]): GmPlanResponse => ({ ...BASE_RESPONSE, trade_window });
  const props = { leagueId: "league-1", teamStance: STANCE, myTeam: MY_TEAM, targets: [], rankings: { ok: true, players: [] } };

  it("switches between the four tabs", () => {
    render(<GmPlanContent leagueName="Dynasty Overlords" data={BASE_RESPONSE} {...props} />);
    expect(screen.getByRole("tab", { name: "Overview", selected: true })).toBeInTheDocument();
    for (const name of ["Trades", "Core", "Watchlist"]) {
      fireEvent.click(screen.getByRole("tab", { name }));
      expect(screen.getByRole("tab", { name, selected: true })).toBeInTheDocument();
    }
    expect(screen.getByRole("heading", { name: "Watchlist" })).toBeInTheDocument();
  });

  it("shows the trade deadline banner with the real week before the deadline", () => {
    render(<GmPlanContent leagueName="L" data={withWindow(WINDOW)} {...props} />);
    expandAll();
    expect(screen.getByTestId("deadline-banner")).toHaveTextContent("Trade deadline: Week 11");
  });

  it("drops the banner after the deadline", () => {
    render(<GmPlanContent leagueName="L" data={withWindow({ ...WINDOW, trade_deadline_passed: true })} {...props} />);
    expect(screen.queryByTestId("deadline-banner")).not.toBeInTheDocument();
    // Summary line says it too; the body only shows once opened.
    expect(screen.getAllByText("Past the trade deadline").length).toBeGreaterThan(0);
  });

  it("renders the four dense stat tiles from the snapshot, and none without data", () => {
    const snapshot = [
      { key: "power" as const, label: "Roster Power", value: "3 of 12", fill: 0.83 },
      { key: "odds" as const, label: "Playoff Odds", value: "55%", fill: 0.55, note: "Proj. 6-seed" },
    ];
    const { unmount } = render(<GmPlanContent leagueName="L" data={BASE_RESPONSE} snapshot={snapshot} {...props} />);
    expect(screen.getByText("This season")).toBeInTheDocument();
    expect(screen.getByText("3rd")).toBeInTheDocument();
    expect(screen.getByText("55%")).toBeInTheDocument();
    unmount();
    render(<GmPlanContent leagueName="L" data={BASE_RESPONSE} snapshot={[]} {...props} />);
    expect(screen.queryByText("This season")).not.toBeInTheDocument();
  });

  it("explains the declared stance in a Why line", () => {
    const snapshot = [{ key: "odds" as const, label: "Playoff Odds", value: "0%", fill: 0 }, { key: "record" as const, label: "Record", value: "3 - 7", fill: null }];
    render(<GmPlanContent leagueName="L" data={BASE_RESPONSE} snapshot={snapshot} {...props} />);
    expect(screen.getByTestId("plan-step-trades")).toHaveTextContent("Sell aging vets for picks");
    expect(screen.getByText("0% playoff odds, 3-7: sell now, buy youth")).toBeInTheDocument();
  });

  it("links trade ideas to Trade Hub", () => {
    render(<GmPlanContent leagueName="L" data={BASE_RESPONSE} {...props} />);
    fireEvent.click(screen.getByTestId("plan-trade-row").querySelector("button")!);
    expect(screen.getAllByRole("link", { name: "View details" })[0].getAttribute("href")).toContain("/trade-hub/league-1");
  });

  it("keeps Free locked while Team Situation stays open", () => {
    const locked: GmPlanResponse = { ok: true, quiet: true, reason: "", focus_areas: [], is_premium: false, upsell: { title: "Locked plan", body: "Upgrade." } };
    render(<GmPlanContent leagueName="L" data={locked} {...props} />);
    expandAll();
    expect(screen.getAllByRole("heading", { name: "Locked plan" }).length).toBeGreaterThan(0);
    expect(screen.getByRole("tab", { name: /^Competing/ })).toBeInTheDocument();
  });

  it("shows an empty state with a next step when there are no trade ideas", () => {
    const none: GmPlanResponse = {
      ...BASE_RESPONSE,
      focus_areas: BASE_RESPONSE.focus_areas.map((a) => (a.key === "trade_opportunities" ? { ...a, status: "no_signal", items: [] } : a)),
    };
    render(<GmPlanContent leagueName="L" data={none} {...props} />);
    expect(screen.getByText("No trade ideas right now.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open Trade Hub" })).toBeInTheDocument();
  });
});
