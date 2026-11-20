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
  it("live sections: one module, compact rows that expand on tap; plays carry the clock; opponent plays stay neutral", () => {
    const now = Date.now();
    const sections = {
      live: true,
      games: [{ key: "HOU-IND", score: "IND 3 - 14 HOU", clock: "Q2 5:54", situation: "2nd & 7 at HOU 25", live: true }],
      plays: [
        { id: "a", at: now - 120_000, playerId: "11", name: "Ja'Marr Chase", side: "mine" as const, points: 9.8, detail: "38-yd TD catch", approx: false, clock: "Q2 6:32", soFar: false },
        { id: "b", at: now - 600_000, playerId: "22", name: "James Cook", side: "opponent" as const, points: 4.2, detail: "TD run and 45 yds", approx: true, clock: null, soFar: false },
        { id: "c", at: now, playerId: "33", name: "Some Guy", side: "mine" as const, points: 6, detail: "1 TD so far", approx: true, clock: "Q2 6:32", soFar: true },
      ],
      ageSeconds: 12,
      projectedLine: "Proj final 118.4 - 109.2",
      projected: { mine: "118.4", opponent: "109.2" },
    };
    const { rerender } = render(<MatchupHeroCard model={model} liveSections={sections} />);
    // one module: no separate big-play card or live feed card
    expect(screen.queryByTestId("live-feed")).toBeNull();
    expect(screen.getByTestId("matchup-section-games-toggle")).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByTestId("matchup-game")).toHaveTextContent("Q2 5:54");
    expect(screen.getByTestId("matchup-game")).toHaveTextContent("2nd & 7 at HOU 25");
    expect(screen.getByTestId("matchup-section-projected-toggle")).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(screen.getByTestId("matchup-section-projected-toggle"));
    expect(screen.getByTestId("matchup-section-projected-toggle")).toHaveAttribute("aria-expanded", "true");
    const items = screen.getAllByTestId("matchup-big-play-item");
    expect(items).toHaveLength(3);
    expect(items[0]).toHaveTextContent("Chase · 38-yd TD catch");
    expect(items[0]).toHaveTextContent("Q2 6:32");
    expect(items[0]).toHaveTextContent("2m ago");
    expect(items[0]).toHaveTextContent("for You");
    expect(items[1]).toHaveTextContent("approx.");
    expect(items[1]).toHaveTextContent("for Mike");
    expect(items[2]).toHaveTextContent("so far");
    const points = screen.getAllByTestId("matchup-big-play-points");
    expect(points[0].style.color).toBe("var(--color-success)");
    expect(points[1].style.color).toBe("var(--color-text-secondary)");
    rerender(<MatchupHeroCard model={model} liveSections={{ ...sections, plays: [] }} />);
    expect(screen.getByTestId("matchup-plays-quiet")).toHaveTextContent("All quiet · last checked 12s ago");
    rerender(<MatchupHeroCard model={model} />);
    expect(screen.queryByTestId("matchup-live-sections")).toBeNull();
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
