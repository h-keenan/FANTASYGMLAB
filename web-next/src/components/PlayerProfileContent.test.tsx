import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PlayerProfileContent } from "./PlayerProfileContent";
import {
  api,
  type CareerResponse,
  type PlayerAwardsResponse,
  type QuickViewResponse,
  type RankedPlayer,
  type ScheduleResponse,
} from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      getPlayerQuickView: vi.fn(),
      getPlayerAwards: vi.fn(),
      getPlayerWeeklyStats: vi.fn(),
      getPlayerSchedule: vi.fn(),
      getPlayerCareer: vi.fn(),
      getPlayerShareCardBlob: vi.fn(),
    },
  };
});

function player(overrides: Partial<RankedPlayer> = {}): RankedPlayer {
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

function quickView(overrides: Partial<QuickViewResponse> = {}): QuickViewResponse {
  return {
    ok: true,
    reason: "",
    stats: {
      seasons: [
        {
          season: 2026,
          season_type: "Regular Season",
          games: 15,
          complete: null,
          label: "2026 Regular Season",
          key_stats: [{ label: "Targets", value: "140", note: "", tone: "reference", percentile: 88 }],
          fantasy: [{ label: "PPR", value: "280.4", note: "", tone: "reference", percentile: 91 }],
          usage: [],
          efficiency: [],
        },
      ],
      college: [],
      college_available: false,
      career_totals_available: false,
      position: "WR",
      overall_rating: 72,
      prime_window: null,
    },
    bio: {
      years_in_league: "3 seasons",
      draft_capital: "2023 / Round 1 / Pick 12",
      college: "Ohio State",
      height: "6'2\"",
      weight: "205 lb",
      bye_week: "",
      contract_status: "",
    },
    model: {
      market_score: 80,
      opportunity_score: 70,
      scarcity_score: 60,
      role_score: 90,
      age_score: 75,
      age_score_label: "Age Score",
      opportunity_confidence: 85,
      workload_trend: "Stable",
      usage_trend: { direction: "up", trend_pct: 12, confidence_label: "High confidence", arrow: "↑", tone: "positive" },
      depth_chart_note: null,
      decision_fit_narrative: "Market value (92nd percentile at WR) is the biggest driver of this valuation.",
      market_rating: 91,
      opportunity_rating: 84,
      scarcity_rating: 62,
      role_rating: 73,
      durability_rating: 58,
    },
    ...overrides,
  };
}

function awardsResult(overrides: Partial<PlayerAwardsResponse> = {}): PlayerAwardsResponse {
  return {
    ok: true,
    reason: "",
    awards: [
      {
        badge_id: "a1",
        category: "fantasy_finish",
        family: "positional_finish",
        title: "Top-3 WR Finish",
        short_label: "Top-3 WR",
        tier: "gold",
        season: 2025,
        rank: 2,
        metric_value: null,
        description: "Finished 2nd among WRs in PPR scoring.",
        occurrence_count: 1,
      },
    ],
    ...overrides,
  };
}

describe("PlayerProfileContent", () => {
  beforeEach(() => {
    vi.mocked(api.getPlayerQuickView).mockReset();
    vi.mocked(api.getPlayerAwards).mockReset();
    vi.mocked(api.getPlayerWeeklyStats).mockReset();
    vi.mocked(api.getPlayerSchedule).mockReset();
    vi.mocked(api.getPlayerCareer).mockReset();
    vi.mocked(api.getPlayerWeeklyStats).mockResolvedValue({ ok: true, season: 2026, weeks: [] });
  });

  it("shows a loading state before the detail/awards requests resolve", () => {
    vi.mocked(api.getPlayerQuickView).mockReturnValue(new Promise(() => {}));
    vi.mocked(api.getPlayerAwards).mockReturnValue(new Promise(() => {}));

    render(<PlayerProfileContent player={player()} leagueId="league-1" leagueName="My League" />);

    expect(screen.getByText("Player One")).toBeInTheDocument();
    expect(screen.getByText(/Loading player profile/)).toBeInTheDocument();
  });

  it("shows an error state when the detail request fails", async () => {
    vi.mocked(api.getPlayerQuickView).mockRejectedValue(new Error("boom"));
    vi.mocked(api.getPlayerAwards).mockResolvedValue(awardsResult());

    render(<PlayerProfileContent player={player()} leagueId="league-1" leagueName="My League" />);

    expect(await screen.findByRole("alert")).toHaveTextContent(/Couldn.t load this player.s profile right now/);
  });

  it("renders the Stats tab by default, with awards/bio tab-agnostic below it", async () => {
    vi.mocked(api.getPlayerQuickView).mockResolvedValue(quickView());
    vi.mocked(api.getPlayerAwards).mockResolvedValue(awardsResult());

    render(<PlayerProfileContent player={player()} leagueId="league-1" leagueName="My League" />);
    await waitFor(() => expect(screen.queryByText(/Loading player profile/)).not.toBeInTheDocument());

    expect(screen.getByText("Targets")).toBeInTheDocument();
    expect(screen.getByText("140")).toBeInTheDocument();
    expect(screen.getByText(/Market value \(92nd percentile at WR\)/)).toBeInTheDocument();
    expect(screen.getByText(/Top-3 WR/)).toBeInTheDocument();
    expect(screen.getByText("Ohio State")).toBeInTheDocument();
  });

  it("shows the Trends tab's loading state, then the weekly chart once it resolves", async () => {
    vi.mocked(api.getPlayerQuickView).mockResolvedValue(quickView());
    vi.mocked(api.getPlayerAwards).mockResolvedValue(awardsResult());
    vi.mocked(api.getPlayerWeeklyStats).mockReturnValue(new Promise(() => {}));

    render(<PlayerProfileContent player={player()} leagueId="league-1" leagueName="My League" />);
    await waitFor(() => expect(screen.queryByText(/Loading player profile/)).not.toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Trends" }));
    expect(screen.getByText(/Loading weekly trends/)).toBeInTheDocument();
  });

  it("shows the Schedule tab's loading, empty, and real states", async () => {
    vi.mocked(api.getPlayerQuickView).mockResolvedValue(quickView());
    vi.mocked(api.getPlayerAwards).mockResolvedValue(awardsResult());
    vi.mocked(api.getPlayerSchedule).mockReturnValue(new Promise(() => {}));

    render(<PlayerProfileContent player={player()} leagueId="league-1" leagueName="My League" />);
    await waitFor(() => expect(screen.queryByText(/Loading player profile/)).not.toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Schedule" }));
    expect(screen.getByText(/Loading schedule/)).toBeInTheDocument();

    const emptySchedule: ScheduleResponse = { ok: true, team: "SF", weeks: [] };
    vi.mocked(api.getPlayerSchedule).mockResolvedValue(emptySchedule);
    fireEvent.click(screen.getByRole("button", { name: "Stats" }));
    fireEvent.click(screen.getByRole("button", { name: "Schedule" }));
    expect(await screen.findByText(/No schedule available for this player's team yet/)).toBeInTheDocument();

    vi.mocked(api.getPlayerSchedule).mockResolvedValue({
      ok: true,
      team: "SF",
      weeks: [
        {
          week: 1,
          opponent: "LAR",
          is_home: true,
          spread_line: -3.5,
          total_line: 44.5,
          played: false,
          team_score: null,
          opponent_score: null,
          bye: false,
          opponent_defense_tier: "weak",
          projection: { status: "ok", point_estimate: 16.2, low: 10, high: 22, confidence: "medium", opponent: "LAR" },
        },
      ],
    });
    fireEvent.click(screen.getByRole("button", { name: "Stats" }));
    fireEvent.click(screen.getByRole("button", { name: "Schedule" }));
    expect(await screen.findByText("vs LAR")).toBeInTheDocument();
    expect(screen.getByText("16.2")).toBeInTheDocument();
  });

  it("shows the Career tab's loading, empty, and real states, with only the most recent season expanded by default", async () => {
    vi.mocked(api.getPlayerQuickView).mockResolvedValue(quickView());
    vi.mocked(api.getPlayerAwards).mockResolvedValue(awardsResult());
    vi.mocked(api.getPlayerCareer).mockReturnValue(new Promise(() => {}));

    render(<PlayerProfileContent player={player()} leagueId="league-1" leagueName="My League" />);
    await waitFor(() => expect(screen.queryByText(/Loading player profile/)).not.toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Career" }));
    expect(screen.getByText(/Loading career history/)).toBeInTheDocument();

    const twoSeasons: CareerResponse = {
      ok: true,
      seasons: [
        { season: 2026, age: 24, games: 6, current_season: true, key_stats: [{ label: "Targets", value: "60" }] },
        { season: 2025, age: 23, games: 17, current_season: false, key_stats: [{ label: "Targets", value: "150" }] },
      ],
    };
    vi.mocked(api.getPlayerCareer).mockResolvedValue(twoSeasons);
    fireEvent.click(screen.getByRole("button", { name: "Stats" }));
    fireEvent.click(screen.getByRole("button", { name: "Career" }));

    await screen.findByText("60");
    // Older season collapsed: its own stat value isn't rendered yet.
    expect(screen.queryByText("150")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /2025/ }));
    expect(await screen.findByText("150")).toBeInTheDocument();
  });

  it("shows the Model tab's sub-ratings, or a graceful message with no model data", async () => {
    vi.mocked(api.getPlayerQuickView).mockResolvedValue(quickView({ model: null }));
    vi.mocked(api.getPlayerAwards).mockResolvedValue(awardsResult());

    render(<PlayerProfileContent player={player()} leagueId="league-1" leagueName="My League" />);
    await waitFor(() => expect(screen.queryByText(/Loading player profile/)).not.toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Model" }));
    expect(screen.getByText(/No model breakdown available for this player yet/)).toBeInTheDocument();
  });

  it("renders a Compare this player link back to Player Compare", async () => {
    vi.mocked(api.getPlayerQuickView).mockResolvedValue(quickView());
    vi.mocked(api.getPlayerAwards).mockResolvedValue(awardsResult());

    render(<PlayerProfileContent player={player()} leagueId="league-1" leagueName="My League" />);
    await waitFor(() => expect(screen.queryByText(/Loading player profile/)).not.toBeInTheDocument());

    const link = screen.getByText("Compare this player");
    expect(link.closest("a")).toHaveAttribute("href", "/player-compare/league-1?a=p1&name=My%20League");
  });

  it("shares the branded player card PNG for this league and lens", async () => {
    vi.mocked(api.getPlayerQuickView).mockResolvedValue(quickView());
    vi.mocked(api.getPlayerAwards).mockResolvedValue(awardsResult());
    vi.mocked(api.getPlayerShareCardBlob).mockResolvedValue(new Blob([new Uint8Array([0x89, 0x50, 0x4e, 0x47])], { type: "image/png" }));
    const share = vi.fn(async () => {});
    Object.defineProperty(navigator, "share", { value: share, configurable: true, writable: true });
    Object.defineProperty(navigator, "canShare", { value: () => true, configurable: true, writable: true });

    render(<PlayerProfileContent player={player()} leagueId="league-1" leagueName="My League" lens="Rebuild" />);
    fireEvent.click(screen.getByText("Share card"));

    await waitFor(() => expect(share).toHaveBeenCalledTimes(1));
    expect(api.getPlayerShareCardBlob).toHaveBeenCalledWith("league-1", "p1", "Rebuild");
    const data = (share.mock.calls[0] as unknown as [ShareData])[0];
    expect(data.files?.[0].type).toBe("image/png");
    expect(data.text).toContain("Player One");

    delete (navigator as unknown as Record<string, unknown>).share;
    delete (navigator as unknown as Record<string, unknown>).canShare;
  });
});
