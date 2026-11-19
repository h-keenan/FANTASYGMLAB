import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PortfolioFreeStanding } from "@/components/PortfolioFreeStanding";
import { SimRealHistory } from "@/components/SimRealHistory";

const getPlayerCareer = vi.fn();
const getPlayerWeeklyStats = vi.fn();
const getDashboard = vi.fn();

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: { ...actual.api, getPlayerCareer: (...a: unknown[]) => getPlayerCareer(...a), getPlayerWeeklyStats: (...a: unknown[]) => getPlayerWeeklyStats(...a), getDashboard: (...a: unknown[]) => getDashboard(...a) } };
});
const SAVED = { rows: [{ league_id: "L1", league_name: "Test" }], status: "ready", reload: () => {} };
vi.mock("@/lib/useSavedLeagues", () => ({ useSavedLeagues: () => SAVED }));

const season = { season: 2025, age: 25, games: 17, current_season: false, key_stats: [{ label: "Pts", value: "200" }] };

describe("SimRealHistory failure states (silent-failures audit)", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows the shared error with Try again when the career fails, and retries", async () => {
    getPlayerCareer.mockRejectedValueOnce(new Error("boom")).mockResolvedValue({ ok: true, seasons: [season] });
    getPlayerWeeklyStats.mockResolvedValue({ ok: true, season: 2025, weeks: [], stats_available: true });
    render(<SimRealHistory playerId="9" asOf={2025} />);
    expect(await screen.findByText("Could not load past seasons", {}, { timeout: 5000 })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByTestId("sim-real-history", {}, { timeout: 5000 })).toBeInTheDocument();
    expect(getPlayerCareer).toHaveBeenCalledTimes(2);
  });

  it("does not read a failed game-log load as 'no games'", async () => {
    getPlayerCareer.mockResolvedValue({ ok: true, seasons: [] });
    getPlayerWeeklyStats.mockResolvedValue({ ok: true, season: 2025, weeks: [], stats_available: false });
    render(<SimRealHistory playerId="9" asOf={2025} />);
    expect(await screen.findByTestId("error-state-compact", {}, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.queryByText("No NFL seasons on file before this one.")).toBeNull();
  });

  it("still says 'no seasons' when the load worked and there is genuinely nothing", async () => {
    getPlayerCareer.mockResolvedValue({ ok: true, seasons: [] });
    getPlayerWeeklyStats.mockResolvedValue({ ok: true, season: 2025, weeks: [], stats_available: true });
    render(<SimRealHistory playerId="9" asOf={2025} />);
    expect(await screen.findByText("No NFL seasons on file before this one.", {}, { timeout: 5000 })).toBeInTheDocument();
  });
});

describe("PortfolioFreeStanding failure state", () => {
  it("shows a retry row instead of vanishing when the standing fails to load", async () => {
    getDashboard.mockRejectedValueOnce(new Error("down")).mockResolvedValue({ team_snapshot: { wins: 3, losses: 1, ties: 0 } });
    render(<PortfolioFreeStanding />);
    const retry = await screen.findByRole("button", { name: "Try again" }, { timeout: 5000 });
    fireEvent.click(retry);
    await waitFor(() => expect(getDashboard).toHaveBeenCalledTimes(2));
  });
});
