import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { DepthChartSection, InjuryHistorySection } from "./PlayerDepthInjury";
import type { DepthChartData, InjuryRecordData } from "@/lib/playerDepthInjury";

const chart: DepthChartData = {
  ok: true, team: "KC", slot: "RB", slot_label: "Running backs", self_order: 2, total: 3,
  entries: [
    { player_id: "a", name: "Isiah Starter", position: "RB", team: "KC", order: 1, is_self: false, change: 1 },
    { player_id: "b", name: "Me Backup", position: "RB", team: "KC", order: 2, is_self: true, change: null, injury_status: "Questionable" },
    { player_id: "c", name: "Third String", position: "RB", team: "KC", order: 3, is_self: false, change: -2 },
  ],
};

const record: InjuryRecordData = {
  ok: true, current_season: 2026, since_season: 2021, career_games_missed: 3,
  current: { label: "Questionable", status: "Questionable", severity: "question", unavailable: false, body_part: "Hamstring", practice: "Limited in practice", report: null, line: "Hamstring · Questionable" },
  seasons: [{ season: 2023, games_missed: 3, stints: [{ start_week: 4, end_week: 6, games_missed: 3, injury: "Foot" }] }],
};

describe("DepthChartSection", () => {
  beforeEach(() => window.localStorage.clear());

  it("is collapsed with a summary, then lists ahead/self/behind with his row highlighted", async () => {
    render(<DepthChartSection chart={chart} />);
    expect(screen.getByTestId("compact-summary")).toHaveTextContent("RB2 · KC · 1 ahead");
    fireEvent.click(screen.getByRole("button", { name: /Depth chart/ }));
    const rows = await screen.findAllByTestId("pqv-depth-row");
    expect(rows.map((r) => r.getAttribute("data-kind"))).toEqual(["ahead", "self", "behind"]);
    expect(rows[1]).toHaveAttribute("aria-current", "true");
    expect(screen.getAllByTestId("pqv-depth-move").map((n) => n.textContent)).toEqual(["▲ Up 1", "▼ Down 2"]);
  });

  it("renders nothing when he is not on a chart and a skeleton while loading", () => {
    const { container, rerender } = render(<DepthChartSection chart={{ ...chart, self_order: null, entries: [] }} />);
    expect(container).toBeEmptyDOMElement();
    rerender(<DepthChartSection chart={undefined} />);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });
});

describe("InjuryHistorySection", () => {
  beforeEach(() => window.localStorage.clear());

  it("shows the current injury line collapsed, and history with career total on tap", async () => {
    render(<InjuryHistorySection record={record} />);
    expect(screen.getByTestId("compact-summary")).toHaveTextContent("Hamstring · Questionable · Limited in practice");
    fireEvent.click(screen.getByRole("button", { name: /Injury history/ }));
    const rows = await screen.findAllByTestId("pqv-injury-row");
    expect(rows).toHaveLength(1);
    expect(rows[0]).toHaveTextContent("2023");
    expect(rows[0]).toHaveTextContent("Foot");
    expect(rows[0]).toHaveTextContent("Wk 4–6");
    expect(rows[0]).toHaveTextContent("3 games");
    expect(screen.getByTestId("pqv-injury-career")).toHaveTextContent("3");
  });

  it("says so when there is no missed-game history", () => {
    render(<InjuryHistorySection record={{ ...record, current: null, seasons: [], career_games_missed: 0 }} />);
    expect(screen.getByTestId("compact-summary")).toHaveTextContent("Healthy · No games missed on record");
  });
});
