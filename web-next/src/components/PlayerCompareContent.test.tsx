import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PlayerCompareContent } from "./PlayerCompareContent";
import type { QuickViewModel, QuickViewResponse, RankedPlayer, WeeklyStatsResponse } from "@/lib/api";
import { api } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      getPlayerQuickView: vi.fn(),
      getPlayerWeeklyStats: vi.fn(),
      getPlayerSchedule: vi.fn(),
      searchLeaguePlayers: vi.fn(),
    },
  };
});

function player(overrides: Partial<RankedPlayer>): RankedPlayer {
  return {
    player_id: "p1",
    name: "Player One",
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

function model(overrides: Partial<QuickViewModel>): QuickViewModel {
  return {
    market_score: 80,
    opportunity_score: 70,
    scarcity_score: 60,
    role_score: 90,
    age_score: 75,
    age_score_label: "Age Score",
    opportunity_confidence: 85,
    workload_trend: null,
    usage_trend: null,
    depth_chart_note: null,
    decision_fit_narrative: null,
    ...overrides,
  };
}

function quickViewResult(m: QuickViewModel): QuickViewResponse {
  return { ok: true, stats: null, bio: null, model: m, reason: "" };
}

function weeklyStatsResult(weeks: WeeklyStatsResponse["weeks"], season = 2026): WeeklyStatsResponse {
  return { ok: true, season, weeks };
}

const PLAYER_A = player({ player_id: "p1", name: "Player One", score: 1500, overall_rank: 12, position_rank: 4, age: 24 });
const PLAYER_B = player({ player_id: "p2", name: "Player Two", score: 1200, overall_rank: 30, position_rank: 10, age: 27 });
const POOL = [PLAYER_A, PLAYER_B, player({ player_id: "p3", name: "Player Three" })];

describe("PlayerCompareContent", () => {
  beforeEach(() => {
    // Every existing test below picks an opponent without caring about the
    // Points By Week chart — default both sides to "no weekly rows yet" so
    // those tests see the same empty-weeks behavior they always have,
    // without each needing its own getPlayerWeeklyStats mock.
    vi.mocked(api.getPlayerWeeklyStats).mockResolvedValue(weeklyStatsResult([]));
    vi.mocked(api.getPlayerSchedule).mockResolvedValue({ ok: true, team: "SF", weeks: [] });
    window.localStorage.clear();
  });

  it("shows two big slots with Player A filled and a Choose a player slot, plus one-tap suggestions", () => {
    render(<PlayerCompareContent leagueId="L1" leagueName="Dynasty Overlords" playerA={PLAYER_A} initialPlayerB={null} pool={POOL} />);

    expect(within(screen.getByTestId("compare-slot-a")).getByText("Player One")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Player B: choose a player" })).toBeInTheDocument();
    // Same-position, nearest-value suggestions as chips (never the base player).
    const suggested = screen.getByRole("region", { name: "Suggested" });
    expect(within(suggested).getByRole("button", { name: "Compare with Player Two" })).toBeInTheDocument();
    expect(within(suggested).queryByText("Player One")).not.toBeInTheDocument();
  });

  it("a suggestion chip compares in one tap and is remembered as a recent opponent", async () => {
    vi.mocked(api.getPlayerQuickView).mockResolvedValue(quickViewResult(model({})));
    render(<PlayerCompareContent leagueId="L1" leagueName="Dynasty Overlords" playerA={PLAYER_A} initialPlayerB={null} pool={POOL} />);

    fireEvent.click(screen.getByRole("button", { name: "Compare with Player Two" }));

    expect(await screen.findByTestId("compare-grid")).toBeInTheDocument();
    await waitFor(() => expect(api.getPlayerQuickView).toHaveBeenCalledWith("p2"));
    expect(JSON.parse(window.localStorage.getItem("fgl:compare-recent:L1") ?? "[]")).toEqual(["p2"]);
  });

  it("opens the shared picker pre-filtered to the same position and chooses with one tap", async () => {
    vi.mocked(api.getPlayerQuickView).mockResolvedValue(quickViewResult(model({})));
    const qb = player({ player_id: "p9", name: "Qb Nine", position: "QB", score: 900 });
    render(<PlayerCompareContent leagueId="L1" leagueName="Dynasty Overlords" playerA={PLAYER_A} initialPlayerB={null} pool={[...POOL, qb]} />);

    fireEvent.click(screen.getByRole("button", { name: "Player B: choose a player" }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByRole("button", { name: "Filters (1)" })).toBeInTheDocument();
    // WR is pre-selected, so the QB is hidden until the filter is cleared.
    expect(within(dialog).queryByRole("button", { name: "Choose Qb Nine" })).not.toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: "Clear filters" }));
    expect(within(dialog).getByRole("button", { name: "Choose Qb Nine" })).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: "Choose Qb Nine" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(await screen.findByTestId("compare-grid")).toBeInTheDocument();
    expect(within(screen.getByTestId("compare-slot-b")).getByText("Qb Nine")).toBeInTheDocument();
  });

  it("finds a player outside the loaded pool through the server search", async () => {
    const deep = player({ player_id: "p650", name: "Carson Beck", position: "WR", team: "ARI" });
    vi.mocked(api.searchLeaguePlayers).mockResolvedValue({ ok: true, players: [deep] } as never);
    render(<PlayerCompareContent leagueId="L1" leagueName="Dynasty Overlords" playerA={PLAYER_A} initialPlayerB={null} pool={POOL} />);

    fireEvent.click(screen.getByRole("button", { name: "Player B: choose a player" }));
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "beck" } });

    expect(await screen.findByRole("button", { name: "Choose Carson Beck" })).toBeInTheDocument();
    expect(api.searchLeaguePlayers).toHaveBeenCalledWith("L1", "beck", "Dynasty");
  });

  it("never offers the base player as their own opponent", () => {
    render(<PlayerCompareContent leagueId="L1" leagueName="Dynasty Overlords" playerA={PLAYER_A} initialPlayerB={null} pool={POOL} />);
    fireEvent.click(screen.getByRole("button", { name: "Player B: choose a player" }));
    expect(screen.queryByRole("button", { name: "Choose Player One" })).not.toBeInTheDocument();
  });

  it("renders every row (identity + each stat row) on the same fixed 3-column grid, so values line up at the same x-position", async () => {
    vi.mocked(api.getPlayerQuickView).mockImplementation((playerId: string) =>
      Promise.resolve(quickViewResult(model(playerId === "p1" ? {} : { market_score: 40 }))),
    );

    render(
      <PlayerCompareContent leagueId="L1" leagueName="Dynasty Overlords" playerA={PLAYER_A} initialPlayerB={PLAYER_B} pool={POOL} />,
    );

    await waitFor(() => expect(screen.getByText("Value Score")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /More stats/ }));
    await waitFor(() => expect(screen.getByText("Market")).toBeInTheDocument());

    const gridRows = document.querySelectorAll("[data-compare-grid-row]");
    // 6 headline rows + 6 Model Breakdown rows.
    expect(gridRows.length).toBeGreaterThanOrEqual(12);
    gridRows.forEach((row) => {
      expect(row.className).toContain("grid-cols-[1fr_6.5rem_1fr]");
    });
  });

  it("highlights the winning side of a numeric row without relying on color alone", async () => {
    vi.mocked(api.getPlayerQuickView).mockResolvedValue(quickViewResult(model({})));

    render(
      <PlayerCompareContent leagueId="L1" leagueName="Dynasty Overlords" playerA={PLAYER_A} initialPlayerB={PLAYER_B} pool={POOL} />,
    );

    await waitFor(() => expect(within(screen.getByTestId("compare-grid")).getByText("1,500")).toBeInTheDocument());
    // Player A's Value Score (1500) beats Player B's (1200); the winner is marked in text, not color alone.
    expect(screen.getAllByText("Better:").length).toBeGreaterThan(0);
    // Age is shown without a winner (which age is better depends on the league).
    const ageRow = screen.getByText("Age").closest("[data-compare-grid-row]") as HTMLElement;
    expect(within(ageRow).queryByText("Better:")).not.toBeInTheDocument();
  });

  it("shows PPG, next-game projection and the schedule outlook with the better side marked", async () => {
    vi.mocked(api.getPlayerQuickView).mockResolvedValue(quickViewResult(model({})));
    vi.mocked(api.getPlayerWeeklyStats).mockImplementation((id: string) =>
      Promise.resolve(weeklyStatsResult([{ week: 1, fantasy_points_ppr: id === "p1" ? 20 : 10, snap_share: 0.8 }])),
    );
    const week = (tier: "weak" | "tough", pts: number) =>
      ({ week: 10, opponent: "DAL", is_home: true, spread_line: null, total_line: null, played: false, team_score: null, opponent_score: null, bye: false, opponent_defense_tier: tier, projection: { status: "ok", point_estimate: pts, low: 1, high: 30, confidence: "medium", opponent: "DAL" } }) as never;
    vi.mocked(api.getPlayerSchedule).mockImplementation((id: string) =>
      Promise.resolve({ ok: true, team: "SF", weeks: [week(id === "p1" ? "tough" : "weak", id === "p1" ? 11 : 14)] }),
    );

    render(<PlayerCompareContent leagueId="L1" leagueName="Dynasty Overlords" playerA={PLAYER_A} initialPlayerB={PLAYER_B} pool={POOL} />);

    const grid = await screen.findByTestId("compare-grid");
    await waitFor(() => expect(within(grid).getByText("20.0")).toBeInTheDocument());
    expect(within(grid).getByText("14.0")).toBeInTheDocument();
    expect(within(grid).getByText("1 soft")).toBeInTheDocument();
    expect(within(grid).getByText("1 tough")).toBeInTheDocument();
  });

  it("collapses the extra stats behind More stats", async () => {
    vi.mocked(api.getPlayerQuickView).mockResolvedValue(quickViewResult(model({})));
    render(<PlayerCompareContent leagueId="L1" leagueName="Dynasty Overlords" playerA={PLAYER_A} initialPlayerB={PLAYER_B} pool={POOL} />);
    await waitFor(() => expect(api.getPlayerQuickView).toHaveBeenCalled());
    const toggle = await screen.findByRole("button", { name: /More stats/ });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("Model Breakdown")).not.toBeInTheDocument();
    fireEvent.click(toggle);
    expect(await screen.findByText("Model Breakdown")).toBeInTheDocument();
  });

  it("Change on a slot swaps that player", async () => {
    vi.mocked(api.getPlayerQuickView).mockResolvedValue(quickViewResult(model({})));
    render(<PlayerCompareContent leagueId="L1" leagueName="Dynasty Overlords" playerA={PLAYER_A} initialPlayerB={PLAYER_B} pool={POOL} />);
    fireEvent.click(screen.getByRole("button", { name: "Player B: Player Two. Change player" }));
    fireEvent.click(screen.getByRole("button", { name: "Choose Player Three" }));
    expect(within(screen.getByTestId("compare-slot-b")).getByText("Player Three")).toBeInTheDocument();
  });

  it("omits the Model Breakdown section when neither side has model data", async () => {
    vi.mocked(api.getPlayerQuickView).mockResolvedValue({ ok: true, stats: null, bio: null, model: null, reason: "not_found" });

    render(
      <PlayerCompareContent leagueId="L1" leagueName="Dynasty Overlords" playerA={PLAYER_A} initialPlayerB={PLAYER_B} pool={POOL} />,
    );

    await waitFor(() => expect(api.getPlayerQuickView).toHaveBeenCalled());
    expect(screen.queryByRole("button", { name: /More stats/ })).not.toBeInTheDocument();
    // The headline grid always renders — it never depends on the quick-view fetch.
    expect(screen.getByText("Value Score")).toBeInTheDocument();
  });

  it("fetches both sides' weekly stats and renders the Points By Week chart once either side has played weeks", async () => {
    vi.mocked(api.getPlayerQuickView).mockResolvedValue(quickViewResult(model({})));
    vi.mocked(api.getPlayerWeeklyStats).mockImplementation((playerId: string) =>
      Promise.resolve(
        weeklyStatsResult(
          playerId === "p1"
            ? [
                { week: 1, fantasy_points_ppr: 12.4, snap_share: 0.8 },
                { week: 2, fantasy_points_ppr: 22.1, snap_share: 0.9 },
              ]
            : [],
        ),
      ),
    );

    render(
      <PlayerCompareContent leagueId="L1" leagueName="Dynasty Overlords" playerA={PLAYER_A} initialPlayerB={PLAYER_B} pool={POOL} />,
    );

    await waitFor(() => expect(api.getPlayerWeeklyStats).toHaveBeenCalledWith("p1"));
    expect(api.getPlayerWeeklyStats).toHaveBeenCalledWith("p2");
    fireEvent.click(await screen.findByRole("button", { name: /More stats/ }));
    await waitFor(() => expect(screen.getByText("Points By Week")).toBeInTheDocument());
    // Both player-name labels render (one per panel), even though only
    // Player One actually has weeks to chart.
    expect(screen.getAllByText("Player One").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Player Two").length).toBeGreaterThan(0);
  });

  it("omits the Points By Week section when neither side has any played weeks", async () => {
    vi.mocked(api.getPlayerQuickView).mockResolvedValue(quickViewResult(model({})));
    vi.mocked(api.getPlayerWeeklyStats).mockResolvedValue(weeklyStatsResult([]));

    render(
      <PlayerCompareContent leagueId="L1" leagueName="Dynasty Overlords" playerA={PLAYER_A} initialPlayerB={PLAYER_B} pool={POOL} />,
    );

    await waitFor(() => expect(api.getPlayerWeeklyStats).toHaveBeenCalled());
    expect(screen.queryByText("Points By Week")).not.toBeInTheDocument();
  });
});
