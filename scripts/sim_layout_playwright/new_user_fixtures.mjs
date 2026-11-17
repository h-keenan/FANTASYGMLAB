// Mocked-API fixtures for new_user_smoke.mjs. The league-endpoint payloads (Today dashboard, team, needs, rankings, trade hub, GM Plan) are copied from
// module_scan.mjs so the smoke exercises the same shapes; update both when an endpoint's response shape changes. See docs/ui-patterns.md > New-user smoke.
const player = (id, name, position, slot, extra = {}) => ({ player_id: id, name, position, team: "DET", age: 25, tier: "starter", score: 2000, slot, suggested_starter: slot !== "BENCH", roster_slot: slot === "BENCH" ? "bench" : "starter", overall_rating: 88, injury_label: "", opportunity_label: null, ...extra });
const ranking = (i) => ({
  roster_id: String(i), team_name: `Team ${i}`, owner_name: `Owner ${i}`, owner_username: `o${i}`, avatar_url: null, wins: 8 - i, losses: i, ties: 0, record_label: `${8 - i}-${i}`,
  points_for: 1200 - i * 20, points_against: 1100, standing_rank: i, win_pct_label: "50%", points_for_label: "1,200", points_against_label: "1,100", playoff_status: i < 4 ? "In playoff position" : "", on_playoff_line: i === 4,
  power_rank: i, power_rank_tied: false, power_score: 9000 - i * 300, franchise_rank: i, franchise_rank_tied: false, franchise_score: 9000, draft_capital_rank: i, draft_capital_rank_tied: false, draft_capital_score: 400, pick_count: 6, first_rounders: 1,
  starter_rank: i, starter_rank_tied: false, starter_score: 6000, bench_rank: i, bench_rank_tied: false, bench_score: 2000, age_rank: i, age_rank_tied: false, average_age: 24 + i * 0.4,
  strategy: "contender", strategy_label: "Contender", archetype: "win_now_contender", archetype_label: "Win-Now Contender", archetype_explanation: null, archetype_strengths: ["RB"], archetype_recommendations: [],
  trade_tendency: "Neutral", transaction_activity_count: 3, firsts_acquired: 0, firsts_sent: 1, current_streak: 1, team_badges: [], injured_starters: 0, health_flag: "Stable",
});
export const FIX = {
  dashboard: {
    ok: true, quiet: false, quiet_reason: "", reason: "",
    items: [
      { category: "top_priority", headline: "Trade for a top-12 RB before the deadline", reason: "Bottom-third at RB.", supporting_context: null, destination: "trade_hub", route_player_id: "4046", route_player_name: "Test Back", route_player_position: "RB", route_player_team: "SF", route_player_tier: "starter", route_player_score: 88.4, route_player_injury_status: "", mentioned_players: [], recommendation_narrative: null, presentation: null, recommendation_id: "rec-1", tier_label: "Top Priority" },
      { category: "watch", headline: "Ashton Jeanty trending down", reason: "Usage is down 13% recently.", supporting_context: null, destination: "my_team", route_player_id: "5", route_player_name: "Ashton Jeanty", route_player_position: "RB", route_player_team: "LV", route_player_tier: "starter", route_player_score: 70, route_player_injury_status: "", mentioned_players: [], recommendation_narrative: null, presentation: null, recommendation_id: "rec-2", tier_label: "Watch" },
    ],
    team_snapshot: { wins: 7, losses: 6, ties: 0, health_flag: "Stable", key_injuries_summary: "", top_injury_impact_summary: "", top_injury_impact_players: [], injured_starters: 0, average_age: 26.4, power_rank: 2, power_rank_tied: false, franchise_rank: 1, franchise_rank_tied: true, starter_rank: 3, starter_rank_tied: false, bench_rank: 5, bench_rank_tied: false },
    trade_window: { trade_deadline_week: 11, current_week: 9, trade_deadline_passed: false, message: "" },
    entitlement: { is_premium: true, visible_count: 2, hidden_count: 0 },
  },
  "my-team": {
    ok: true, reason: "", roster_id: "1",
    starters: [player("qb1", "Test Quarterback", "QB", "QB", { overall_rating: 95 }), player("rb1", "Test Running Back", "RB", "RB"), player("wr1", "Test Receiver", "WR", "WR")],
    bench: [player("wr2", "Test Bench Receiver", "WR", "BENCH", { overall_rating: 61 }), player("te1", "Test IR Tight End", "TE", "BENCH", { roster_slot: "ir", injury_label: "IR", overall_rating: null })],
  },
  "my-team-needs": {
    ok: true, reason: "", show_franchise_construction: true, superflex: false, te_premium: false, strengths: ["RB"], weaknesses: ["WR"],
    biggest_need: { label: "Biggest Need", value: "Wide Receiver", note: "Clearest current deficiency." },
    position_groups: [
      { position: "QB", classification: "covered", reasons: ["QB is covered."], upgrade_opportunity: false, temporary_injury_pressure: false },
      { position: "RB", classification: "strength", reasons: ["RB is a strength."], upgrade_opportunity: false, temporary_injury_pressure: false },
      { position: "WR", classification: "short_term_need", reasons: ["WR is below the baseline."], upgrade_opportunity: false, temporary_injury_pressure: false },
    ],
  },
  "team-rankings": { ok: true, reason: "", season: "2026", standings_available: true, standings_message: "", week_label: "Week 9", teams: [1, 2, 3, 4, 5, 6, 7, 8].map(ranking) },
  "value-signals": { ok: true, status: "ok", span_days: 12, method: "Method.", buy_low: [{ player_id: "9", name: "Test Receiver", position: "WR", team: "DET", age: 24, injury_status: "", signal: "buy_low", rating_change: -4, production_percentile: 80, value_percentile: 50 }], sell_high: [] },
  multi: { ok: true, locked: false, idea_count: 0, ideas: [], reason: "no_fit" },
  "trade-hub": {
    ok: true, reason: "", team_strategy: "contender", posture_sentence: "You are contending.", hold: null,
    ideas: [1, 2, 3].map((n) => ({ partner_team_name: `Team ${n + 1}`, partner_team_avatar_url: null, rationale: "Fills your WR need with a surplus RB.", trade_gain: 400 * n, confidence_label: "High", market_realism_label: "Realistic", reasoning_tags: [], package: { send: [{ asset_type: "player", player_id: `s${n}`, name: "Test Running Back", position: "RB", team: "DET", age: 25, score: 1000, tier: "starter" }, { asset_type: "player", player_id: `s${n}b`, name: "Test Bench Receiver", position: "WR", team: "DET", age: 24, score: 300, tier: "bench" }], receive: [{ asset_type: "player", player_id: `g${n}`, name: "Opponent Wide Receiver", position: "WR", team: "SEA", age: 24, score: 1700, tier: "starter" }], value_edge: "+400", confidence: "High" }, category: "need", value_edge_band: "Fair", impact_tag: "Lineup", landed_gm_target_player_ids: [], send_score: 1000, receive_score: 1400, recommendation_id: `idea-${n}` })),
    entitlement: { is_premium: true, free_limit: 3, approved_count: 3, visible_count: 3, hidden_count: 0 },
    trade_window: { trade_deadline_week: 11, current_week: 9, trade_deadline_passed: false, message: "" },
  },
};
const tradeItem = (n) => ({ partner_team_name: `Team ${n + 1}`, my_player: "Test Running Back", their_player: "Opponent Wide Receiver", my_player_id: `s${n}`, their_player_id: `g${n}`, their_player_injury_display: "", rationale: "Fills your WR need with a surplus RB.", trade_confidence_label: "High", priority: n, send_assets: [], receive_assets: [], trade_gain: 300 * n, source: "x" });
FIX["gm-plan"] = { ok: true, quiet: false, reason: "", is_premium: true, upsell: null, season_phase_label: "In season", team_stance: "competing", team_stance_label: "Competing", headline: "Push for a title: your WR room is the one gap.", trade_window: { trade_deadline_week: 11, current_week: 9, trade_deadline_passed: false, message: "" }, focus_areas: [
  { key: "standing", title: "Where you stand", status: "signal", items: [{ rank: 2, label: "Roster Power", total_teams: 8 }, { wins: 7, losses: 6, ties: 0 }], watch_for: "" },
  { key: "trade_opportunities", title: "Trade opportunities", status: "signal", items: [1, 2, 3].map(tradeItem), watch_for: "" },
  { key: "roster_construction", title: "Roster construction", status: "no_signal", items: [], watch_for: "No glaring holes." },
] };

