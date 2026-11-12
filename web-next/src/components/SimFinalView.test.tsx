import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SimFinalView } from "./SimGameRecap";
import { api } from "@/lib/api";
import type { SimCtx } from "./SimGameParts";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: { ...actual.api, getSimGameResult: vi.fn() } };
});

const ctx = { gameId: "g1", game: { settings: { regular_weeks: 14 } } } as unknown as SimCtx;
const row = (team_id: string, is_you: boolean, playoff_result: string) => ({
  rank: 1, team_id, name: `Team ${team_id}`, is_you, wins: 9, losses: 5, ties: 0, pf: 1500.5, pa: 1400, playoff_result,
});

describe("SimFinalView", () => {
  it("renders the backend's real result shape (object grade summary and champion)", async () => {
    vi.mocked(api.getSimGameResult).mockResolvedValue({
      ok: true,
      result: {
        champion: { team_id: "3", name: "Team 3" },
        final_standings: [row("3", false, "champion"), row("1", true, "lost_round_2")],
        grade: { letter: "C+", score: 60, summary: { record: "9-5", finish: 2, points_rank: 4 } },
        decisions_that_mattered: [{ kind: "trade", title: "Week 3 trade", detail: "Helped." }],
      },
    } as never);
    render(<SimFinalView ctx={ctx} onNewGame={() => {}} onHub={() => {}} />);
    await waitFor(() => expect(screen.getByTestId("final-result")).toBeTruthy());
    expect(screen.getByText(/Champion: Team 3/)).toBeTruthy();
    expect(screen.getByText(/finished 2nd/)).toBeTruthy();
  });

  it("renders a missed-playoffs result with no champion, no decisions and no summary", async () => {
    vi.mocked(api.getSimGameResult).mockResolvedValue({
      ok: true,
      result: { champion: null, final_standings: [row("1", true, "missed")], grade: { letter: "D" }, decisions_that_mattered: [] },
    } as never);
    render(<SimFinalView ctx={ctx} onNewGame={() => {}} onHub={() => {}} />);
    await waitFor(() => expect(screen.getByTestId("final-result")).toBeTruthy());
    expect(screen.queryByText(/Champion:/)).toBeNull();
  });
});
