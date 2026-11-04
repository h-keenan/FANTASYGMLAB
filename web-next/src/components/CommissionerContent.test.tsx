import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CommissionerContent } from "./CommissionerContent";
import { api } from "@/lib/api";
import type { CommissionerIntegrityResponse, IntegrityTeam, VetoCheckResponse } from "@/lib/commissionerIntegrity";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: {
      ...actual.api,
      getCommissionerIntegrity: vi.fn(),
      getLeagueRankings: vi.fn(),
      getLeagueDraftPicks: vi.fn(),
      getLeagueRosters: vi.fn(),
      getLeagueTeamProfiles: vi.fn(),
      postCommissionerVetoCheck: vi.fn(),
    } };
});

const tanker: IntegrityTeam = {
  roster_id: 6, team_name: "Tanker", owner_name: "Tom", band: "strong", band_label: "Strong signals", score: 0.88,
  confidence: "high", interpretation: "possible_tanking", context: "eliminated",
  weeks: { evaluated: 6, flagged: 5, longest_streak: 5, latest_streak: 5 },
  evidence: [{ kind: "lineup", week: 6, text: "Week 6: started WR4 over WR1." }],
  innocent_explanations: ["Late injury designations."],
  series: [{ week: 1, actual: 100, best_possible: 110, efficiency: 0.9, flagged: false }],
};
const fine: IntegrityTeam = { ...tanker, roster_id: 1, team_name: "Alpha", band: "fine", band_label: "Lineup looks fine", interpretation: "none", score: 0.03 };

function body(overrides: Partial<CommissionerIntegrityResponse> = {}): CommissionerIntegrityResponse {
  return { ok: true, reason: "", is_premium: true, upsell: null, weeks_evaluated: 6, teams: [tanker, fine], collusion: [], inactive: [], limits: ["Sleeper does not say who was injured."], ...overrides };
}