export const LID = "1221647449446162432";
export const LEAGUE_NAME = "Smoke Dynasty League";
export const SLEEPER_USERNAME = "smokeuser";
export const sleeperLookup = { ok: true, status: "ok", message: "", username: SLEEPER_USERNAME, leagues: [{ league_id: LID, name: LEAGUE_NAME, season: "2026", total_rosters: 8 }] };
export const session = (id = "smoke-user-1") => ({ access_token: "a.b.c", refresh_token: "r", token_type: "bearer", expires_in: 99999, expires_at: Math.floor(Date.now() / 1000) + 99999, user: { id, aud: "authenticated", role: "authenticated", email: "smoke@example.com", app_metadata: {}, user_metadata: {}, created_at: "2026-01-01T00:00:00Z" } });
// GET /v1/me: the ONE input planOf() (web-next/src/lib/plan.ts) reads. "premium" is Pro, "free" is Free.
export const me = (entitlement) => ({ ok: true, user: { id: "smoke-user-1", email: "smoke@example.com", entitlement, sleeper_username: SLEEPER_USERNAME, profile_status: "ok", league_cap: entitlement === "free" ? 1 : 5, trial_ends_at: "" }, premium_benefits: ["Unlimited leagues"], premium_comparison: [{ key: "leagues", label: "Leagues", free: "1", pro: "Unlimited" }] });
export const FREE_GM_PLAN = { ok: true, quiet: false, reason: "", is_premium: false, upsell: { title: "Your season-arc roadmap", body: "GM Plan is a Pro feature." }, focus_areas: [] };
export const FREE_PORTFOLIO = { ok: true, is_premium: false, upsell: null, lens: "Dynasty", saved_leagues: [], leagues: [], failed_leagues: [] };
