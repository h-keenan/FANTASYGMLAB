import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
  return { ...actual, api: { ...actual.api, getSimGamePlayer: vi.fn(), getSimPlayerHistory: vi.fn(), getPlayerQuickView: vi.fn(), getPlayerAwards: vi.fn(), getPlayerWeeklyStats: vi.fn(), getPlayerNews: vi.fn() } };
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
  beforeEach(() => { vi.clearAllMocks(); window.sessionStorage.clear(); });

  it("renders one rest-of-season line, no week-by-week list, and an initials avatar for a generated player", async () => {
    vi.mocked(api.getSimGamePlayer).mockResolvedValue(detail());
    render(<SimPlayerSheet gameId="g1" player={player()} onClose={() => {}} />);
    fireEvent.click(await screen.findByRole("tab", { name: "Outlook" }));
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
    fireEvent.click(await screen.findByRole("tab", { name: "Outlook" }));
    const flat = await screen.findByTestId("weekly-chart");
    expect(flat).toHaveAttribute("data-weeks", "2");
    expect(flat).toHaveAttribute("data-band", "0");
    unmount();

    const varied = weeks(3).map((w, i) => ({ ...w, projection: 8 + i }));
    vi.mocked(api.getSimGamePlayer).mockResolvedValue(detail({ history, weeks: varied, projection_flat: false }));
    render(<SimPlayerSheet gameId="g1" player={player()} onClose={() => {}} />);
    fireEvent.click(await screen.findByRole("tab", { name: "Outlook" }));
    expect((await screen.findByTestId("weekly-chart")).getAttribute("data-band")).toBe("3");
  });

  it("is a tabbed sheet: Overview, Outlook and History for a generated player (no real Stats / Profile), Scouting for a rookie", async () => {
    vi.mocked(api.getSimGamePlayer).mockResolvedValue(detail({ scouting: { version: 1, source: "generated", label: "Generated prospect", school: "Summit Tech", class_year: 2027, position_word: "running back", draft: { round: 1, pick: 12, class_rank: 5, class_size: 60, basis: "" }, measurables: [], college: { columns: [], seasons: [], career: {}, percentiles: {}, final: { season: 2026, team: "Summit Tech", games: 13, stats: {} } }, analytics: [], tags: [], blurb: "A prospect.", development: { base_year: 1, points: [], confidence: 0.4, confidence_label: "Medium", archetype: null, archetype_label: null, revealed: false, note: "" } } } as never));
    render(<SimPlayerSheet gameId="g1" player={player()} onClose={() => {}} />);
    const tabs = await screen.findAllByRole("tab");
    expect(tabs.map((t) => t.textContent)).toEqual(expect.arrayContaining(["Overview", "Outlook", "History"]));
    expect(screen.queryByRole("tab", { name: "Stats" })).toBeNull();
    expect(await screen.findByRole("tab", { name: "Scouting" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Overview" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("sim-in-game")).toBeInTheDocument();
  });

  it("History tab shows the draft slot, moves and seasons from the event-log endpoint, fetched only when opened", async () => {
    vi.mocked(api.getSimGamePlayer).mockResolvedValue(detail());
    const origin = { kind: "drafted", season: 1, year: 2026, week: 0, offseason: false, team_id: "9", team_name: "Hail Marys", round: 3, pick: 31, auto: false, draft: "league" };
    vi.mocked(api.getSimPlayerHistory).mockResolvedValue({
      ok: true, reason: "", pid: "R2027-001", name: "Brock Briggs", origin, current_team: { team_id: "3", team_name: "Bench Mob" },
      entries: [origin, { kind: "traded", season: 1, year: 2026, week: 6, offseason: false, team_id: "3", team_name: "Bench Mob", from_team: { team_id: "9", team_name: "Hail Marys" }, to_team: { team_id: "3", team_name: "Bench Mob" }, with_assets: [{ id: "x", name: "Ace Receiver", pos: "WR" }] }],
      seasons: [{ season: 1, year: 2026, games: 8, points: 121.4, ppg: 15.2, teams: [{ team_id: "9", team_name: "Hail Marys", games: 5, points: 70.1, ppg: 14 }, { team_id: "3", team_name: "Bench Mob", games: 3, points: 51.3, ppg: 17.1 }] }],
    } as never);
    render(<SimPlayerSheet gameId="g1" player={player()} onClose={() => {}} />);
    await screen.findByRole("tab", { name: "History" });
    expect(api.getSimPlayerHistory).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("tab", { name: "History" }));
    const origin_ = await screen.findByRole("region", { name: "Origin" });
    expect(origin_).toHaveTextContent("Round 3, pick 31 overall");
    expect(origin_).toHaveTextContent("Hail Marys");
    expect(origin_).toHaveTextContent("Now with Bench Mob");
    expect(screen.getByRole("region", { name: "Moves" })).toHaveTextContent("Traded from Hail Marys to Bench Mob for Ace Receiver");
    expect(screen.getByRole("region", { name: "Seasons" })).toHaveTextContent("8 games · 121.4 pts · 15.2 ppg");
    expect(api.getSimPlayerHistory).toHaveBeenCalledWith("g1", "R2027-001");
  });

  it("header carries the list row's tags once: the injury chip, Free agent, and no separate Health chip", async () => {
    const hurt = player({ status: "out", out_weeks: 3, owner: { type: "free_agent" } as SimGamePlayer["owner"] });
    vi.mocked(api.getSimGamePlayer).mockResolvedValue(detail({ player: hurt }));
    render(<SimPlayerSheet gameId="g1" player={hurt} onClose={() => {}} />);
    const strip = await screen.findByTestId("pqv-badges");
    const badges = Array.from(strip.querySelectorAll("[data-badge]"));
    expect(badges.map((b) => b.getAttribute("aria-label"))).toEqual(["Out: 3 wks", "Free agent"]);
    expect(screen.queryByText(/Health:/)).toBeNull();
  });

  it("a real player's Stats tab shows prior seasons up to the as-of season and that season's game log, never the one in progress", async () => {
    const real = player({ id: "4046", headshot_id: "4046", name: "Real Guy", pos: "QB" });
    vi.mocked(api.getSimGamePlayer).mockResolvedValue(detail({ player: real }));
    vi.mocked(api.getPlayerQuickView).mockResolvedValue({ ok: true } as never);
    vi.mocked(api.getPlayerAwards).mockResolvedValue({ ok: true, awards: [] } as never);
    vi.mocked(api.getPlayerNews).mockResolvedValue({ ok: true, items: [] } as never);
    vi.mocked(api.getPlayerWeeklyStats).mockResolvedValue({ ok: true, season: 2025, weeks: [{ week: 1, fantasy_points_ppr: 21.5, snap_share: null }, { week: 2, fantasy_points_ppr: 9, snap_share: null }] });
    const career = vi.spyOn(api, "getPlayerCareer").mockResolvedValue({
      ok: true,
      seasons: [
        { season: 2026, age: 29, games: 4, current_season: true, key_stats: [{ label: "Pass TD", value: "9" }] },
        { season: 2025, age: 28, games: 17, current_season: false, key_stats: [{ label: "Pass TD", value: "31" }] },
        { season: 2024, age: 27, games: 16, current_season: false, key_stats: [] },
      ],
    });
    render(<SimPlayerSheet gameId="g1" player={real} onClose={() => {}} startYear={2026} />);
    fireEvent.click(await screen.findByRole("tab", { name: "Stats" }));
    const careerBlock = await screen.findByTestId("sim-career");
    expect(careerBlock).toHaveTextContent("2025 · 17 games");
    expect(careerBlock).toHaveTextContent("2024 · 16 games");
    expect(careerBlock).not.toHaveTextContent("2026");
    expect(await screen.findByTestId("sim-game-log")).toHaveTextContent("2 games");
    expect(api.getPlayerWeeklyStats).toHaveBeenCalledWith("4046", 2025);
    career.mockRestore();
  });
});
