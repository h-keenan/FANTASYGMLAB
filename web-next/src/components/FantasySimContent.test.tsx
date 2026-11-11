import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FantasySimContent } from "./FantasySimContent";
import { api, ApiError } from "@/lib/api";
import { DEFAULT_SIM_STRATEGY, type SimResult, type SimWorld } from "@/lib/simPresentation";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      getSimStatus: vi.fn(),
      listSimWorlds: vi.fn(),
      createSimWorld: vi.fn(),
      updateSimStrategy: vi.fn(),
      runSimWorld: vi.fn(),
      getSimResult: vi.fn(),
      deleteSimWorld: vi.fn(),
      getTeamRankings: vi.fn(),
      getMyTeam: vi.fn(),
    },
  };
});

const world: SimWorld = {
  id: "w1",
  source_league_id: "9",
  league_name: "Test League",
  mode: "remaining",
  seed: 1,
  engine_version: "sim-1.0.0",
  status: "ready",
  strategy: DEFAULT_SIM_STRATEGY,
  grade_letter: null,
  created_at: "",
  updated_at: "",
};

function result(letter: string, wins: number, playoff = "semifinal"): SimResult {
  return {
    engine_version: "sim-1.0.0",
    seed: 1,
    mode: "remaining",
    strategy: DEFAULT_SIM_STRATEGY,
    standings: [
      { team_id: "1", name: "Mine", is_user: true, wins, losses: 14 - wins, ties: 0, pf: 1500, pa: 1400, seed: 2, made_playoffs: true, playoff_result: playoff },
      { team_id: "2", name: "Theirs", is_user: false, wins: 6, losses: 8, ties: 0, pf: 1300, pa: 1400, seed: 5, made_playoffs: false, playoff_result: "missed" },
    ],
    playoffs: [{ round: 1, week: 15, games: [{ home: "1", away: "2", home_pts: 100, away_pts: 90, winner: "1" }] }],
    champion: "1",
    events: [{ week: 8, seq: 0, type: "waiver", team: "1", involves_user: true, add: { name: "Pickup Guy", pos: "WR" }, drop: null }],
    personas: [{ team_id: "2", name: "Theirs", is_user: false, persona_id: "passive", label: "Passive", blurb: "Rarely moves.", power_percentile: 0.3, avg_age: 26 }],
    user: { team_id: "1", wins, losses: 14 - wins, ties: 0, pf: 1500, pa: 1400, seed: 2, playoff_result: playoff, made_playoffs: true },
    grade: { letter, score: 70, grade_points: 80, components: [{ key: "record", label: "Record and seeding", score: 80, weight: 0.35 }], summary: {} },
    decisions_that_mattered: [{ kind: "waiver", week: 8, title: "Week 8 pickup: Pickup Guy", detail: "That move helped your season.", impact: { season_value: 1, points_per_game: 2.5 } }],
  };
}

describe("FantasySimContent", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(api.listSimWorlds).mockResolvedValue({ ok: true, worlds: [] });
    vi.mocked(api.getTeamRankings).mockRejectedValue(new Error("no"));
    vi.mocked(api.getMyTeam).mockRejectedValue(new Error("no"));
  });

  it("shows the Pro upsell when the server says premium_required", async () => {
    vi.mocked(api.getSimStatus).mockResolvedValue({ ok: true, reason: "premium_required", is_premium: false, upsell: { title: "Unlock Fantasy Sim", body: "Pro only." } });
    render(<FantasySimContent leagueId="9" leagueName="Test League" />);
    expect(await screen.findByText("Unlock Fantasy Sim")).toBeInTheDocument();
  });

  it("shows a coming-soon state when the sim routes 404", async () => {
    vi.mocked(api.getSimStatus).mockRejectedValue(new ApiError(404, "Not found"));
    render(<FantasySimContent leagueId="9" leagueName="Test League" />);
    expect(await screen.findByText("Fantasy Sim is coming soon")).toBeInTheDocument();
  });

  it("says it is temporarily unavailable (not coming soon) when storage is not applied yet", async () => {
    vi.mocked(api.getSimStatus).mockResolvedValue({ ok: true, reason: "sim_storage_unavailable", is_premium: true });
    render(<FantasySimContent leagueId="9" leagueName="Test League" />);
    expect(await screen.findByText("Fantasy Sim is temporarily unavailable")).toBeInTheDocument();
  });

  it("shows an error with retry for a real failure", async () => {
    vi.mocked(api.getSimStatus).mockRejectedValue(new ApiError(500, "Boom"));
    render(<FantasySimContent leagueId="9" leagueName="Test League" />);
    expect(await screen.findByText("Boom")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("runs a sim, labels it a simulation, and compares a re-run", async () => {
    vi.mocked(api.getSimStatus).mockResolvedValue({ ok: true, reason: "", is_premium: true, enabled: true });
    vi.mocked(api.createSimWorld).mockResolvedValue({ ok: true, reason: "", world, team: { team_id: "1", name: "Mine" }, notes: ["bye_weeks_not_modeled"] });
    vi.mocked(api.runSimWorld).mockResolvedValueOnce({ ok: true, reason: "", world, result: result("C", 7, "missed") });
    render(<FantasySimContent leagueId="9" leagueName="Test League" />);

    fireEvent.click(await screen.findByRole("button", { name: "Run simulation" }));
    expect(await screen.findByLabelText("Grade C")).toBeInTheDocument();
    expect(screen.getAllByText(/This is a simulation/).length).toBeGreaterThan(0);
    expect(screen.getByText("Decisions that mattered")).toBeInTheDocument();
    expect(api.createSimWorld).toHaveBeenCalledWith(expect.objectContaining({ league_id: "9", mode: "remaining", strategy: DEFAULT_SIM_STRATEGY }));

    vi.mocked(api.updateSimStrategy).mockResolvedValue({ ok: true, reason: "", world });
    vi.mocked(api.runSimWorld).mockResolvedValueOnce({ ok: true, reason: "", world, result: result("A", 10, "champion") });
    fireEvent.click(screen.getByRole("button", { name: "Change strategy" }));
    fireEvent.click(screen.getByRole("radio", { name: /Win now/ }));
    fireEvent.click(screen.getByRole("button", { name: "Run again" }));

    expect(await screen.findByLabelText("Grade A")).toBeInTheDocument();
    await waitFor(() => expect(api.updateSimStrategy).toHaveBeenCalledWith("w1", expect.objectContaining({ posture: "win_now" })));
    expect(screen.getByText("Strategy A/B")).toBeInTheDocument();
    expect(screen.getByText(/3 wins more/)).toBeInTheDocument();
  });

  it("explains a not-ready reason instead of failing silently", async () => {
    vi.mocked(api.getSimStatus).mockResolvedValue({ ok: true, reason: "", is_premium: true, enabled: true });
    vi.mocked(api.createSimWorld).mockResolvedValue({ ok: true, reason: "season_complete" });
    render(<FantasySimContent leagueId="9" leagueName="Test League" />);
    fireEvent.click(await screen.findByRole("button", { name: "Run simulation" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/regular season is over/);
  });
});
