import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FantasySimContent } from "./FantasySimContent";
import { api, ApiError } from "@/lib/api";
import type { SimForecast, SimForecastResponse } from "@/lib/simPresentation";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: { ...actual.api, getSimForecast: vi.fn() } };
});

const forecast: SimForecast = {
  samples: 80,
  start_week: 10,
  regular_season_end: 14,
  weeks_remaining: 5,
  team: { team_id: "1", name: "Mine" },
  current: { wins: 5, losses: 4, ties: 0 },
  odds: { playoffs: 0.62, finals: 0.2, title: 0.09, playoff_spots: 6 },
  record: { wins: 8.6, losses: 5.4, wins_low: 7, wins_high: 10, projected: "9-5", games: 14 },
  finish: {
    median: 4,
    low: 2,
    high: 7,
    teams: 12,
    distribution: Array.from({ length: 12 }, (_, i) => ({ finish: i + 1, probability: i === 3 ? 0.3 : 0.06 })),
  },
  swing_factors: [
    { kind: "game", week: 11, title: "Week 11 vs Theirs", detail: "Win and your playoff odds are about 75%; lose and they fall to about 40%.", playoff_delta: 0.35, title_delta: 0.05 },
    { kind: "waiver", title: "Work the waiver wire: Pickup Guy (WR)", detail: "Pickups like this lift your playoff odds.", playoff_delta: 0.06, title_delta: 0, players: ["Pickup Guy (WR)"] },
  ],
};
const ok: SimForecastResponse = { ok: true, reason: "", is_premium: true, forecast, notes: ["bye_weeks_unavailable"], mode: "remaining", as_of: "2026-11-12T12:00:00+00:00" };

describe("FantasySimContent (Season Outlook forecast)", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("shows the Pro upsell when the server says premium_required", async () => {
    vi.mocked(api.getSimForecast).mockResolvedValue({ ok: true, reason: "premium_required", is_premium: false, upsell: { title: "Unlock Season Outlook", body: "Pro only." } });
    render(<FantasySimContent leagueId="9" leagueName="Test League" />);
    expect(await screen.findByText("Unlock Season Outlook")).toBeInTheDocument();
  });

  it("shows a coming-soon state when the sim routes 404", async () => {
    vi.mocked(api.getSimForecast).mockRejectedValue(new ApiError(404, "Not found"));
    render(<FantasySimContent leagueId="9" leagueName="Test League" />);
    expect(await screen.findByText("Season Outlook is coming soon")).toBeInTheDocument();
  });

  it("shows an error with retry for a real failure", async () => {
    vi.mocked(api.getSimForecast).mockRejectedValue(new ApiError(500, "Boom"));
    render(<FantasySimContent leagueId="9" leagueName="Test League" />);
    expect(await screen.findByText("Boom")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("renders the one-tap forecast with no strategy controls, scope copy and a game card", async () => {
    vi.mocked(api.getSimForecast).mockResolvedValue(ok);
    render(<FantasySimContent leagueId="9" leagueName="Test League" />);
    expect(await screen.findByLabelText("Playoff odds 62%")).toBeInTheDocument();
    expect(api.getSimForecast).toHaveBeenCalledWith("9");
    expect(screen.getByText(/rest of season \(5 games left\)/)).toBeInTheDocument();
    expect(screen.getByText(/on current rosters/)).toBeInTheDocument();
    expect(screen.getByText("9-5")).toBeInTheDocument();
    expect(screen.getByText("Championship odds")).toBeInTheDocument();
    expect(screen.getByText("Week 11 vs Theirs")).toBeInTheDocument();
    expect(screen.getByText(/Work the waiver wire/)).toBeInTheDocument();
    expect(screen.queryByRole("slider")).toBeNull();
    expect(screen.queryByRole("button", { name: /run simulation/i })).toBeNull();
    expect(screen.getByRole("link", { name: "Play Fantasy Sim" })).toHaveAttribute("href", "/gm-game");
    expect(screen.getByText("Bye weeks could not be loaded, so no player is on bye.")).toBeInTheDocument();
  });

  it("explains a not-ready reason instead of failing silently", async () => {
    vi.mocked(api.getSimForecast).mockResolvedValue({ ok: true, reason: "season_complete" });
    render(<FantasySimContent leagueId="9" leagueName="Test League" />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/regular season is over/);
  });

  it("refreshes the forecast on demand", async () => {
    vi.mocked(api.getSimForecast).mockResolvedValue(ok);
    render(<FantasySimContent leagueId="9" leagueName="Test League" />);
    fireEvent.click(await screen.findByRole("button", { name: "Refresh forecast" }));
    await screen.findByLabelText("Playoff odds 62%");
    expect(api.getSimForecast).toHaveBeenCalledTimes(2);
  });
});
