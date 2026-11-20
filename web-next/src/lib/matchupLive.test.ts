import { describe, expect, it } from "vitest";

import { liveGamesFromStarters, mergeLivePlays, quietLabel } from "./matchupLive";

describe("matchupLive", () => {
  it("one row per game, live first, score home-last, situation only while live", () => {
    const games = liveGamesFromStarters([
      { team: "HOU", game_status: "in_progress", game_clock_label: "Q2 5:54", game_situation: "2nd & 7 at HOU 25", game_opponent: "IND", game_is_home: true, game_team_score: 14, game_opponent_score: 3 },
      { team: "IND", game_status: "in_progress", game_clock_label: "Q2 5:54", game_opponent: "HOU", game_is_home: false, game_team_score: 3, game_opponent_score: 14 },
      { team: "KC", game_status: "final", game_opponent: "LV", game_is_home: true, game_team_score: 27, game_opponent_score: 20, game_situation: "ignored" },
      { team: "SF", game_status: "scheduled", game_opponent: "MIN" },
    ]);
    expect(games).toHaveLength(2);
    expect(games[0]).toMatchObject({ live: true, clock: "Q2 5:54", score: "IND 3 - 14 HOU", situation: "2nd & 7 at HOU 25" });
    expect(games[1]).toMatchObject({ live: false, clock: "Final", situation: null });
  });
  it("merges server and client plays, dedupes, so-far sorts last", () => {
    const rows = mergeLivePlays(
      [
        { id: "s1", at: 10, player_id: "1", name: "A B", side: "mine", points: 6, description: "TD catch", clock: "Q1 3:00" },
        { id: "s2", at: 99, player_id: "2", name: "C D", side: "mine", points: 6, description: "1 TD so far", so_far: true },
      ],
      [
        { id: "c1", at: 20, playerId: "1", name: "A B", side: "mine", points: 6, detail: "TD catch", approx: false },
        { id: "c2", at: 30, playerId: "3", name: "E F", side: "opponent", points: 4, detail: "22-yd run", approx: false },
      ],
    );
    expect(rows.map((r) => r.id)).toEqual(["c2", "s1", "s2"]);
    expect(rows[1].clock).toBe("Q1 3:00");
    expect(rows[2].soFar).toBe(true);
  });
  it("quiet label", () => {
    expect(quietLabel(null)).toBe("All quiet");
    expect(quietLabel(12)).toBe("All quiet · last checked 12s ago");
    expect(quietLabel(130)).toBe("All quiet · last checked 2m ago");
  });
});
