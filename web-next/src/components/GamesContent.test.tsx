import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { GamesContent } from "./GamesContent";
import { api } from "@/lib/api";
import type { GamesPickemResponse, GamesSeasonSimResponse } from "@/lib/api";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      getGamesSeasonSim: vi.fn(),
      postGamesWhatIf: vi.fn(),
      getGamesPickem: vi.fn(),
      postGamesPick: vi.fn(),
      getLeagueRankings: vi.fn(),
    },
  };
});

const mine = {
  playoff_probability: 62,
  median_final_wins: 9,
  median_final_losses: 5,
  median_seed: 4,
  clinched: false,
  eliminated: false,
};

function sim(overrides: Partial<GamesSeasonSimResponse> = {}): GamesSeasonSimResponse {
  return {
    ok: true,
    reason: "",
    is_premium: true,
    upsell: null,
    my_roster_id: "1",
    my_team: mine,
    teams: [
      { roster_id: "1", team_name: "Alpha", avatar_url: null, record_label: "5-3", playoff_probability: 62, median_seed: 4, mine: true },
      { roster_id: "2", team_name: "Bravo", avatar_url: null, record_label: "6-2", playoff_probability: 80, median_seed: 2, mine: false },
    ],
    roster: [{ player_id: "10", name: "Sam Starter", position: "WR", team: "KC", injury_status: null, tier: null }],
    weeks_remaining: 6,
    ...overrides,
  };
}

function pickem(overrides: Partial<GamesPickemResponse> = {}): GamesPickemResponse {
  return {
    ok: true,
    available: true,
    reason: "",
    season: "2026",
    current_week: 5,
    weeks: [1, 2, 3, 4, 5],
    week: 5,
    phase: "open",
    matchups: [
      {
        matchup_id: "1",
        teams: [
          { roster_id: "1", team_name: "Alpha", owner_name: "a", avatar_url: null, points: 0 },
          { roster_id: "2", team_name: "Bravo", owner_name: "b", avatar_url: null, points: 0 },
        ],
        my_pick: null,
        winner_roster_id: null,
        correct: null,
      },
    ],
    picked: 0,
    correct: 0,
    graded: 0,
    season_record: { correct: 0, graded: 0 },
    leaderboard: [],
    leaderboard_scope: "league",
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("GamesContent season sim", () => {
  it("shows my odds and the league table", async () => {
    vi.mocked(api.getGamesSeasonSim).mockResolvedValue(sim());
    render(<GamesContent leagueId="9" leagueName="Test League" />);
    expect(await screen.findByText("Your odds")).toBeInTheDocument();
    expect(screen.getAllByText("62%").length).toBeGreaterThan(0);
    expect(screen.getByText("Bravo")).toBeInTheDocument();
  });

  it("shows the upgrade card instead of the what-if builder for Free", async () => {
    vi.mocked(api.getGamesSeasonSim).mockResolvedValue(
      sim({ is_premium: false, upsell: { title: "See how a move changes your season", body: "Premium feature." } }),
    );
    render(<GamesContent leagueId="9" leagueName="Test League" />);
    expect(await screen.findByText("See how a move changes your season")).toBeInTheDocument();
    expect(screen.queryByText("Run what-if")).not.toBeInTheDocument();
  });

  it("runs a what-if for Premium and reports the change", async () => {
    vi.mocked(api.getGamesSeasonSim).mockResolvedValue(sim());
    vi.mocked(api.postGamesWhatIf).mockResolvedValue({
      ok: true,
      reason: "",
      is_premium: true,
      upsell: null,
      baseline: mine,
      scenario: { ...mine, playoff_probability: 71 },
      change: { playoff_probability: 9, median_final_wins: 1, median_seed: -1, within_noise: false },
      factors: [{ label: "Lineup strength", detail: "+20 starter value" }],
    });
    render(<GamesContent leagueId="9" leagueName="Test League" />);
    fireEvent.click(await screen.findByRole("button", { name: "Drop" }));
    fireEvent.click(screen.getByRole("button", { name: "Run what-if" }));
    await waitFor(() => expect(api.postGamesWhatIf).toHaveBeenCalledWith("9", { add: [], drop: ["10"] }));
    expect(await screen.findByText("Raises your playoff odds by 9.0 points.")).toBeInTheDocument();
    expect(screen.getByText("+20 starter value")).toBeInTheDocument();
  });

  it("shows an empty state with a next step when the season has not started", async () => {
    vi.mocked(api.getGamesSeasonSim).mockResolvedValue(sim({ reason: "offseason", my_team: null, teams: [] }));
    render(<GamesContent leagueId="9" leagueName="Test League" />);
    expect(await screen.findByText(/Opens once the regular season starts/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Back to Dashboard" })).toBeInTheDocument();
  });
});

describe("GamesContent pick'em", () => {
  async function openPickem() {
    vi.mocked(api.getGamesSeasonSim).mockResolvedValue(sim());
    render(<GamesContent leagueId="9" leagueName="Test League" />);
    fireEvent.click(await screen.findByRole("tab", { name: "Pick'em" }));
  }

  it("saves a pick optimistically", async () => {
    vi.mocked(api.getGamesPickem).mockResolvedValue(pickem());
    vi.mocked(api.postGamesPick).mockResolvedValue({ ok: true, available: true, reason: "" });
    await openPickem();
    const bravo = await screen.findByRole("button", { name: /Bravo/ });
    fireEvent.click(bravo);
    expect(api.postGamesPick).toHaveBeenCalledWith("9", { week: 5, matchup_id: "1", roster_id: "2" });
    await waitFor(() => expect(screen.getByRole("button", { name: /Bravo/ })).toHaveAttribute("aria-pressed", "true"));
  });

  it("disables picking once the week is locked", async () => {
    vi.mocked(api.getGamesPickem).mockResolvedValue(pickem({ phase: "locked" }));
    await openPickem();
    expect(await screen.findByRole("button", { name: /Bravo/ })).toBeDisabled();
  });

  it("shows the dormant state when storage is not set up", async () => {
    vi.mocked(api.getGamesPickem).mockResolvedValue({ ok: true, available: false, reason: "" });
    await openPickem();
    expect(await screen.findByText("Pick'em is not open yet")).toBeInTheDocument();
  });

  it("lists the leaderboard", async () => {
    vi.mocked(api.getGamesPickem).mockResolvedValue(
      pickem({
        phase: "final",
        leaderboard: [
          { rank: 1, roster_id: "2", team_name: "Bravo", owner_name: "b", avatar_url: null, correct: 5, graded: 6, accuracy: 83, mine: false },
        ],
      }),
    );
    await openPickem();
    expect(await screen.findByText("5/6")).toBeInTheDocument();
  });
});
