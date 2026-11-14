import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ValueSignalsCard } from "@/components/ValueSignalsCard";
import { PlayerValueHistory } from "@/components/PlayerValueHistory";
import { api, type ValueSignalItem } from "@/lib/api";

vi.mock("@/components/RatingHistoryChart", () => ({ RatingHistoryChart: () => <div data-testid="chart" /> }));
vi.mock("@/components/PlayerIdentityTrigger", () => ({
  PlayerIdentityTrigger: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

const item = (over: Partial<ValueSignalItem> = {}): ValueSignalItem => ({
  player_id: "1",
  name: "Test Receiver",
  position: "WR",
  team: "SF",
  age: 25,
  rating: 70,
  rating_change: -6,
  ppg: 14.2,
  games_played: 8,
  production_percentile: 80,
  value_percentile: 50,
  gap: 30,
  injury_status: null,
  signal: "buy_low",
  factors: [],
  ...over,
});

describe("ValueSignalsCard", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    window.localStorage.clear();
  });

  it("lists buy-low players with both halves of the reason", async () => {
    vi.spyOn(api, "getPlayerValueSignals").mockResolvedValue({
      ok: true, status: "ok", span_days: 12, method: "Method.", buy_low: [item()], sell_high: [],
    });
    render(<ValueSignalsCard leagueId="L" />);
    // Collapsed it already says "1 signal · 1 buy low · 0 sell high · Test Receiver"; open for the reasons.
    fireEvent.click(await screen.findByRole("button", { name: /^Buy low \/ Sell high: 1 signal/ }));
    await waitFor(() => expect(screen.getAllByText("Test Receiver").length).toBeGreaterThan(0));
    expect(screen.getByText(/production 80th pct vs value 50th/)).toBeTruthy();
    expect(screen.getByText(/12 days of stored value history/)).toBeTruthy();
  });

  it("says how little history exists instead of listing anyone", async () => {
    vi.spyOn(api, "getPlayerValueSignals").mockResolvedValue({
      ok: true, status: "history_building", span_days: 3, min_span_days: 7, buy_low: [], sell_high: [],
    });
    render(<ValueSignalsCard leagueId="L" />);
    await waitFor(() => expect(screen.getAllByText(/3 days stored so far, 7 needed/).length).toBeGreaterThan(0));
  });

  it("renders nothing when value history is unavailable", async () => {
    vi.spyOn(api, "getPlayerValueSignals").mockResolvedValue({ ok: true, status: "unavailable", buy_low: [], sell_high: [] });
    const { container } = render(<ValueSignalsCard leagueId="L" />);
    await waitFor(() => expect(container.querySelector("[data-testid='value-signals']")).toBeNull());
    expect(container.textContent).not.toContain("Buy low");
  });
});

describe("PlayerValueHistory", () => {
  it("draws the chart only for real multi-day history and states the span", async () => {
    vi.spyOn(api, "getPlayerRatingHistory").mockResolvedValue({
      ok: true, status: "ok", span_days: 9, current_rating: 66,
      points: [{ date: "2026-10-01", rating: 60 }, { date: "2026-10-10", rating: 66 }],
      change: { days: 9, delta: 6 }, changes: [{ days: 9, delta: 6, from_date: "2026-10-01" }],
    });
    render(<PlayerValueHistory playerId="9" />);
    await waitFor(() => expect(screen.getByTestId("chart")).toBeTruthy());
    expect(screen.getByText(/\+6 over 9 days/)).toBeTruthy();
  });

  it("shows only a short-history note for one snapshot", async () => {
    vi.spyOn(api, "getPlayerRatingHistory").mockResolvedValue({
      ok: true, status: "insufficient_history", span_days: 0, first_date: "2026-10-01",
      points: [{ date: "2026-10-01", rating: 60 }],
    });
    render(<PlayerValueHistory playerId="10" />);
    await waitFor(() => expect(screen.getByText(/started Oct 1/)).toBeTruthy());
    expect(screen.queryByTestId("chart")).toBeNull();
  });
});
