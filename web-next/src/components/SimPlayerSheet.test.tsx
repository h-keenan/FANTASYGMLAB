import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SimPlayerSheet } from "./SimGamePlayers";
import { api } from "@/lib/api";
import type { SimGamePlayer, SimPlayerDetailResponse } from "@/lib/simGame";

vi.mock("next/navigation", () => ({ usePathname: () => "/sim" }));
vi.mock("@/components/WeeklyPointsChartLazy", () => ({
  WeeklyPointsPanel: (props: { projection?: unknown[] | null; weeks: unknown[] }) => (
    <div data-testid="weekly-chart" data-weeks={props.weeks.length} data-band={props.projection ? props.projection.length : 0} />
  ),
  usePreloadWeeklyPointsChart: () => {},
}));
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: { ...actual.api, getSimGamePlayer: vi.fn(), getPlayerQuickView: vi.fn(), getPlayerAwards: vi.fn(), getPlayerWeeklyStats: vi.fn(), getPlayerNews: vi.fn() } };
});

const player = (over: Partial<SimGamePlayer> = {}): SimGamePlayer => ({
  id: "R2027-001", headshot_id: null, name: "Brock Briggs", pos: "RB", team: "BUF", age: 24, adp: 40, value: 0, projection: 2.2, floor: 0.6, ceiling: 3.8,
  status: "healthy", out_weeks: 0, bye_week: 9, season_points: 0, games: 0, ...over,
});

const weeks = (n: number, from = 3) => Array.from({ length: n }, (_, i) => ({ week: from + i, projection: 2.2, floor: 0.6, ceiling: 3.8, bye: false, out: false }));

function detail(over: Partial<SimPlayerDetailResponse> = {}): SimPlayerDetailResponse {
  return {
    ok: true, reason: "", is_premium: true, upsell: null, preview: null, player: player({ value_rank: 211, pos_value_rank: 60 }), weeks: weeks(12), history: [], news: [],
    projection_flat: true, ros: { mean: 2.2, floor: 0.6, ceiling: 3.8, weeks_left: 12, playable_weeks: 11, bye_week: 9, out_weeks: [] }, ...over,
  } as SimPlayerDetailResponse;
}

describe("Fantasy Sim player sheet is the real Player Quick View", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders one rest-of-season line, no week-by-week list, and an initials avatar for a generated player", async () => {
    vi.mocked(api.getSimGamePlayer).mockResolvedValue(detail());
    render(<SimPlayerSheet gameId="g1" player={player()} onClose={() => {}} />);
    expect(await screen.findByTestId("sim-ros-line")).toHaveTextContent("Rest of season: 2.2 ppg (0.6-3.8)");
    expect(screen.queryByLabelText("Week-by-week projection")).toBeNull();
    expect(screen.queryByText("W3")).toBeNull();
    expect(screen.queryByText(/results so far/i)).toBeNull();
    expect(screen.queryByTestId("weekly-chart")).toBeNull(); // nothing played and a flat projection: no chart
    expect(screen.getByText("BB")).toBeInTheDocument(); // initials, same fallback as the real PQV
    expect(api.getPlayerQuickView).not.toHaveBeenCalled(); // a generated player has no real data
  });

  it("shows an em dash with a reason, not 0, for a player with no market value", async () => {
    vi.mocked(api.getSimGamePlayer).mockResolvedValue(detail());
    render(<SimPlayerSheet gameId="g1" player={player()} onClose={() => {}} />);
    const tile = await screen.findByTestId("pqv-value-empty");
    expect(tile).toHaveTextContent("—");
    expect(tile).toHaveTextContent(/no market value/i);
    await waitFor(() => expect(screen.getByText("Overall #211 · RB #60")).toBeInTheDocument());
  });

  it("plots this season's actual points through the shared weekly chart, with the band only when the projection varies", async () => {
    const history = [{ week: 1, points: 12.4 }, { week: 2, points: 3.1 }];
    vi.mocked(api.getSimGamePlayer).mockResolvedValue(detail({ history, projection_flat: true }));
    const { unmount } = render(<SimPlayerSheet gameId="g1" player={player()} onClose={() => {}} />);
    const flat = await screen.findByTestId("weekly-chart");
    expect(flat).toHaveAttribute("data-weeks", "2");
    expect(flat).toHaveAttribute("data-band", "0");
    unmount();

    const varied = weeks(3).map((w, i) => ({ ...w, projection: 8 + i }));
    vi.mocked(api.getSimGamePlayer).mockResolvedValue(detail({ history, weeks: varied, projection_flat: false }));
    render(<SimPlayerSheet gameId="g1" player={player()} onClose={() => {}} />);
    expect((await screen.findByTestId("weekly-chart")).getAttribute("data-band")).toBe("3");
  });
});
