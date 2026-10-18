import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PlayerQuickView } from "./PlayerQuickView";
import type { PlayerQuickViewIdentity } from "@/context/PlayerQuickViewContext";
import { api, type PlayerAwardsResponse, type QuickViewResponse } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      getPlayerQuickView: vi.fn(),
      getPlayerAwards: vi.fn(),
      getPlayerWeeklyStats: vi.fn(),
    },
  };
});

function identity(overrides: Partial<PlayerQuickViewIdentity> = {}): PlayerQuickViewIdentity {
  return {
    player_id: "p1",
    name: "Player One",
    position: "WR",
    team: "SF",
    age: 24,
    injury_status: null,
    tier: "starter",
    score: 1500,
    overall_rank: 12,
    position_rank: 4,
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

describe("PlayerQuickView", () => {
  beforeEach(() => {
    vi.mocked(api.getPlayerQuickView).mockReset();
    vi.mocked(api.getPlayerAwards).mockReset();
    vi.mocked(api.getPlayerWeeklyStats).mockReset();
    // Benign default (no weeks played) so tests unrelated to the weekly
    // chart don't need to mock this fetch themselves.
    vi.mocked(api.getPlayerWeeklyStats).mockResolvedValue({ ok: true, season: 2026, weeks: [] });
  });

  it("shows a loading state before the detail/awards requests resolve", async () => {
    vi.mocked(api.getPlayerQuickView).mockReturnValue(new Promise(() => {}));
    vi.mocked(api.getPlayerAwards).mockReturnValue(new Promise(() => {}));

    render(<PlayerQuickView identity={identity()} onClose={vi.fn()} />);

    expect(screen.getByText("Player One")).toBeInTheDocument();
    expect(screen.getByText(/Loading player detail/)).toBeInTheDocument();
  });

  it("renders stats, model sub-ratings, decision fit, awards, and bio once loaded", async () => {
    vi.mocked(api.getPlayerQuickView).mockResolvedValue(quickView());
    vi.mocked(api.getPlayerAwards).mockResolvedValue(awardsResult());

    render(<PlayerQuickView identity={identity()} onClose={vi.fn()} />);

    await waitFor(() => expect(api.getPlayerQuickView).toHaveBeenCalledWith("p1"));
    await waitFor(() => expect(api.getPlayerAwards).toHaveBeenCalledWith("p1"));

    await waitFor(() => expect(screen.queryByText(/Loading player detail/)).not.toBeInTheDocument());

    expect(screen.getByText(/Market value \(92nd percentile at WR\)/)).toBeInTheDocument();
    expect(screen.getByText("MKT")).toBeInTheDocument();
    expect(screen.getByText("91")).toBeInTheDocument();
    expect(screen.getByText("Targets")).toBeInTheDocument();
    expect(screen.getByText("140")).toBeInTheDocument();
    expect(screen.getByText(/88th pct/)).toBeInTheDocument();
    expect(screen.getByText(/Top-3 WR/)).toBeInTheDocument();
    expect(screen.getByText("Ohio State")).toBeInTheDocument();

    // coridian_, 2026-10-18: "Starter and usage still need to be color
    // coordinated" — the tier chip matches the avatar's own prestige-ring
    // color (same resolvePlayerTier source), and the usage chip carries
    // its real positive/negative tone instead of the same flat gray as
    // every other inert chip.
    const tierChip = screen.getByText("starter");
    expect(tierChip.style.color).toBe("var(--color-tier-starter)");
    const usageChip = screen.getByText(/12% usage/);
    expect(usageChip.className).toContain("pqv-chip--positive");
  });

  it("shows the week-by-week points chart once weekly stats load", async () => {
    vi.mocked(api.getPlayerQuickView).mockResolvedValue(quickView());
    vi.mocked(api.getPlayerAwards).mockResolvedValue(awardsResult());
    vi.mocked(api.getPlayerWeeklyStats).mockResolvedValue({
      ok: true,
      season: 2026,
      weeks: [
        { week: 1, fantasy_points_ppr: 18.4, snap_share: 0.82 },
        { week: 2, fantasy_points_ppr: 9.1, snap_share: 0.7 },
      ],
    });

    render(<PlayerQuickView identity={identity()} onClose={vi.fn()} />);

    await waitFor(() => expect(api.getPlayerWeeklyStats).toHaveBeenCalledWith("p1"));
    expect(await screen.findByText("Week by Week")).toBeInTheDocument();
  });

  it("omits the week-by-week section when no weeks have been played yet", async () => {
    vi.mocked(api.getPlayerQuickView).mockResolvedValue(quickView());
    vi.mocked(api.getPlayerAwards).mockResolvedValue(awardsResult());
    vi.mocked(api.getPlayerWeeklyStats).mockResolvedValue({
      ok: true,
      season: 2026,
      weeks: [{ week: 1, fantasy_points_ppr: null, snap_share: null }],
    });

    render(<PlayerQuickView identity={identity()} onClose={vi.fn()} />);

    await waitFor(() => expect(screen.queryByText(/Loading player detail/)).not.toBeInTheDocument());
    expect(screen.queryByText("Week by Week")).not.toBeInTheDocument();
  });

  it("calls onClose on Escape, backdrop click, and the close button", async () => {
    vi.mocked(api.getPlayerQuickView).mockResolvedValue(quickView());
    vi.mocked(api.getPlayerAwards).mockResolvedValue(awardsResult());
    const onClose = vi.fn();

    render(<PlayerQuickView identity={identity()} onClose={onClose} />);
    await waitFor(() => expect(screen.queryByText(/Loading player detail/)).not.toBeInTheDocument());

    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByLabelText("Close player details"));
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  it("shows a graceful message when the player has no quick-view data", async () => {
    vi.mocked(api.getPlayerQuickView).mockResolvedValue({ ok: true, stats: null, bio: null, model: null, reason: "not_found" });
    vi.mocked(api.getPlayerAwards).mockResolvedValue({ ok: true, awards: [], reason: "not_found" });

    render(<PlayerQuickView identity={identity()} onClose={vi.fn()} />);
    await waitFor(() => expect(screen.queryByText(/Loading player detail/)).not.toBeInTheDocument());

    expect(screen.queryByText("Awards")).not.toBeInTheDocument();
    expect(screen.queryByText("Model")).not.toBeInTheDocument();
    expect(screen.getByText("Player One")).toBeInTheDocument();
  });

  it("renders a Compare link only when leagueId is provided", async () => {
    vi.mocked(api.getPlayerQuickView).mockResolvedValue(quickView());
    vi.mocked(api.getPlayerAwards).mockResolvedValue(awardsResult());

    const { rerender } = render(<PlayerQuickView identity={identity()} onClose={vi.fn()} />);
    await waitFor(() => expect(screen.queryByText(/Loading player detail/)).not.toBeInTheDocument());
    expect(screen.queryByText("Compare this player")).not.toBeInTheDocument();

    rerender(
      <PlayerQuickView identity={identity({ leagueId: "league-1", leagueName: "My League" })} onClose={vi.fn()} />,
    );
    const link = screen.getByText("Compare this player");
    expect(link.closest("a")).toHaveAttribute("href", "/player-compare/league-1?a=p1&name=My%20League");
  });
});
