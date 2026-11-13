import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { OPEN_SEARCH_EVENT } from "@/lib/orbSearch";
import type { SimGame } from "@/lib/simGame";

import { SimGameHeader, SimStatusChips } from "./SimGameHeader";

const game = {
  id: "g1",
  phase: "regular",
  week: 3,
  settings: { regular_weeks: 14 },
  dynasty: { season_no: 1, seasons: 5, year: 2026 },
  you: { team_id: "t1", name: "Trade Deadline Titans", wins: 0, losses: 2, ties: 0, rank: 12, pf: 132.3 },
  pending: { lineup_warnings: 1, inbox: 1 },
} as unknown as SimGame;

describe("SimGameHeader", () => {
  it("is one line: back, week + season, team chip, search, menu", () => {
    const onHub = vi.fn();
    const onTeam = vi.fn();
    const onMore = vi.fn();
    render(<SimGameHeader game={game} onHub={onHub} onTeam={onTeam} onMore={onMore} />);
    expect(screen.getByTestId("game-heading-phone")).toHaveTextContent("Wk 3/14");
    expect(screen.getByTestId("dynasty-progress-phone")).toHaveTextContent("S1/5");
    fireEvent.click(screen.getByRole("button", { name: "Back to all games" }));
    expect(onHub).toHaveBeenCalled();
    fireEvent.click(screen.getByTestId("sim-team-chip"));
    expect(onTeam).toHaveBeenCalledWith("t1");
    fireEvent.click(screen.getByRole("button", { name: /Game menu/ }));
    expect(onMore).toHaveBeenCalled();
  });

  it("search opens the GM menu's search through the shared event", () => {
    const heard = vi.fn();
    window.addEventListener(OPEN_SEARCH_EVENT, heard);
    render(<SimGameHeader game={game} onHub={() => {}} onTeam={() => {}} onMore={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: "Search players and pages" }));
    expect(heard).toHaveBeenCalled();
    window.removeEventListener(OPEN_SEARCH_EVENT, heard);
  });
});

describe("SimStatusChips", () => {
  it("shows tappable chips that jump to the fixing tab, nothing when clean", () => {
    const onTab = vi.fn();
    const { rerender } = render(<SimStatusChips game={game} onTab={onTab} />);
    fireEvent.click(screen.getByRole("button", { name: /1 lineup issue/ }));
    expect(onTab).toHaveBeenCalledWith("team");
    fireEvent.click(screen.getByRole("button", { name: /1 offer expiring/ }));
    expect(onTab).toHaveBeenCalledWith("trades");
    rerender(<SimStatusChips game={{ ...game, pending: { lineup_warnings: 0, inbox: 0 } } as unknown as SimGame} onTab={onTab} />);
    expect(screen.queryByTestId("sim-status-chips")).toBeNull();
  });
});
