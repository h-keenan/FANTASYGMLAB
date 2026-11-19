import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SimPickReveal, SimWeekStamp } from "@/components/SimMoments";
import { SIM_CELEBRATIONS_KEY } from "@/lib/simMoments";

vi.mock("@/components/PlayerAvatar", () => ({ PlayerAvatar: () => <span /> }));
vi.mock("@/components/SimGameParts", () => ({
  SimPlayerChip: ({ player, shortName }: { player: { name: string }; shortName?: boolean }) => <span data-short={shortName ? "1" : "0"}>{player.name}</span>,
}));

const pick = { pick_no: 7, round: 1, team_id: "me", player: { id: "1", name: "Jalen Pruitt", pos: "WR", team: "CIN", headshot_id: "1" }, adp: 13, value_over_adp: 6, auto: false } as never;
const recap = {
  your_game: { result: "win", your_pts: 112.4, opp_pts: 98.1, opponent_name: "Ghosts", starters: [{ player: { name: "Jalen Pruitt" }, pts: 31.4, flag: null }] },
  standings: [{ is_you: true, wins: 4, losses: 2, rank: 3, rank_prev: 5 }],
};

describe("Sim moments", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.useRealTimers();
  });

  it("pick reveal: card back, tap flips, the grade pops and Continue closes", async () => {
    vi.useFakeTimers();
    const onDone = vi.fn();
    render(<SimPickReveal pick={pick} board={[pick]} onDone={onDone} />);
    expect(screen.getByText("Tap to reveal your pick")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Tap to reveal your pick" }));
    await act(async () => {
      vi.advanceTimersByTime(300);
    });
    expect(screen.getAllByText("J. Pruitt").length).toBeGreaterThan(0);
    expect(screen.getByTestId("pick-grade").textContent).toBe("A-");
    expect(screen.getByText("+6 over his slot")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(onDone).toHaveBeenCalled();
  });

  it("the board holds back the pick being revealed until the card flips, then shows it", async () => {
    vi.useFakeTimers();
    const earlier = { ...(pick as object), pick_no: 3, round: 1, player: { id: "2", name: "Marcus Hale", pos: "RB", team: "DAL", headshot_id: "2" } } as never;
    render(<SimPickReveal pick={pick} board={[earlier, pick]} onDone={vi.fn()} />);
    // Face down: only the earlier pick is on the board; the pick under the card is not spoiled.
    expect(screen.getAllByTestId("board-row")).toHaveLength(1);
    expect(screen.queryByText("Jalen Pruitt")).toBeNull();
    expect(screen.getByText("Marcus Hale")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Tap to reveal your pick" }));
    await act(async () => {
      vi.advanceTimersByTime(300);
    });
    expect(screen.getAllByTestId("board-row")).toHaveLength(2);
    expect(screen.getByText("Jalen Pruitt")).toBeTruthy();
  });

  it("board rows use the short player name", () => {
    const earlier = { ...(pick as object), pick_no: 3, player: { id: "2", name: "Marcus Hale", pos: "RB", team: "DAL", headshot_id: "2" } } as never;
    render(<SimPickReveal pick={pick} board={[earlier, pick]} onDone={vi.fn()} />);
    expect(screen.getByText("Marcus Hale").getAttribute("data-short")).toBe("1");
  });

  it("week stamp rolls in, then stamps with the record and a J. Surname note", async () => {
    vi.useFakeTimers();
    render(<SimWeekStamp recap={recap} />);
    expect(screen.getByTestId("week-rolling").textContent).toBe("Scores rolling in...");
    await act(async () => {
      vi.advanceTimersByTime(1000);
    });
    expect(screen.getByTestId("week-stamp").textContent).toContain("4-2, up to 3rd");
    expect(screen.getByTestId("week-stamp").textContent).toContain("J. Pruitt led you with 31.4");
  });

  it("with Celebrations off nothing renders", () => {
    window.localStorage.setItem(SIM_CELEBRATIONS_KEY, "off");
    const { container } = render(<SimWeekStamp recap={recap} />);
    expect(container.textContent).toBe("");
  });
});
