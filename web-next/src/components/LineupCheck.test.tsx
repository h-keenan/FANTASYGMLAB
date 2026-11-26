import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LineupCheckView } from "@/components/LineupCheck";
import type { CommissionerLineupsResponse, LineupCheckTeam } from "@/lib/commissionerLineups";

function team(over: Partial<LineupCheckTeam>): LineupCheckTeam {
  return {
    roster_id: "1", team_name: "Alpha", owner_name: null, avatar_url: null, has_lineup: true, starters: [], set_points: 80, best_points: 100,
    gap: 20, gap_pct: 0.2, partial: false, possible_tanking: true, flags: [{ kind: "out", label: "Out", player: "A. Smith", slot: "RB" }],
    locked_count: 1, swaps: [{ slot: "RB", start: { player_id: "9", name: "Bench Guy", position: "RB", team: "BUF", points: 12 }, over: null, over_reason: "empty_slot", gain: 12 }], ...over,
  };
}
const base: CommissionerLineupsResponse = { ok: true, is_premium: true, reason: "", week: 6, projection_ready: true, teams: [team({})], limits: [] };

describe("LineupCheckView", () => {
  it("shows the compact row, then the fixing swaps on tap", () => {
    render(<LineupCheckView data={base} />);
    expect(screen.getByText("Set 80.0 · Best 100.0")).toBeTruthy();
    expect(screen.getByText("Possible tanking")).toBeTruthy();
    expect(screen.getByText("Out: A. Smith")).toBeTruthy();
    expect(screen.getByText("1 locked")).toBeTruthy();
    fireEvent.click(screen.getByTestId("lineup-team-1-toggle"));
    expect(screen.getByText(/Start Bench Guy over an empty slot/)).toBeTruthy();
  });

  it("explains an empty state when there are no projections or no week", () => {
    render(<LineupCheckView data={{ ...base, reason: "no_current_week", teams: [] }} />);
    expect(screen.getByText(/no live week yet/i)).toBeTruthy();
  });

  it("handles a league with no projections yet", () => {
    render(<LineupCheckView data={{ ...base, projection_ready: false, teams: [team({ set_points: null, best_points: null, gap: null, possible_tanking: false })] }} />);
    expect(screen.getByText("No projections yet")).toBeTruthy();
    expect(screen.getByTestId("lineup-summary").textContent).toMatch(/no projections yet/);
  });
});
