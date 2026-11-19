import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SimWatchPlayback } from "@/components/SimWatch";

vi.mock("@/components/SimGameParts", () => ({
  SimToneBadge: ({ label }: { label: string }) => <span>{label}</span>,
  SimPlayerChip: () => null,
}));

const WINS = [true, false, true, false, true];
const advance = vi.fn(async (_id: string, week: number) => {
  const i = week - 1;
  if (i >= WINS.length) return {};
  const wins = WINS.slice(0, i + 1).filter(Boolean).length;
  return {
    recap: { week, kind: "regular", your_game: { result: WINS[i] ? "win" : "loss", your_pts: 100 + week, opp_pts: WINS[i] ? 90 : 120, opponent_name: `Team ${week}` }, standings: [{ is_you: true, rank: 3 }], waivers: [] },
    game: { id: "g", status: "in_season", week: week + 1, settings: { watch_v: 1, regular_weeks: 14 }, you: { team_id: "me", wins, losses: i + 1 - wins, ties: 0, rank: 3 } },
  };
});
vi.mock("@/lib/api", () => ({ api: { advanceSimGame: (id: string, week: number) => advance(id, week) } }));

describe("Draft & Watch playback", () => {
  it("shows a record that matches the results list after N weeks", async () => {
    // The parent's game never updates here (setGame is a no-op), like a render that lags the advance answer.
    const ctx = { gameId: "g", game: { id: "g", status: "in_season", week: 1, settings: { watch_v: 1, regular_weeks: 14 }, you: { team_id: "me", wins: 0, losses: 0, ties: 0, rank: 0 } }, call: (fn: () => Promise<unknown>) => fn(), setGame: () => {} };
    render(<SimWatchPlayback ctx={ctx as never} />);
    fireEvent.click(screen.getByRole("tab", { name: "Skip to end" }));
    fireEvent.click(screen.getByRole("button", { name: "Sim the season" }));
    await waitFor(() => expect(screen.getAllByRole("listitem").length).toBeGreaterThanOrEqual(5));
    await waitFor(() => expect(screen.queryByRole("button", { name: "Pause" })).toBeNull());
    const results = screen.getByLabelText("Results");
    const wins = Array.from(results.querySelectorAll("li")).filter((li) => li.textContent?.includes("Team")).length;
    expect(wins).toBe(5);
    const won = WINS.filter(Boolean).length;
    expect(screen.getByTestId("watch-record").textContent).toBe(`${won}-${WINS.length - won}`);
  });
});
