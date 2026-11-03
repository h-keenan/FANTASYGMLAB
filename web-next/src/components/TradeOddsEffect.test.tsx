import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { oddsStripItems } from "@/components/DashboardOddsStrip";
import { TradeOddsEffect } from "@/components/TradeOddsEffect";
import { api, type GamesSeasonSimResponse, type TradeOddsEffectResponse } from "@/lib/api";

const player = (id: string) => ({ asset_type: "player" as const, player_id: id, name: id });
const pick = { asset_type: "pick" as const, label: "2027 R1" };

function ok(item: Partial<TradeOddsEffectResponse["results"][number]>): TradeOddsEffectResponse {
  return {
    ok: true,
    reason: "",
    is_premium: true,
    upsell: null,
    results: [{ send_player_ids: ["1"], receive_player_ids: ["2"], reason: "", ...item }],
  };
}

describe("TradeOddsEffect", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("shows the change, title odds, margin and sample size, and sends only player ids", async () => {
    const spy = vi.spyOn(api, "postTradeOddsEffect").mockResolvedValue(
      ok({
        picks_excluded: true,
        baseline: { playoff_probability: 40, title_probability: 5, median_final_wins: 7, median_final_losses: 6, median_seed: 6, clinched: false, eliminated: false },
        scenario: { playoff_probability: 52, title_probability: 8, median_final_wins: 8, median_final_losses: 5, median_seed: 4, clinched: false, eliminated: false },
        change: { playoff_probability: 12, title_probability: 3, median_final_wins: 1, median_seed: -2, within_noise: false, title_within_noise: false },
        margin_points: 2.5,
        trials: 3000,
        slope_fitted: true,
        weeks_remaining: 6,
      }),
    );
    render(<TradeOddsEffect leagueId="L1" send={[player("1"), pick]} receive={[player("2")]} />);
    await waitFor(() => expect(screen.getByTestId("trade-odds-effect")).toBeTruthy());
    expect(screen.getByText("Playoff odds 40% to 52% (+12.0 pts)")).toBeTruthy();
    expect(screen.getByText(/Title odds 5% to 8%/)).toBeTruthy();
    expect(screen.getByText(/3,000 simulated seasons/)).toBeTruthy();
    expect(screen.getByText(/Draft picks are not counted/)).toBeTruthy();
    expect(spy).toHaveBeenCalledWith("L1", [{ send_player_ids: ["1"], receive_player_ids: ["2"], has_picks: true }], "Dynasty");
  });

  it("renders nothing when the simulator has no real answer", async () => {
    vi.spyOn(api, "postTradeOddsEffect").mockResolvedValue({
      ok: true,
      reason: "no_games_left",
      is_premium: true,
      upsell: null,
      results: [],
    });
    const { container } = render(<TradeOddsEffect leagueId="L2" send={[player("3")]} receive={[player("4")]} />);
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(container.textContent).toBe("");
  });

  it("points Free accounts at Pro instead of showing odds", async () => {
    vi.spyOn(api, "postTradeOddsEffect").mockResolvedValue({
      ok: true,
      reason: "premium_required",
      is_premium: false,
      upsell: { title: "See how a trade moves your odds", body: "" },
      results: [],
    });
    render(<TradeOddsEffect leagueId="L3" send={[player("5")]} receive={[player("6")]} />);
    await waitFor(() => expect(screen.getByTestId("trade-odds-upsell")).toBeTruthy());
  });
});

describe("oddsStripItems", () => {
  const base: GamesSeasonSimResponse = {
    ok: true,
    reason: "",
    is_premium: false,
    upsell: null,
    my_team: { playoff_probability: 61.4, median_final_wins: 9, median_final_losses: 4, median_seed: 3, title_probability: 0.4, clinched: false, eliminated: false },
    teams: [],
    roster: [],
    title_odds: { available: true, reason: "" },
  };

  it("shows playoff and title odds, with a real tiny chance as <1%", () => {
    const items = oddsStripItems(base)!;
    expect(items.map((i) => i.value)).toEqual(["61%", "<1%", "9-4"]);
  });

  it("falls back to the projected seed when title odds are unavailable and omits the strip when not ready", () => {
    const items = oddsStripItems({ ...base, title_odds: { available: false, reason: "playoffs_underway" } })!;
    expect(items[1].label).toBe("Proj. seed");
    expect(oddsStripItems({ ...base, reason: "offseason" })).toBeNull();
    expect(oddsStripItems(null)).toBeNull();
  });
});
