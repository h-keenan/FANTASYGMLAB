import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PlayerUsageBlock } from "./PlayerUsageBlock";
import { api, type UsageProfile } from "@/lib/api";
import { formatUsageDelta, formatUsageValue, hasUsageContent } from "@/lib/usageProfilePresentation";

function profile(overrides: Partial<UsageProfile> = {}): UsageProfile {
  return {
    status: "ok",
    season: 2026,
    games_played: 8,
    metrics: [
      { key: "snap_share", label: "Snap share", unit: "pct", source: "sleeper", last4: 0.78, last8: 0.66, prior: 0.55, season: 0.66, delta_last4_vs_prior: 0.23, direction: "up", games_with_data: 8, explorer_key: "snap", percentile: 83 },
      { key: "opportunities", label: "Opportunities / game", unit: "count", source: "sleeper", last4: 12.5, last8: 10, prior: 7.5, season: 10, delta_last4_vs_prior: 5, direction: "up", games_with_data: 8 },
    ],
    flags: [
      { key: "role_expanding", label: "Role expanding", tone: "positive", explanation: "His role is growing: snap share is 78% over the last 4 games vs 55% before (+23 pts).", evidence_metrics: ["snap_share"] },
    ],
    advanced: { available: true, through_week: 8, as_of: "t" },
    not_available: [{ key: "routes_run", label: "Routes run / yards per route run", reason: "x" }],
    attribution: { text: "Usage stats: nflverse (nflverse.com), CC BY 4.0", url: "https://www.nflverse.com/", license: "CC BY 4.0" },
    ...overrides,
  };
}

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: { ...actual.api, getPercentileExplorer: vi.fn() } };
});

describe("PlayerUsageBlock", () => {
  it("opens the shared Percentile Explorer for a usage row, with the sample stated", async () => {
    vi.mocked(api.getPercentileExplorer).mockResolvedValue({
      ok: true, reason: "", stat: "snap", label: "Snap Share", format: "share", pool: "position", position: "WR", season: 2026,
      scopes: ["season"], pool_size: 40,
      sample_note: "WRs with at least 4 games played in 2026; season average of weekly values",
      bins: [{ count: 5, pct_start: 0, pct_end: 100, value_start: 10, value_end: 90 }],
      player: { player_id: "p1", name: "Player One", team: "SF", position: "WR", value: 66, percentile: 83 },
      nearby: [],
    });
    render(<PlayerUsageBlock profile={profile()} position="WR" playerId="p1" />);
    fireEvent.click(screen.getByRole("button", { name: "Snap share percentile explorer" }));
    await waitFor(() => expect(api.getPercentileExplorer).toHaveBeenCalledWith("p1", "snap", "position", true));
    expect(await screen.findByTestId("pe-sample-note")).toHaveTextContent(/at least 4 games played in 2026/);
  });

  it("renders the flag explanation, rolling table, data note and nflverse credit", () => {
    render(<PlayerUsageBlock profile={profile()} position="WR" playerId="p1" />);
    expect(screen.getByText("Role expanding")).toBeInTheDocument();
    expect(screen.getByText(/snap share is 78% over the last 4 games/)).toBeInTheDocument();
    expect(screen.getByText("Snap share")).toBeInTheDocument();
    expect(screen.getByText("66%")).toBeInTheDocument();
    expect(screen.getByText(/Last 4: 78% \(\+23 pts vs earlier\)/)).toBeInTheDocument();
    // percentile bar row names the pool and season
    expect(screen.getByText("83rd")).toBeInTheDocument();
    expect(screen.getByText("Percentile vs WRs · 2026")).toBeInTheDocument();
    expect(screen.getByText(/through Week 8/)).toBeInTheDocument();
    expect(screen.getByText(/Not shown: Routes run/)).toBeInTheDocument();
    const credit = screen.getByRole("link", { name: /nflverse/ });
    expect(credit).toHaveAttribute("href", "https://www.nflverse.com/");
  });

  it("states missing advanced data instead of hiding it", () => {
    render(<PlayerUsageBlock profile={profile({ flags: [], advanced: { available: false, reason: "advanced_stats_file_unavailable" } })} />);
    expect(screen.getByText(/not available for this player right now/)).toBeInTheDocument();
  });

  it("explains a held-back sample and renders nothing for uncovered positions", () => {
    const { container, rerender } = render(
      <PlayerUsageBlock profile={profile({ status: "building_sample", flags: [], status_note: "Trend flags need 7 played games; this player has 5." })} />,
    );
    expect(screen.getByText(/need 7 played games/)).toBeInTheDocument();
    rerender(<PlayerUsageBlock profile={profile({ status: "not_covered", metrics: [], flags: [] })} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("surfaces a computation failure explicitly", () => {
    render(<PlayerUsageBlock profile={{ status: "unavailable", metrics: [], flags: [] }} />);
    expect(screen.getByRole("status")).toHaveTextContent(/could not be calculated/);
  });
});

describe("usage presentation helpers", () => {
  it("formats shares, counts and nulls", () => {
    const share = profile().metrics[0];
    const count = profile().metrics[1];
    expect(formatUsageValue(share, 0.783)).toBe("78%");
    expect(formatUsageValue(count, 12.54)).toBe("12.5");
    expect(formatUsageValue(count, null)).toBe("–");
    expect(formatUsageDelta(share)).toBe("+23 pts");
    expect(formatUsageDelta(count)).toBe("+5.0");
    expect(hasUsageContent(null)).toBe(false);
  });
});
