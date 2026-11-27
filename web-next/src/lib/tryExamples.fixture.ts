/** Test fixture: the /v1/public/try-examples payload shape with synthetic players. */
const side = (id: string, name: string, points: number) => ({
  player_id: id, name, position: "WR", team: "AAA", tier: "starter", slot: "FLEX", points, projection_status: "ok", injury_label: "",
});

export const REAL_PAYLOAD = {
  ok: true,
  season: 2026,
  week: 12,
  start_sit: {
    move: {
      slot: "FLEX",
      start: side("1", "Real Alpha", 13.4),
      over: side("2", "Real Bravo", 12.6),
      over_reason: null,
      gain: 0.8,
      locked: false,
      range: {
        start: { name: "Real Alpha", projected: 13.4, low: 8.4, high: 20.4 },
        over: { name: "Real Bravo", projected: 12.6, low: 7.6, high: 19.6 },
        stance: null,
        lean: null,
      },
    },
    matchup_note: "Real Alpha vs XXX: they allow 38.0 PPR points per game to WR (+20% vs league average, weak defense).",
  },
  waivers: {
    adds: [
      {
        player_id: "5", name: "Wire Echo", position: "WR", team: "AAA", age: 24, score: 2100, position_rank: 50, overall_rank: 70, overall_rating: 66,
        tier: "backup", trending_adds_24h: 5400, trending_rank: 1, roster_pct: 12, injury_cover_for: "Hurt Golf",
        reason: "5,400 adds on Sleeper in the last 24 hours and only 12% rostered, ranked WR50 on the dynasty board.",
        bid: { low: 6, high: 11, budget: 100 },
      },
    ],
  },
};
