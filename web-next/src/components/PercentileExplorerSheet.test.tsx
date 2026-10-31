import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PercentileExplorerSheet } from "./PercentileExplorerSheet";
import { api } from "@/lib/api";
import {
  assignMarkerLanes,
  defaultComparison,
  explorerStatKey,
  formatExplorerDelta,
  type ExplorerPlayer,
  type PercentileExplorerResponse,
} from "@/lib/percentileExplorer";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: { ...actual.api, getPercentileExplorer: vi.fn() } };
});

const mocked = vi.mocked(api.getPercentileExplorer);

function p(id: string, name: string, value: number, percentile: number): ExplorerPlayer {
  return { player_id: id, name, team: "CIN", position: "WR", value, percentile };
}

function response(overrides: Partial<PercentileExplorerResponse> = {}): PercentileExplorerResponse {
  return {
    ok: true,
    reason: "",
    stat: "ppr_ppg",
    label: "PPR PPG",
    format: "ppg",
    pool: "position",
    position: "WR",
    season: 2026,
    scopes: ["season"],
    pool_size: 40,
    bins: [
      { count: 5, pct_start: 0, pct_end: 50, value_start: 2, value_end: 10 },
      { count: 2, pct_start: 50, pct_end: 100, value_start: 10, value_end: 18 },
    ],
    player: p("me", "Test Chase", 16.7, 88),
    nearby: [p("a", "Peer Lamb", 13.6, 74), p("b", "Peer Brown", 18.1, 95)],
    ...overrides,
  };
}

function renderSheet(onOpenPlayer = vi.fn()) {
  render(<PercentileExplorerSheet playerId="me" statKey="ppr_ppg" statLabel="PPR PPG" onClose={vi.fn()} onOpenPlayer={onOpenPlayer} />);
  return onOpenPlayer;
}

describe("PercentileExplorerSheet", () => {
  beforeEach(() => {
    mocked.mockReset();
  });

  it("shows a loading state first", () => {
    mocked.mockReturnValue(new Promise(() => {}));
    renderSheet();
    expect(screen.getByTestId("pe-loading")).toBeTruthy();
    expect(screen.getByText("PPR PPG Percentile Explorer")).toBeTruthy();
  });

  it("renders markers and a compare card with the delta, and swaps", async () => {
    mocked.mockResolvedValue(response());
    renderSheet();
    await waitFor(() => expect(screen.getByTestId("pe-chart")).toBeTruthy());
    expect(screen.getByRole("button", { name: /Peer Lamb, 13.6 PPR PPG, 74th percentile/ })).toBeTruthy();
    // Default comparison is the closest player above: Peer Brown (18.1).
    expect(screen.getByTestId("pe-compare").textContent).toContain("-1.4");
    fireEvent.click(screen.getByRole("button", { name: /Peer Lamb, 13.6/ }));
    expect(screen.getByTestId("pe-compare").textContent).toContain("+3.1");
    fireEvent.click(screen.getByRole("button", { name: "Swap comparison" }));
    expect(screen.getByTestId("pe-compare").textContent).toContain("-3.1");
  });

  it("opens a player's own quick view from the compare card", async () => {
    mocked.mockResolvedValue(response());
    const onOpenPlayer = renderSheet();
    await waitFor(() => screen.getByTestId("pe-compare"));
    fireEvent.click(screen.getByRole("button", { name: "Open Peer Brown" }));
    expect(onOpenPlayer).toHaveBeenCalledWith({ player_id: "b", name: "Peer Brown", team: "CIN", position: "WR" });
  });

  it("refetches with pool=all when All Players is chosen", async () => {
    mocked.mockResolvedValue(response());
    renderSheet();
    await waitFor(() => screen.getByTestId("pe-chart"));
    fireEvent.click(screen.getByRole("tab", { name: "All Players" }));
    await waitFor(() => expect(mocked).toHaveBeenLastCalledWith("me", "ppr_ppg", "all"));
  });

  it("explains an insufficient pool instead of drawing a chart", async () => {
    mocked.mockResolvedValue(response({ reason: "insufficient_pool", bins: undefined, nearby: undefined, player: undefined }));
    renderSheet();
    await waitFor(() => expect(screen.getByText("Not enough players to rank")).toBeTruthy());
    expect(screen.queryByTestId("pe-chart")).toBeNull();
  });

  it("shows a no-data state and an error state", async () => {
    mocked.mockResolvedValueOnce(response({ reason: "no_data", player: undefined }));
    const { unmount } = render(
      <PercentileExplorerSheet playerId="me" statKey="ppr_ppg" statLabel="PPR PPG" onClose={vi.fn()} />,
    );
    await waitFor(() => expect(screen.getByText("No data for this stat")).toBeTruthy());
    unmount();
    mocked.mockRejectedValueOnce(new Error("x"));
    render(<PercentileExplorerSheet playerId="me" statKey="ppr_ppg" statLabel="PPR PPG" onClose={vi.fn()} />);
    await waitFor(() => expect(screen.getByText("Couldn't load this stat")).toBeTruthy());
  });
});

describe("percentileExplorer helpers", () => {
  it("maps tile labels to stat keys and skips Games", () => {
    expect(explorerStatKey("PPR PPG")).toBe("ppr_ppg");
    expect(explorerStatKey("Snap %")).toBe("snap");
    expect(explorerStatKey("Games")).toBeNull();
  });

  it("formats deltas by unit", () => {
    expect(formatExplorerDelta(16.7, 13.6, "ppg")).toBe("+3.1");
    expect(formatExplorerDelta(251, 300, "yards")).toBe("-49");
    expect(formatExplorerDelta(70, 60, "share")).toBe("+10 pts");
  });

  it("keeps close markers on different lanes", () => {
    const lanes = assignMarkerLanes([20, 24, 28, 60]);
    expect(new Set(lanes.slice(0, 3)).size).toBe(3);
    expect(lanes[3]).toBe(0);
  });

  it("defaults the comparison to the nearest player above", () => {
    const me = p("me", "Me", 10, 50);
    expect(defaultComparison(me, [p("a", "A", 12, 60), p("b", "B", 11, 55), p("c", "C", 9, 45)])?.player_id).toBe("b");
    expect(defaultComparison(me, [])).toBeNull();
  });
});
