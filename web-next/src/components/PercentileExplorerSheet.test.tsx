import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PercentileExplorerSheet } from "./PercentileExplorerSheet";
import { api } from "@/lib/api";
import {
  addPin,
  assignMarkerLanes,
  binIndexAtPercentile,
  bucketPlayers,
  defaultComparison,
  explorerMetricsFor,
  playersNearPercentile,
  poolMedian,
  rosterIdsFromRoster,
  searchExplorerPool,
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
    window.sessionStorage.clear();
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
    await waitFor(() => expect(mocked).toHaveBeenLastCalledWith("me", "ppr_ppg", "all", true));
  });


  it("labels players with first initial and full last name, never an ellipsis", async () => {
    mocked.mockResolvedValue(
      response({
        player: p("me", "Marvin Mitchell", 16.7, 88),
        nearby: [p("a", "Amon-Ra St. Brown", 13.6, 74), p("b", "Marvin Harrison Jr.", 18.1, 95)],
      }),
    );
    renderSheet();
    await waitFor(() => screen.getByTestId("pe-chart"));
    const chart = screen.getByTestId("pe-chart").textContent ?? "";
    expect(chart).toContain("M. Mitchell");
    expect(chart).toContain("A. St. Brown");
    expect(chart).toContain("M. Harrison Jr.");
    expect(chart).not.toContain("…");
    expect(screen.getByTestId("pe-compare").textContent).toContain("M. Harrison Jr.");
  });

  it("scrubs the histogram, lists the bucket and adds a tapped player as the comparison", async () => {
    const pool = [p("b", "Peer Brown", 18.1, 95), p("me", "Test Chase", 16.7, 88), p("a", "Peer Lamb", 13.6, 74), p("c", "Zed Low", 3, 10)];
    mocked.mockResolvedValue(
      response({
        pool_players: pool,
        bins: [
          { count: 2, pct_start: 0, pct_end: 50, value_start: 3, value_end: 10 },
          { count: 2, pct_start: 50, pct_end: 100, value_start: 10, value_end: 18.1 },
        ],
      }),
    );
    renderSheet();
    await waitFor(() => screen.getByTestId("pe-scrub"));
    const strip = screen.getByTestId("pe-scrub");
    strip.getBoundingClientRect = () => ({ left: 0, width: 100, top: 0, height: 88, right: 100, bottom: 88, x: 0, y: 0, toJSON() {} }) as DOMRect;
    fireEvent.pointerDown(strip, { clientX: 80, pointerId: 1 });
    await waitFor(() => screen.getByTestId("pe-bucket"));
    // The top bucket holds Peer Brown and Test Chase.
    const bucket = screen.getByTestId("pe-bucket");
    expect(bucket.textContent).toContain("P. Brown");
    expect(bucket.textContent).toContain("T. Chase");
    fireEvent.click(screen.getByRole("button", { name: "Compare with Peer Brown" }));
    expect(screen.getByTestId("pe-compare").textContent).toContain("P. Brown");
  });

  it("switches metric without closing and refetches with the full pool", async () => {
    mocked.mockResolvedValue(response());
    renderSheet();
    await waitFor(() => screen.getByTestId("pe-chart"));
    fireEvent.click(screen.getByRole("tab", { name: "Target Share" }));
    await waitFor(() => expect(mocked).toHaveBeenLastCalledWith("me", "target_share", "position", true));
    expect(screen.getByText("Target Share Percentile Explorer")).toBeTruthy();
  });

  it("searches the pool and charts the chosen player", async () => {
    const pool = [p("me", "Test Chase", 16.7, 88), p("a", "Peer Lamb", 13.6, 74), p("z", "Zed Low", 3, 10)];
    mocked.mockResolvedValue(response({ pool_players: pool, nearby: [p("a", "Peer Lamb", 13.6, 74)] }));
    renderSheet();
    await waitFor(() => screen.getByTestId("pe-chart"));
    fireEvent.click(await screen.findByRole("tab", { name: "Find a player" }));
    fireEvent.change(screen.getByLabelText("Search players to add to the chart"), { target: { value: "zed" } });
    fireEvent.click(screen.getByRole("button", { name: "Compare with Zed Low" }));
    expect(screen.getByTestId("pe-compare").textContent).toContain("Z. Low");
    expect(screen.getByRole("button", { name: /Zed Low, 3.0 PPR PPG, 10th percentile/ })).toBeTruthy();
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

  it("buckets players exactly by histogram counts", () => {
    const pool = [p("e", "E", 9, 90), p("d", "D", 8, 70), p("c", "C", 5, 50), p("b", "B", 2, 30), p("a", "A", 1, 10)];
    const bins = [
      { count: 2, pct_start: 0, pct_end: 40, value_start: 1, value_end: 4 },
      { count: 1, pct_start: 40, pct_end: 60, value_start: 4, value_end: 6 },
      { count: 2, pct_start: 60, pct_end: 100, value_start: 6, value_end: 9 },
    ];
    expect(bucketPlayers(pool, bins, 0).map((x) => x.player_id)).toEqual(["b", "a"]);
    expect(bucketPlayers(pool, bins, 1).map((x) => x.player_id)).toEqual(["c"]);
    expect(bucketPlayers(pool, bins, 2).map((x) => x.player_id)).toEqual(["e", "d"]);
    expect(bucketPlayers(pool, bins, 3)).toEqual([]);
    expect(binIndexAtPercentile(bins, 0)).toBe(0);
    expect(binIndexAtPercentile(bins, 40)).toBe(1);
    expect(binIndexAtPercentile(bins, 100)).toBe(2);
    expect(playersNearPercentile(pool, 68, 2).map((x) => x.player_id)).toEqual(["d", "c"]);
  });

  it("searches by prefix, word prefix and substring; median; roster ids; metrics", () => {
    const pool = [p("1", "Amon-Ra St. Brown", 1, 1), p("2", "Marvin Brownlee", 2, 2), p("3", "Cobrown Smith", 3, 3)];
    expect(searchExplorerPool(pool, "st").map((x) => x.player_id)).toEqual(["1"]);
    expect(searchExplorerPool(pool, "brown").map((x) => x.player_id)).toEqual(["1", "2", "3"]);
    expect(searchExplorerPool(pool, "b")).toEqual([]);
    expect(poolMedian([p("1", "A", 1, 1), p("2", "B", 5, 2), p("3", "C", 9, 3)])).toBe(5);
    expect(poolMedian([])).toBeNull();
    expect([...rosterIdsFromRoster({ players: ["1", "2", 3] })]).toEqual(["1", "2"]);
    expect(rosterIdsFromRoster(null).size).toBe(0);
    expect(addPin(["a", "b"], "c", 2)).toEqual(["b", "c"]);
    expect(addPin(["a"], "a")).toEqual(["a"]);
    expect(explorerMetricsFor("QB", { key: "ppr_ppg", label: "PPR PPG" }).map((m) => m.key)).toContain("pass_yards");
    expect(explorerMetricsFor("WR", { key: "carry_share", label: "Carry Share" })[0].key).toBe("carry_share");
  });
});
