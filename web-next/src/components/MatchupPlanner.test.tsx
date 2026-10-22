import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MatchupContent } from "./MatchupContent";
import { api, type MatchupResponse, type MatchupWhatIfResponse } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: { ...actual.api, postMatchupWhatIf: vi.fn() } };
});

function row(id: string, name: string, slot: string, pts: number) {
  return {
    player_id: id,
    name,
    position: slot,
    team: "SF",
    age: 25,
    status: "Active",
    injury_status: null,
    injury_label: "",
    ruled_out: false,
    tier: "starter",
    score: 1000,
    slot,
    suggested_starter: true,
    roster_slot: "starter",
    opportunity_label: null,
    overall_rating: 70,
    why: "",
    projection: { status: "ok", point_estimate: pts, low: pts - 3, high: pts + 3, confidence: "medium", opponent: "SEA" },
  };
}

function side(rosterId: string, name: string, starters: ReturnType<typeof row>[]) {
  return {
    roster_id: rosterId,
    team_name: name,
    owner_name: null,
    avatar_url: null,
    wins: 1,
    losses: 1,
    ties: 0,
    starters,
    season_value_total: 1000,
    starters_basis: "suggested_optimal_lineup",
    real_starters: [],
    real_points: null,
    has_live_data: false,
    real_starters_basis: "sleeper_actual_lineup",
    real_empty_slots: [],
    open_slots: [],
  };
}

function matchup(overrides: Record<string, unknown> = {}): MatchupResponse {
  return {
    ok: true,
    week: 7,
    my_team: side("1", "Mine", [row("qb", "Quinn Back", "QB", 20), row("wr1", "Wes Receiver", "WR", 11)]),
    opponent: side("2", "Theirs", [row("oq", "Opp Quarterback", "QB", 18)]),
    comparison: {
      my_season_value: 1000,
      opponent_season_value: 1000,
      margin: 0,
      edge: "even",
      headline: "",
      basis: "season_value",
      basis_label: "",
    },
    real_comparison: null,
    win_probability: { available: false, reason: "no_starters" },
    position_edges: { actual: null, suggested: [] },
    suggested_moves: null,
    basis: "season_value",
    basis_label: "",
    reason: "",
    best_ball: false,
    ...overrides,
  } as unknown as MatchupResponse;
}

function whatIf(pct: number, extra: Partial<MatchupWhatIfResponse> = {}): MatchupWhatIfResponse {
  return {
    ok: true,
    reason: "",
    lineup: [row("qb", "Quinn Back", "QB", 20), row("wr1", "Wes Receiver", "WR", 11)] as never,
    win_probability: {
      available: true,
      probability: pct / 100,
      my_projected_total: 31,
      opponent_projected_total: 18,
      coverage: { my: 1, opponent: 1 },
    },
    position_edges: [],
    candidates: null,
    ...extra,
  };
}

const post = vi.mocked(api.postMatchupWhatIf);

beforeEach(() => {
  post.mockReset();
});

describe("Matchup lineup planner", () => {
  it("is hidden for best ball", () => {
    render(<MatchupContent leagueName="L" leagueId="9" matchup={matchup({ best_ball: true })} />);
    expect(screen.queryByRole("button", { name: "Edit lineup" })).toBeNull();
  });

  it("edits a slot, shows pros and cons, updates the win bar, and resets", async () => {
    post.mockResolvedValueOnce(whatIf(60));
    render(<MatchupContent leagueName="L" leagueId="9" matchup={matchup()} />);
    fireEvent.click(screen.getByRole("button", { name: "Edit lineup" }));
    await waitFor(() => expect(post).toHaveBeenCalledTimes(1));
    expect(post.mock.calls[0][1].lineup).toEqual([
      { slot: "QB", player_id: "qb" },
      { slot: "WR", player_id: "wr1" },
    ]);
    await screen.findByText("60%");

    post.mockResolvedValueOnce(
      whatIf(60, {
        candidates: {
          slot: "WR",
          slot_locked: false,
          current_player_id: "wr1",
          candidates: [
            {
              player: row("bench", "Ben Chwarmer", "WR", 15) as never,
              selectable: true,
              blocked_reason: null,
              points_delta: 4,
              win_probability_delta: 5,
              win_probability_after: null,
              bullets: [
                { tone: "pro", text: "+4.0 projected pts" },
                { tone: "pro", text: "+5% win probability" },
              ],
            },
            {
              player: row("bye", "Bye Guy", "WR", 0) as never,
              selectable: false,
              blocked_reason: "bye",
              points_delta: null,
              win_probability_delta: null,
              win_probability_after: null,
              bullets: [{ tone: "con", text: "On a bye" }],
            },
          ],
        },
      }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Swap Wes Receiver" }));
    await screen.findByText("+4.0 projected pts");
    expect(screen.getByText("On a bye")).toBeTruthy();
    expect((screen.getByText("Bye Guy").closest("button") as HTMLButtonElement).disabled).toBe(true);

    post.mockResolvedValueOnce(whatIf(66));
    fireEvent.click(screen.getByText("Ben Chwarmer").closest("button")!);
    await waitFor(() => expect(post).toHaveBeenCalledTimes(3));
    expect(post.mock.calls[2][1].lineup).toEqual([
      { slot: "QB", player_id: "qb" },
      { slot: "WR", player_id: "bench" },
    ]);
    await screen.findByText("66%");

    post.mockResolvedValueOnce(whatIf(60));
    fireEvent.click(screen.getByRole("button", { name: "Reset to suggested" }));
    await waitFor(() => expect(post).toHaveBeenCalledTimes(4));
    expect(post.mock.calls[3][1].lineup).toEqual(post.mock.calls[0][1].lineup);
    expect(screen.getByRole("link", { name: "Open in Sleeper" }).getAttribute("href")).toBe(
      "https://sleeper.com/leagues/9",
    );
  });
});