describe("CommissionerContent", () => {
  beforeEach(() => vi.mocked(api.getCommissionerIntegrity).mockReset());

  it("shows flagged teams with evidence and innocent explanations, others collapsed", async () => {
    vi.mocked(api.getCommissionerIntegrity).mockResolvedValue(body());
    render(<CommissionerContent leagueId="L1" leagueName="My League" />);
    expect(await screen.findByText("Tanker")).toBeTruthy();
    expect(screen.getByText("Strong signals")).toBeTruthy();
    expect(screen.getByText("Week 6: started WR4 over WR1.")).toBeTruthy();
    expect(screen.getByText("Late injury designations.")).toBeTruthy();
    expect(screen.queryByText("Alpha")).toBeNull();
    fireEvent.click(screen.getByText("Show 1 team"));
    expect(screen.getByText("Alpha")).toBeTruthy();
  });

  it("re-requests with the draft-order rule the commissioner picks", async () => {
    vi.mocked(api.getCommissionerIntegrity).mockResolvedValue(body());
    render(<CommissionerContent leagueId="L1" leagueName="My League" />);
    await screen.findByText("Tanker");
    fireEvent.click(screen.getByText("Worst record picks first"));
    await waitFor(() => expect(api.getCommissionerIntegrity).toHaveBeenLastCalledWith("L1", "record"));
  });

  it("is honest in early season and for unsupported platforms", async () => {
    vi.mocked(api.getCommissionerIntegrity).mockResolvedValue(body({ reason: "not_enough_weeks", teams: [] }));
    const { unmount } = render(<CommissionerContent leagueId="L1" leagueName="My League" />);
    expect(await screen.findByText(/at least three completed/)).toBeTruthy();
    unmount();
    vi.mocked(api.getCommissionerIntegrity).mockResolvedValue(body({ reason: "unsupported_platform", teams: [] }));
    render(<CommissionerContent leagueId="L2" leagueName="Other" />);
    expect(await screen.findByText(/only available for Sleeper leagues/)).toBeTruthy();
  });

  it("shows the upsell for a Free account", async () => {
    vi.mocked(api.getCommissionerIntegrity).mockResolvedValue(
      body({ is_premium: false, teams: [], upsell: { title: "Spot tanking early", body: "Pro feature." } }),
    );
    render(<CommissionerContent leagueId="L1" leagueName="My League" />);
    expect(await screen.findByText("Spot tanking early")).toBeTruthy();
    // One page title; the upsell title is a section heading, not a second <h1>.
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  });

  it("shows a repeated-trade pair as worth a look with its evidence and innocent explanations", async () => {
    vi.mocked(api.getCommissionerIntegrity).mockResolvedValue(
      body({
        collusion: [
          {
            roster_ids: [3, 9], beneficiary_name: "Alpha", giver_name: "Bravo", headline: "Alpha and Bravo",
            summary: "4 trades between them with a repeating pattern worth a look", patterns: ["round_trip"],
            trades_between: 4, lopsided_same_direction: 0, band: "worth_a_look", band_label: "Worth a look", confidence: "low",
            evidence: ["3 assets went back and forth between them across 4 trades (2026 1st)."],
            innocent_explanations: ["A trade can be undone or reworked."],
          },
        ],
      }),
    );
    render(<CommissionerContent leagueId="L1" leagueName="My League" />);
    expect(await screen.findByText("Alpha and Bravo")).toBeTruthy();
    expect(screen.getByText(/repeating pattern worth a look/)).toBeTruthy();
    expect(screen.getByText(/went back and forth/)).toBeTruthy();
    expect(screen.getByText("A trade can be undone or reworked.")).toBeTruthy();
  });

  it("collapses a clean league to one summary line and shows the league calendar", async () => {
    const teams = Array.from({ length: 12 }, (_, i) => ({ ...fine, roster_id: i + 1, team_name: `Team ${i + 1}` }));
    vi.mocked(api.getCommissionerIntegrity).mockResolvedValue(
      body({
        teams,
        calendar: { trade_deadline_week: 11, current_week: 8, trade_deadline_passed: false, weeks_to_deadline: 3, deadline_phase: "open", playoff_week_start: 15, regular_season_weeks: 14, in_season: true },
      }),
    );
    render(<CommissionerContent leagueId="L1" leagueName="My League" />);
    expect(await screen.findByText("All 12 teams look fine this week")).toBeTruthy();
    expect(screen.queryByText("Team 1")).toBeNull();
    expect(screen.getByText("Trade deadline: after week 11 (3 weeks left)")).toBeTruthy();
    expect(screen.getByText("Playoffs start week 15")).toBeTruthy();
    fireEvent.click(screen.getByText("Show 12 teams"));
    expect(screen.getByText("Team 12")).toBeTruthy();
  });

  describe("trade veto calculator", () => {
    const vetoOk: VetoCheckResponse = {
      ok: true, status: "ok", is_premium: true, outrage: 52, band: "lopsided", label: "Lopsided", advice: "Worth a conversation before it processes.",
      hurt_roster_id: "1", reasons: ["Alpha's lineup loses about 4.0 points a week."], limits: ["A signal to look at a trade; the league's rules decide."],
      sides: [
        { roster_id: 1, team_name: "Alpha", posture: "contender", sends: ["Star WR"], receives: ["2027 1st"], market_delta: -900, team_score: -1500, points_per_week: -4, worst_position: { position: "WR", per_week_delta: -4 } },
        { roster_id: 2, team_name: "Bravo", posture: "rebuild", sends: ["2027 1st"], receives: ["Star WR"], market_delta: 900, team_score: 800, points_per_week: 1.2, worst_position: null },
      ],
    };

    async function openAndBuild() {
      vi.mocked(api.getCommissionerIntegrity).mockResolvedValue(body());
      vi.mocked(api.getLeagueRankings).mockResolvedValue({ players: [{ player_id: "p1", name: "Star WR", position: "WR", team: "KC", age: 25, score: 5000 }] } as never);
      vi.mocked(api.getLeagueDraftPicks).mockResolvedValue({ ok: true, picks: [], reason: "" } as never);
      vi.mocked(api.getLeagueRosters).mockResolvedValue({ ok: true, rosters: [{ roster_id: 1, players: ["p1"] }, { roster_id: 2, players: [] }] });
      vi.mocked(api.getLeagueTeamProfiles).mockResolvedValue({
        ok: true,
        profiles: {
          "1": { team_name: "Alpha", owner_name: "", username: "", avatar_id: "", avatar_url: "", roster_id: 1, owner_id: "" },
          "2": { team_name: "Bravo", owner_name: "", username: "", avatar_id: "", avatar_url: "", roster_id: 2, owner_id: "" },
        },
      });
      render(<CommissionerContent leagueId="L1" leagueName="My League" />);
      fireEvent.click(await screen.findByText("Check a proposed trade"));
      const teamA = await screen.findByRole("tablist", { name: "Team A" });
      fireEvent.click(within(teamA).getByText("Alpha"));
      fireEvent.click(within(screen.getByRole("tablist", { name: "Team B" })).getByText("Bravo"));
      fireEvent.click(await screen.findByText("Star WR"));
      fireEvent.click(screen.getByText("Check this trade"));
    }

    it("shows the score, band, per-team cards, reasons and limits", async () => {
      vi.mocked(api.postCommissionerVetoCheck).mockResolvedValue(vetoOk);
      await openAndBuild();
      expect(await screen.findByTestId("veto-result")).toBeTruthy();
      expect(screen.getByTestId("veto-outrage").textContent).toBe("52");
      expect(screen.getByText("Lopsided: worth a conversation")).toBeTruthy();
      expect(screen.getByText("Worth a conversation before it processes.")).toBeTruthy();
      expect(screen.getByText("Rebuild")).toBeTruthy();
      expect(screen.getByText("Contender")).toBeTruthy();
      expect(screen.getByText("Market value -900")).toBeTruthy();
      expect(screen.getByText("Biggest hit: WR (-4.0 pts/wk)")).toBeTruthy();
      expect(screen.getByText("Alpha's lineup loses about 4.0 points a week.")).toBeTruthy();
      expect(screen.getByTestId("veto-limits").textContent).toContain("the league's rules decide");
      expect(vi.mocked(api.postCommissionerVetoCheck)).toHaveBeenCalledWith(
        "L1",
        expect.objectContaining({ roster_a: 1, roster_b: 2, a_sends_player_ids: ["p1"], lens: "Dynasty" }),
      );
    });

    it("shows the upsell when the check is locked", async () => {
      vi.mocked(api.postCommissionerVetoCheck).mockResolvedValue({ ok: true, status: "locked", is_premium: false, upsell: { title: "Veto check is Pro", body: "Upgrade." } });
      await openAndBuild();
      expect(await screen.findByText("Veto check is Pro")).toBeTruthy();
    });

    it("shows the server headline for an invalid trade", async () => {
      vi.mocked(api.postCommissionerVetoCheck).mockResolvedValue({ ok: true, status: "invalid", headline: "A player in the trade is not on that team's roster any more." });
      await openAndBuild();
      expect(await screen.findByText("A player in the trade is not on that team's roster any more.")).toBeTruthy();
      expect(screen.queryByTestId("veto-result")).toBeNull();
    });
  });
});
