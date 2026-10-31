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

  // coridian_, 2026-10-20: "it expands the background of the PQV as those
  // modules load in and looks very clunky" — instead of a single bare
  // status line, the loading body now renders a skeleton shaped like the
  // eventual content (a chart-height placeholder plus stat-tile grids
  // reusing the real .pqv-stat-row/.pqv-stat-grid classes) so the modal's
  // height is already roughly reserved and swapping in the real content
  // doesn't visibly grow the sheet.
  it("renders a sized skeleton (not just a status line) while detail/awards are loading", () => {
    vi.mocked(api.getPlayerQuickView).mockReturnValue(new Promise(() => {}));
    vi.mocked(api.getPlayerAwards).mockReturnValue(new Promise(() => {}));

    const { container } = render(<PlayerQuickView identity={identity()} onClose={vi.fn()} />);

    // Chart-height placeholder, reserving WeeklyPointsChart's own
    // CHART_HEIGHT footprint ahead of time.
    const chartSkeleton = Array.from(container.querySelectorAll<HTMLElement>(".pqv-skeleton-line")).find((el) => el.style.height === "160px") ?? null;
    expect(chartSkeleton).toBeInTheDocument();
    expect(chartSkeleton?.style.height).toBe("160px");
    // Stat-tile skeletons reuse the real tile classes so the grid is
    // already the right shape/height before real data lands.
    expect(container.querySelectorAll(".pqv-stat-row.pqv-skeleton-tile").length).toBeGreaterThan(0);
    // Decorative — never double-announced to assistive tech alongside the
    // one real sr-only status line.
    expect(container.querySelector('[aria-hidden="true"] .pqv-skeleton-line')).toBeInTheDocument();
  });

  // coridian_, 2026-10-19 (screenshot): "the contributor tag doesnt make
  // sense if he hasnt been playing much" — tier/opportunity_label are
  // available from the `identity` prop immediately, no fetch needed.
  it("explains a low tier vs. high right-now opportunity (e.g. an injury-driven promotion)", () => {
    vi.mocked(api.getPlayerQuickView).mockReturnValue(new Promise(() => {}));
    vi.mocked(api.getPlayerAwards).mockReturnValue(new Promise(() => {}));

    render(
      <PlayerQuickView
        identity={identity({ tier: "Contributor", opportunity_label: "Elite Opportunity" })}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText(/reflects value over the full season/)).toBeInTheDocument();
  });

  it("stays quiet when tier and opportunity_label don't contradict", () => {
    vi.mocked(api.getPlayerQuickView).mockReturnValue(new Promise(() => {}));
    vi.mocked(api.getPlayerAwards).mockReturnValue(new Promise(() => {}));

    render(<PlayerQuickView identity={identity()} onClose={vi.fn()} />);

    expect(screen.queryByText(/reflects value over the full season/)).not.toBeInTheDocument();
  });

  it("renders stats, model sub-ratings, decision fit, awards, and bio once loaded", async () => {
    vi.mocked(api.getPlayerQuickView).mockResolvedValue(quickView());
    vi.mocked(api.getPlayerAwards).mockResolvedValue(awardsResult());

    const { container } = render(<PlayerQuickView identity={identity()} onClose={vi.fn()} />);

    await waitFor(() => expect(api.getPlayerQuickView).toHaveBeenCalledWith("p1"));
    await waitFor(() => expect(api.getPlayerAwards).toHaveBeenCalledWith("p1"));

    await waitFor(() => expect(screen.queryByText(/Loading player detail/)).not.toBeInTheDocument());

    expect(screen.getByText(/Market value \(92nd percentile at WR\)/)).toBeInTheDocument();
    // All 5 Model ratings present -> the radar chart renders (coridian_,
    // 2026-10-18: "have that multi-axis thing") instead of the flat chip
    // row; its accessible summary carries the same real numbers.
    // The radar is a lazy chunk (next/dynamic), so await it rather than assume it is mounted.
    expect(await screen.findByText(/MKT 91, OPP 84, SCR 62, ROLE 73, DUR 58/)).toBeInTheDocument();
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
    // Header redesign (owner concept, 2026-10-21): the tier is a rounded
    // archetype pill bordered in that same prestige color, and usage is a
    // stat tile toned by the trend's direction.
    const tierChip = screen.getByText("starter").closest(".pqv-archetype-pill") as HTMLElement;
    expect(tierChip.style.getPropertyValue("--archetype-color")).toBe("var(--color-tier-starter)");
    const usageTile = screen.getByTestId("pqv-usage-tile");
    expect(usageTile).toHaveAttribute("data-tone", "positive");
    expect(usageTile).toHaveTextContent("12%");

    // coridian_, 2026-10-20 (screenshots): "this takes up way too much
    // space for the information that is displaying" — each stat is a
    // compact tile (label + value + a small percentile dot) inside a
    // dense grid, not a full-width row with its own full-width progress
    // bar and a separate percentile-text line underneath.
    const targetsRow = screen.getByText("Targets").closest(".pqv-stat-row");
    expect(targetsRow).toBeInTheDocument();
    expect(targetsRow?.querySelector(".pqv-percentile-dot")).toBeInTheDocument();
    expect(targetsRow?.querySelector(".pqv-percentile-bar")).not.toBeInTheDocument();
    expect(container.querySelector(".pqv-stat-grid")).toBeInTheDocument();
  });

  // coridian_, 2026-10-19: "was there any way for us to predict (scenario)
  // something like cam skattebo having 0 snaps and relaying that to
  // USERS?"
  it("shows a real depth-chart-order move as a plain-language note", async () => {
    vi.mocked(api.getPlayerQuickView).mockResolvedValue(
      quickView({ model: { ...quickView().model!, depth_chart_note: "Moved up 1 spot on the depth chart since last week." } }),
    );
    vi.mocked(api.getPlayerAwards).mockResolvedValue(awardsResult());

    render(<PlayerQuickView identity={identity()} onClose={vi.fn()} />);

    await waitFor(() => expect(screen.queryByText(/Loading player detail/)).not.toBeInTheDocument());
    expect(screen.getByText("Moved up 1 spot on the depth chart since last week.")).toBeInTheDocument();
  });

  // coridian_, 2026-10-20: "it expands the background of the PQV as those
  // modules load in" — PlayerTrendsPanel.tsx fetches weekly stats on its
  // own, independently of the outer detail/awards gate above, so it used
  // to mount (once that outer gate resolved) showing its own bare
  // "Loading weekly trends…" line and only then grow a second time into
  // the real chart. It now reserves the chart's exact CHART_HEIGHT
  // footprint up front instead.
  it("reserves the weekly chart's height with a skeleton instead of a second growth once it mounts", async () => {
    vi.mocked(api.getPlayerQuickView).mockResolvedValue(quickView());
    vi.mocked(api.getPlayerAwards).mockResolvedValue(awardsResult());
    vi.mocked(api.getPlayerWeeklyStats).mockReturnValue(new Promise(() => {}));

    const { container } = render(<PlayerQuickView identity={identity()} onClose={vi.fn()} />);

    await waitFor(() => expect(screen.queryByText(/Loading player detail/)).not.toBeInTheDocument());

    const trendsChartSkeleton = Array.from(container.querySelectorAll<HTMLElement>(".pqv-skeleton-line")).find((el) => el.style.height === "160px") ?? null;
    expect(trendsChartSkeleton).toBeInTheDocument();
    expect(trendsChartSkeleton?.style.height).toBe("160px");
    expect(screen.getByText(/Loading weekly trends/)).toBeInTheDocument();
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

    await waitFor(() => expect(api.getPlayerWeeklyStats).toHaveBeenCalledWith("p1", undefined));
    expect(await screen.findByText("Week by Week · 2026")).toBeInTheDocument();
  });

  // coridian_, 2026-10-19: "need to see other years week by week" — a
  // season with no games played is exactly when a selector back to an
  // earlier season (which might have real data) is most useful, so the
  // section stays visible (with the panel's own empty-season message)
  // instead of disappearing, as it used to.
  it("shows the week-by-week section's own empty-season message (not hidden) when no weeks have been played yet", async () => {
    vi.mocked(api.getPlayerQuickView).mockResolvedValue(quickView());
    vi.mocked(api.getPlayerAwards).mockResolvedValue(awardsResult());
    vi.mocked(api.getPlayerWeeklyStats).mockResolvedValue({
      ok: true,
      season: 2026,
      weeks: [{ week: 1, fantasy_points_ppr: null, snap_share: null }],
    });

    render(<PlayerQuickView identity={identity()} onClose={vi.fn()} />);

    await waitFor(() => expect(screen.queryByText(/Loading player detail/)).not.toBeInTheDocument());
    expect(await screen.findByText("Week by Week · 2026")).toBeInTheDocument();
    expect(screen.getByText(/No weekly fantasy points are recorded for the 2026 season yet/)).toBeInTheDocument();
  });

  it("lets the user pick an earlier season and refetches weekly stats for it", async () => {
    vi.mocked(api.getPlayerQuickView).mockResolvedValue(quickView());
    vi.mocked(api.getPlayerAwards).mockResolvedValue(awardsResult());
    vi.mocked(api.getPlayerWeeklyStats).mockResolvedValue({
      ok: true,
      season: 2026,
      weeks: [{ week: 1, fantasy_points_ppr: 18.4, snap_share: 0.82 }],
    });

    render(<PlayerQuickView identity={identity()} onClose={vi.fn()} />);

    await waitFor(() => expect(api.getPlayerWeeklyStats).toHaveBeenCalledWith("p1", undefined));
    expect(await screen.findByLabelText("Season")).toBeInTheDocument();

    vi.mocked(api.getPlayerWeeklyStats).mockResolvedValue({
      ok: true,
      season: 2024,
      weeks: [{ week: 1, fantasy_points_ppr: 11.2, snap_share: 0.6 }],
    });
    fireEvent.change(screen.getByLabelText("Season"), { target: { value: "2024" } });

    await waitFor(() => expect(api.getPlayerWeeklyStats).toHaveBeenCalledWith("p1", 2024));
    expect(await screen.findByText("Week by Week · 2024")).toBeInTheDocument();
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
    expect(screen.getByRole("heading", { name: "Player One" })).toBeInTheDocument();
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

  // coridian_, 2026-10-19: "the pqv on the app has tabs that the site
  // doesnt. Thats a consistency error" — the actual product fix: a real
  // link from this condensed modal to the full Player Profile page (mobile's
  // Stats/Trends/Schedule/Career/Model tabs), gated the same way the
  // Compare link already is (both need a league context to deep-link into).
  it("renders an Open Full Profile link only when leagueId is provided", async () => {
    vi.mocked(api.getPlayerQuickView).mockResolvedValue(quickView());
    vi.mocked(api.getPlayerAwards).mockResolvedValue(awardsResult());

    const { rerender } = render(<PlayerQuickView identity={identity()} onClose={vi.fn()} />);
    await waitFor(() => expect(screen.queryByText(/Loading player detail/)).not.toBeInTheDocument());
    expect(screen.queryByText("Open Full Profile")).not.toBeInTheDocument();

    rerender(
      <PlayerQuickView identity={identity({ leagueId: "league-1", leagueName: "My League" })} onClose={vi.fn()} />,
    );
    const link = screen.getByText("Open Full Profile");
    expect(link.closest("a")).toHaveAttribute("href", "/players/league-1/p1?name=My%20League");
  });
});
