import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { MatchupHeroCard, MatchupTicker } from "./MatchupModule";
import { matchupCardModel, matchupSwingPlayers } from "@/lib/matchupModules";

const swing = matchupSwingPlayers(
  [
    { playerId: "11", name: "Ja'Marr Chase", position: "WR", team: "CIN", low: 8, high: 26, done: false, side: "mine" },
    { playerId: "22", name: "James Cook", position: "RB", team: "BUF", low: 4, high: 12, done: false, side: "opponent" },
  ],
  "Mike",
);
const model = matchupCardModel({ week: 7, live: true, final: false, myName: "You", opponentName: "Mike", myScore: 112.4, opponentScore: 98.1, myProjected: 131.2, opponentProjected: 124, winPercent: 71, kickedOff: true, playersLeft: 3, swing });

describe("MatchupModule", () => {
  it("hero: score, win chip, bar, detail and swing players with avatars that open the peek", () => {
    const onOpen = vi.fn();
    render(<MatchupHeroCard model={model} onOpenPlayer={onOpen} action={<button>Open lineup</button>} />);
    expect(screen.getByTestId("matchup-kicker")).toHaveTextContent("WEEK 7 · LIVE");
    expect(screen.getByTestId("matchup-win-chip")).toHaveTextContent("71% win");
    expect(screen.getByTestId("matchup-my-score")).toHaveTextContent("112.4");
    expect(screen.getByRole("img", { name: "Win chance 71%" })).toBeInTheDocument();
    expect(screen.getByTestId("matchup-detail")).toHaveTextContent("Proj final 131.2 - 124.0 · 3 players left");
    const players = screen.getAllByTestId("matchup-swing-player");
    expect(players).toHaveLength(2);
    expect(players[0].querySelector("img")).not.toBeNull();
    expect(players[1]).toHaveTextContent("±4 for Mike");
    fireEvent.click(players[0].querySelector("button")!);
    expect(onOpen).toHaveBeenCalledWith(expect.objectContaining({ name: "Ja'Marr Chase" }));
    expect(document.body.innerHTML).not.toMatch(/--color-action|--color-premium/);
  });
  it("ticker: one line that links to the matchup page", () => {
    render(<MatchupTicker model={model} week={7} href="/matchup/L" />);
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "/matchup/L");
    expect(link).toHaveTextContent("WK 7");
    expect(link).toHaveTextContent("You 112.4 - 98.1 Mike");
    expect(link).toHaveTextContent("71%");
  });
});
