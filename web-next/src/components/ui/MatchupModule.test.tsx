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
  it("latest big play: newest line, tap expands the last 3, opponent plays stay neutral, hidden when empty", () => {
    const now = Date.now();
    const plays = [
      { id: "a", at: now - 120_000, player_id: "11", name: "Ja'Marr Chase", position: "WR", team: "CIN", side: "mine" as const, points: 9.8, description: "38-yd TD catch", approx: false },
      { id: "b", at: now - 600_000, player_id: "22", name: "James Cook", position: "RB", team: "BUF", side: "opponent" as const, points: 4.2, description: "TD run and 45 yds", approx: true },
      { id: "c", at: now - 900_000, player_id: "33", name: "Some Guy", position: "QB", team: "KC", side: "mine" as const, points: -2, description: "interception", approx: false },
      { id: "d", at: now - 990_000, player_id: "44", name: "Fourth Guy", position: "WR", team: "KC", side: "mine" as const, points: 3, description: "25-yd catch", approx: false },
    ];
    const { rerender } = render(<MatchupHeroCard model={model} bigPlays={plays} />);
    expect(screen.getAllByTestId("matchup-big-play-item")).toHaveLength(1);
    const item = screen.getByTestId("matchup-big-play-item");
    expect(item).toHaveTextContent("Chase · 38-yd TD catch");
    expect(item).toHaveTextContent("2m ago");
    expect(item).toHaveTextContent("for You");
    expect(screen.getByTestId("matchup-big-play-points")).toHaveTextContent("+9.8");
    expect(screen.getByTestId("matchup-big-play-points").style.color).toBe("var(--color-success)");
    fireEvent.click(screen.getByTestId("matchup-big-play-toggle"));
    const items = screen.getAllByTestId("matchup-big-play-item");
    expect(items).toHaveLength(3);
    expect(items[1]).toHaveTextContent("approx.");
    expect(items[1]).toHaveTextContent("for Mike");
    expect(screen.getAllByTestId("matchup-big-play-points")[1].style.color).toBe("var(--color-text-secondary)");
    expect(screen.getAllByTestId("matchup-big-play-points")[2].style.color).toBe("var(--color-text-secondary)");
    rerender(<MatchupHeroCard model={model} bigPlays={[]} />);
    expect(screen.queryByTestId("matchup-big-play")).toBeNull();
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
