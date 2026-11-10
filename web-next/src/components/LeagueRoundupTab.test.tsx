import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LeagueRoundupTab } from "./LeagueRoundupTab";
import type { RoundupResponse, RoundupSwap } from "@/lib/api";
import { api } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: { ...actual.api, getLeagueRoundup: vi.fn() } };
});

const player = (id: string, name: string, points: number) => ({ player_id: id, name, position: "RB", team: "XX", points });

const SWAP: RoundupSwap = {
  slot: "RB",
  started: player("1", "Alpha Back", 3),
  benched: player("2", "Beta Back", 21),
  gain: 18,
  predictability: "foreseeable",
  edge: 4.2,
  reason: "Our projection had the benched player ahead by 4.2 pts before the week.",
  started_projection: { points: 8, sd: 3 },
  benched_projection: { points: 12.2, sd: 3 },
};

function response(overrides: Partial<RoundupResponse> = {}): RoundupResponse {
  return {
    ok: true,
    reason: "",
    max_completed_week: 3,
    week: 3,
    roundup: {
      week: 3,
      actual_points: 95,
      optimal_points: 113,
      left_on_bench: 18,
      foreseeable_points: 18,
      lineup: [{ slot: "RB", actual: player("1", "Alpha Back", 3), optimal: player("2", "Beta Back", 21) }],
      swaps: [SWAP],
      unattributed_points: 0,
      takeaway: "This miss was visible before kickoff: the benched player had a clear projection edge.",
    },
    season: {
      weeks_reviewed: 3,
      total_left_on_bench: 30,
      avg_left_on_bench: 10,
      foreseeable_points: 18,
      foreseeable_share: 0.6,
      weeks: [{ week: 3, actual_points: 95, optimal_points: 113, left_on_bench: 18, foreseeable_points: 18 }],
      summary: "Over 3 weeks you left 30.0 pts on the bench (10.0 per week); about 60% of that was foreseeable.",
    },
    method: "Predictability uses retroactive point-in-time projections.",
    is_premium: true,
    upsell: null,
    ...overrides,
  };
}

const mock = api.getLeagueRoundup as unknown as ReturnType<typeof vi.fn>;

describe("LeagueRoundupTab", () => {
  beforeEach(() => mock.mockReset());

  it("shows the headline numbers, tagged swap, lineup, season tally and the method note for Pro", async () => {
    mock.mockResolvedValue(response());
    render(<LeagueRoundupTab leagueId="L1" />);
    expect(await screen.findByText("Week 3")).toBeTruthy();
    expect(screen.getByText("113.0")).toBeTruthy();
    expect(screen.getByTestId("swap-tag").textContent).toBe("Foreseeable");
    expect(screen.getByText("Alpha Back (3.0) over Beta Back (21.0)")).toBeTruthy();
    expect(screen.getByText("Your lineup vs the best one")).toBeTruthy();
    expect(screen.getByTestId("season-summary").textContent).toContain("30.0 pts");
    expect(screen.getByTestId("roundup-method").textContent).toContain("point-in-time");
  });

  it("gives Free the headline and top swap with an upgrade card, no lineup or season", async () => {
    mock.mockResolvedValue(
      response({
        is_premium: false,
        season: null,
        upsell: { title: "See your full weekly roundup", body: "Pro shows more." },
        roundup: { ...response().roundup!, lineup: [], swaps_total: 3 },
      }),
    );
    render(<LeagueRoundupTab leagueId="L1" />);
    expect(await screen.findByText("Biggest miss")).toBeTruthy();
    expect(screen.getByText("2 more missed swaps with Pro.")).toBeTruthy();
    expect(screen.getByText("See your full weekly roundup")).toBeTruthy();
    expect(screen.queryByText("Your lineup vs the best one")).toBeNull();
    expect(screen.queryByTestId("season-summary")).toBeNull();
  });

  it("degrades offseason and unsupported leagues to an explanation", async () => {
    mock.mockResolvedValue(response({ roundup: null, reason: "no_completed_week", max_completed_week: 0, season: null }));
    const { unmount } = render(<LeagueRoundupTab leagueId="L1" />);
    expect(await screen.findByText("No roundup yet")).toBeTruthy();
    unmount();
    mock.mockResolvedValue(response({ roundup: null, reason: "unsupported_platform", season: null }));
    render(<LeagueRoundupTab leagueId="L1" />);
    expect(await screen.findByText("Roundup is not available for this league type yet")).toBeTruthy();
  });

  it("loads another week from the picker and offers a retry on failure", async () => {
    mock.mockResolvedValue(response());
    render(<LeagueRoundupTab leagueId="L1" />);
    await screen.findByText("Week 3");
    mock.mockResolvedValue(response({ week: 2 }));
    fireEvent.click(screen.getByRole("tab", { name: "Wk 2" }));
    await waitFor(() => expect(mock).toHaveBeenLastCalledWith("L1", 2));
  });

  it("shows an error with retry when the request fails", async () => {
    mock.mockRejectedValueOnce(new Error("boom"));
    render(<LeagueRoundupTab leagueId="L1" />);
    expect(await screen.findByText("Could not load your roundup")).toBeTruthy();
    mock.mockResolvedValue(response());
    fireEvent.click(screen.getByText("Try again"));
    expect(await screen.findByText("Week 3")).toBeTruthy();
  });
});
