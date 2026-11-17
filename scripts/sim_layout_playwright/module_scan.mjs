// Module-template scan (docs/audits/2026-11-module-templates-rollout.md): Today, Team, Trades, League, Matchup, Waivers, Players, Trade Finder/Analyzer, GM Plan, Games, Recaps, Draft Center and the public sample league at 390 and 1440 WITH data (desktop also checks one header bar).
// Unlike app_audit.mjs (empty stubs) this answers the league endpoints with fixtures, then checks per page:
//   - no horizontal overflow (scrollWidth <= width),
//   - every collapsed compact module shows >= 12 characters of summary (the same rule as the unit tests),
//   - at most one tablist/tab row of the page family (the family strip) and no empty section headers,
//   - total scroll height and module count (reported, so a page that grows shows up in the diff).
// Start the dev server first:
//   NEXT_PUBLIC_SUPABASE_URL=https://dummy.supabase.co NEXT_PUBLIC_SUPABASE_ANON_KEY=x NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npx next dev -p 3197
//   PW_CORE=.../playwright-core/index.mjs BASE=http://localhost:3197 OUT=/tmp/module-scan [WIDTHS=360,390] node scripts/sim_layout_playwright/module_scan.mjs
import fs from "fs";
import { GUARD } from "./guard_checks.mjs";
import { createMock } from "./simmock.mjs";

const pw = await import(process.env.PW_CORE || "playwright-core");
// WebKit by default (coridian_ sees these pages in iPhone Safari); BROWSER=chromium [CHROME=path] for Chromium.
const engine = process.env.BROWSER === "chromium" ? pw.chromium : pw.webkit;
// GUARD=1 adds the layout guard (guard_checks.mjs: no sideways scroll, nothing past its card / viewport, no ellipsis, no clipped text, controls >= 44px) at every width; LARGE=1 re-runs at 125% text.
const GUARD_ON = process.env.GUARD === "1";
const LARGE = process.env.LARGE === "1";
const guardViolations = [];
// AXE=1 runs axe-core (WCAG 2.x A/AA) on each route and fails on serious / critical issues (docs/audits/2026-11-accessibility.md).
// AXE_CORE=path/to/axe.min.js (CI installs axe-core next to playwright-core); AXE_ROUTES overrides the default key-route list.
const AXE_ON = process.env.AXE === "1";
const AXE_ONLY = AXE_ON && process.env.AXE_ONLY === "1";
const AXE_ROUTES = (process.env.AXE_ROUTES || "today,team,trades,matchup,waivers,gm-plan").split(",");
const axeViolations = [];
const axeSource = AXE_ON ? fs.readFileSync(process.env.AXE_CORE || "node_modules/axe-core/axe.min.js", "utf8") : "";
const BASE = process.env.BASE || "http://localhost:3197";
const OUT = process.env.OUT || "/private/tmp/claude-501/module-scan";
const WIDTHS = (process.env.WIDTHS || (process.env.GUARD === "1" ? "320,360,390,430" : "390,1440")).split(",").map(Number);
const LID = "1221647449446162432";
// Audit knobs (docs/audits/2026-11-ui-consistency-audit-4.md): NAV=bottom opens every page in the phone shell (header + bottom pill) instead of the legacy
// header + orb, FULL=1 saves full-page screenshots, METRICS=1 adds the design-token census (radii, type sizes, gold, button heights) to report.json.
const NAV = process.env.NAV || "";
// First-module budget (batch B, docs/audits/2026-11-ui-audit-e2e.md P0-2): at phone width the first card/row must start within TOP_BUDGET px below the sticky nav.
// Pages whose first row legitimately sits under a control stack are ratcheted at their current value (the number may go down, never up); fixture-only or
// banner pages are exempt.
const TOP_BUDGET = 110;
const TOP_BUDGET_OVERRIDES = {}; // batch H: every override is gone, all pages pass the 110px budget
const TOP_EXEMPT = new Set(["sample-league", "landing", "commissioner", "commissioner-missing", "trade-analyzer", "trade-analyzer-missing"]);
// OVERFLOW=1: every route (incl. the overflow-only ones), failing ONLY on a sideways-scrolling document and naming the elements that cause it.
const OVERFLOW_MODE = process.env.OVERFLOW === "1";
const FULL = process.env.FULL === "1";
// SHEET=more|search: after each page loads, open the navigation sheet from the bottom bar's More button or the header Search icon and screenshot it as <route>-<sheet>-<width>.png (use with NAV=bottom, ONLY=today).
const SHEET = process.env.SHEET || "";
const METRICS = process.env.METRICS === "1";
fs.mkdirSync(OUT, { recursive: true });

const player = (id, name, position, slot, extra = {}) => ({ player_id: id, name, position, team: "DET", age: 25, tier: "starter", score: 2000, slot, suggested_starter: slot !== "BENCH", roster_slot: slot === "BENCH" ? "bench" : "starter", overall_rating: 88, injury_label: "", opportunity_label: null, ...extra });
const ranking = (i) => ({
  roster_id: String(i), team_name: `Team ${i}`, owner_name: `Owner ${i}`, owner_username: `o${i}`, avatar_url: null, wins: 8 - i, losses: i, ties: 0, record_label: `${8 - i}-${i}`,
  points_for: 1200 - i * 20, points_against: 1100, standing_rank: i, win_pct_label: "50%", points_for_label: "1,200", points_against_label: "1,100", playoff_status: i < 4 ? "In playoff position" : "", on_playoff_line: i === 4,
  power_rank: i, power_rank_tied: false, power_score: 9000 - i * 300, franchise_rank: i, franchise_rank_tied: false, franchise_score: 9000, draft_capital_rank: i, draft_capital_rank_tied: false, draft_capital_score: 400, pick_count: 6, first_rounders: 1,
  starter_rank: i, starter_rank_tied: false, starter_score: 6000, bench_rank: i, bench_rank_tied: false, bench_score: 2000, age_rank: i, age_rank_tied: false, average_age: 24 + i * 0.4,
  strategy: "contender", strategy_label: "Contender", archetype: "win_now_contender", archetype_label: "Win-Now Contender", archetype_explanation: null, archetype_strengths: ["RB"], archetype_recommendations: [],
  trade_tendency: "Neutral", transaction_activity_count: 3, firsts_acquired: 0, firsts_sent: 1, current_streak: 1, team_badges: [], injured_starters: 0, health_flag: "Stable",
});
const FIX = {
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

// Matchup / Waivers / Players fixtures (page migration pass 2).
const mStarter = (id, name, position, pts, slot) => ({ player_id: id, name, position, team: "SF", age: 25, status: "Active", injury_status: null, injury_label: "", ruled_out: false, tier: "starter", score: 1500, slot, suggested_starter: true, roster_slot: "starter", opportunity_label: "Lead back", overall_rating: 82, why: "", projection: { status: "ok", point_estimate: pts, low: pts - 3, high: pts + 3, confidence: "medium", opponent: "SEA" } });
const mSide = (rid, name, w, l, val, extra = {}) => ({ roster_id: rid, team_name: name, owner_name: "o", avatar_url: null, wins: w, losses: l, ties: 0, season_value_total: val, starters_basis: "suggested_optimal_lineup", real_starters: [], real_points: null, has_live_data: false, real_starters_basis: "sleeper_actual_lineup", real_empty_slots: [], starters: [mStarter(`${rid}q`, `Quarterback ${rid}`, "QB", 20, "QB"), mStarter(`${rid}r`, `Running Back ${rid}`, "RB", 15, "RB"), mStarter(`${rid}w`, `Wide Receiver ${rid}`, "WR", 14, "WR")], ...extra });
const EDGES = [{ position: "RB", my_points: 30, opponent_points: 13, edge: 16.7, my_count: 2, opponent_count: 2, unmodeled: 0 }, { position: "QB", my_points: 20, opponent_points: 19.6, edge: 0.4, my_count: 1, opponent_count: 1, unmodeled: 0 }, { position: "TE", my_points: 8, opponent_points: 11.2, edge: -3.2, my_count: 1, opponent_count: 1, unmodeled: 0 }, { position: "WR", my_points: 30, opponent_points: 34.6, edge: -4.6, my_count: 3, opponent_count: 3, unmodeled: 0 }];
FIX.matchup = { ok: true, week: 10, my_team: mSide("1", "Not Your Dad's Dih", 3, 6, 45719), opponent: mSide("2", "Shiesty", 4, 5, 48673), comparison: { my_season_value: 45719, opponent_season_value: 48673, margin: -2954, edge: "opponent", headline: "", basis: "season_value", basis_label: "" }, real_comparison: null, win_probability: { available: true, probability: 0.57, my_projected_total: 118.3, opponent_projected_total: 109.7, coverage: { my: 1, opponent: 1 } }, game_state: null, position_edges: { actual: null, suggested: EDGES }, suggested_moves: [{ slot: "RB", start: { player_id: "b1", name: "Aaron Jones", position: "RB", team: "MIN", tier: "starter", slot: "RB", points: 15.7, projection_status: "ok", injury_label: "" }, over: { player_id: "s2", name: "Tyrone Tracy", position: "RB", team: "NYG", tier: "starter", slot: "RB", points: 7.4, projection_status: "ok", injury_label: "" }, over_reason: null, gain: 8.3, locked: false }], basis: "season_value", basis_label: "", reason: "" };
const wDrop = { player_id: "d1", name: "Tutu Atwell", position: "WR", team: "LAR", age: 26, status: "Active", injury_status: "", value: 300, start_share: 0, usage_flag: null, reasons: ["never starts in your best lineup"], effect: { lineup_points_ros: 0, lineup_points_per_week: 0, this_week: 0, value_delta: 300, score: 900, weeks: 9 }, action: "drop" };
const wAdd = (id, name, pos, team, score, lo, hi, why) => ({ player_id: id, name, position: pos, team, age: 24, status: "Active", injury_status: "", tier: "starter", opportunity_label: "Strong Opportunity", score, position_rank: 30, overall_rank: 90, stale_free_agent: false, injury_replacement_fit: false, sleeper_trending_add: id !== "w3", sleeper_trending_add_count: 900, sleeper_trending_add_rank: 4, overall_rating: 75, recommendation_label: "Add", recommendation_tone: "opportunity", faab: { low_bid: lo, high_bid: hi, pct_low: lo, pct_high: hi, remaining: 81, dollars_known: true, label: "", reasons: [why], why }, confidence_label: "High", confidence_reason: "", usage_flag: id === "w1" || id === "w2" ? { label: "Usage +40%", tone: "positive", explanation: "Snap share up 40% over four weeks." } : null, drop_suggestion: { status: "ok", add: { player_id: id, name, position: pos }, roster: { active_limit: 22, active_count: 22, open_spots: 0, is_full: true, reserve_slots: 3, reserve_used: 1, taxi_slots: 0, taxi_used: 0 }, drop_required: true, drop: wDrop, alternatives: [], no_good_drop: false, why: "" } });
const WA = [wAdd("w0", "Jalen Nailor", "WR", "LV", 2608, 8, 12, "Best on the wire for your WR need"), wAdd("w1", "Marvin Mims Jr.", "WR", "DEN", 1786, 3, 5, "Rival demand: two teams need WR"), wAdd("w2", "Khalil Herbert", "RB", "ATL", 1283, 2, 4, "Role rising"), wAdd("w3", "John Metchie III", "WR", "CAR", 1223, 1, 3, "Rival demand"), wAdd("w4", "Coleman Owen", "WR", "GB", 1100, 1, 2, "Role rising")];
FIX.waivers = { ok: true, reason: "", players: WA, priority_adds: WA, needed_positions: ["WR"], available_count: 120, avg_wire_score: 650, injured_starters: 0, injury_positions: [], stash_candidates: [], watchlist_candidates: [], faab_targets: [], entitlement: { is_premium: true } };
FIX.rankings = { ok: true, players: Array.from({ length: 12 }, (_, i) => ({ player_id: `r${i}`, name: `Ranked Player ${i}`, position: ["QB", "RB", "WR", "TE"][i % 4], team: "DET", age: 24 + (i % 5), status: "Active", injury_status: null, tier: "starter", score: 5000 - i * 200, overall_rank: i + 1, position_rank: Math.floor(i / 4) + 1, rank_unavailable_reason: null, opportunity_label: null, overall_rating: 90 - i })) };

// Pass 3 fixtures: GM Plan, Games, Draft Center (Recaps / Trade Analyzer use the generic empty shapes).
const tradeItem = (n) => ({ partner_team_name: `Team ${n + 1}`, my_player: "Test Running Back", their_player: "Opponent Wide Receiver", my_player_id: `s${n}`, their_player_id: `g${n}`, their_player_injury_display: "", rationale: "Fills your WR need with a surplus RB.", trade_confidence_label: "High", priority: n, send_assets: [], receive_assets: [], trade_gain: 300 * n, source: "x" });
FIX["gm-plan"] = { ok: true, quiet: false, reason: "", is_premium: true, upsell: null, season_phase_label: "In season", team_stance: "competing", team_stance_label: "Competing", headline: "Push for a title: your WR room is the one gap.", trade_window: { trade_deadline_week: 11, current_week: 9, trade_deadline_passed: false, message: "" }, focus_areas: [
  { key: "standing", title: "Where you stand", status: "signal", items: [{ rank: 2, label: "Roster Power", total_teams: 8 }, { wins: 7, losses: 6, ties: 0 }], watch_for: "" },
  { key: "trade_opportunities", title: "Trade opportunities", status: "signal", items: [1, 2, 3].map(tradeItem), watch_for: "" },
  { key: "roster_construction", title: "Roster construction", status: "no_signal", items: [], watch_for: "No glaring holes." },
] };
const gOdds = (i) => ({ roster_id: String(i), team_name: `Team ${i}`, avatar_url: null, record_label: `${8 - i}-${i}`, playoff_probability: 90 - i * 10, title_probability: 30 - i * 3, median_seed: i, mine: i === 3 });
FIX["games/season-sim"] = { ok: true, reason: "", is_premium: true, upsell: null, my_roster_id: "3", my_team: { ...gOdds(3), median_final_wins: 9, median_final_losses: 5, clinched: false, eliminated: false }, teams: [1, 2, 3, 4, 5, 6, 7, 8].map(gOdds), roster: [{ player_id: "r1", name: "Test Running Back", position: "RB", team: "DET", injury_status: null, tier: "starter" }], playoff_teams: 6, title_odds: { available: true, reason: "" }, current_week: 9, weeks_remaining: 5, trials: 2000 };
FIX["draft-center"] = { ok: true, reason: "", posture: { label: "Pick-Rich Rebuilder", note: "Rebuild path already has strong pick insulation.", tone: "opportunity", draft_capital_rank: 1, draft_capital_rank_tied: false, draft_capital: 4200, future_draft_capital_rank: 2, future_draft_capital_rank_tied: false, future_draft_capital: 2000, first_rounders: 3, pick_count: 9, strategy_display: "Rebuild", power_rank: 5, power_rank_tied: false, franchise_rank: 4, franchise_rank_tied: false }, posture_reason: "", decision_cards: [{ label: "Best Pick Buyers", title: "Who will pay for picks", tone: "opportunity", items: ["Team 2 needs RB depth."] }], partner_cards: [{ label: "Pick-Rich Teams", title: "Teams with extra firsts", tone: "neutral", items: ["Team 4 holds 4 firsts."] }], is_premium: true, upsell: null };
FIX["draft-picks"] = { ok: true, reason: "", picks: [1, 2, 3].flatMap((r) => [2026, 2027].map((y) => ({ pick_id: `${y}-${r}`, label: `${y} Round ${r}`, score: 900 - r * 200, season: y, round: r, original_roster_id: "1", owner_roster_id: "1", original_team_name: "Team 1", owner_team_name: "Team 1", pick_tier: "Early", projected_pick_range: "1.03-1.06" }))) };
FIX["my-roster"] = { ok: true, roster: { roster_id: "1" } };

// Weekly recap fixture (League > Recaps): every story type, a long team name, a 3-team trade is covered by the unit tests.
const rTeams = ["Epstein's List", "The tickle monster", "Revivalry Dynasty Superfans Of The Capital", "Not Your Dad's Dih", "Shiesty"];
const rAsset = (id, name, position, team) => ({ kind: "player", name, player_id: id, position, team });
FIX["team-profiles"] = { ok: true, profiles: Object.fromEntries(rTeams.map((t, i) => [String(i + 1), { team_name: t, owner_name: `Owner ${i + 1}`, username: `o${i + 1}`, avatar_id: "", avatar_url: "", roster_id: i + 1, owner_id: `u${i + 1}` }])) };
const rStory = (o) => ({ story_type: "performance", title: "Week's scoring leader", summary: "The clearest scoring week belonged to Epstein's List: 183.4.", glyph: "x", primary_team: rTeams[0], secondary_team: "", primary_roster_id: "1", secondary_roster_id: "", players: [], metric_label: "Points", metric_value: "183.4", history_week: 9, confidence: "recorded", editorial_label: "", history_filter: "", ...o });
FIX.recap = { ok: true, reason: "", max_completed_week: 9, my_roster_id: "3", recap: { recap_id: "r9", league_id: LID, season: "2026", week: 9, headline: "League memory - Week 9", incomplete: false, empty_reason: "", stories: [
  rStory({}),
  rStory({ story_type: "performance_low", title: "The week's toughest scoreline", summary: "The toughest scoring week belonged to The tickle monster: 57.9.", primary_team: rTeams[1], primary_roster_id: "2", metric_value: "57.9" }),
  rStory({ story_type: "matchup", title: "Biggest matchup", summary: "Revivalry Dynasty Superfans Of The Capital defeated Shiesty 150.2-109.7 (margin 40.5).", primary_team: rTeams[2], primary_roster_id: "3", secondary_team: rTeams[4], secondary_roster_id: "5", metric_label: "Margin", metric_value: "40.5", winner_points: 150.2, loser_points: 109.7, history_filter: "" }),
  rStory({ story_type: "matchup_close", title: "Down to the wire", summary: "Not Your Dad's Dih edged The tickle monster 101.3-100.5 (margin 0.8).", primary_team: rTeams[3], primary_roster_id: "4", secondary_team: rTeams[1], secondary_roster_id: "2", metric_label: "Margin", metric_value: "0.8", winner_points: 101.3, loser_points: 100.5 }),
  rStory({ story_type: "waiver", title: "Waiver winner", summary: "Revivalry Dynasty Superfans Of The Capital spent $14 FAAB to add Jalen Nailor.", primary_team: rTeams[2], primary_roster_id: "3", players: ["Jalen Nailor"], metric_label: "FAAB", metric_value: "$14", history_filter: "Waivers", player_assets: [rAsset("9001", "Jalen Nailor", "WR", "LV")] }),
  rStory({ story_type: "waiver_low", title: "Cheapest add", summary: "Shiesty added Coleman Owen for just $1 FAAB.", primary_team: rTeams[4], primary_roster_id: "5", players: ["Coleman Owen"], metric_label: "FAAB", metric_value: "$1", history_filter: "Waivers", player_assets: [rAsset("9002", "Coleman Owen", "WR", "GB")] }),
  rStory({ story_type: "trade", title: "Trade of the week", summary: "Epstein's List received Aaron Jones and a 2027 R2; Shiesty received Tyrone Tracy.", primary_team: rTeams[0], secondary_team: rTeams[4], primary_roster_id: "1", secondary_roster_id: "5", players: ["Aaron Jones", "Tyrone Tracy"], metric_label: "", metric_value: "", history_filter: "Trades", editorial_label: "Too Early to Tell", value_lenses: [{ lens: "now", label: "Current market", note: "Current values only." }], sides: [{ team_name: rTeams[0], roster_id: "1", assets: [rAsset("9003", "Aaron Jones", "RB", "MIN"), { kind: "pick", name: "2027 R2", label: "2027 Round 2", season: "2027", round: 2 }] }, { team_name: rTeams[4], roster_id: "5", assets: [rAsset("9004", "Tyrone Tracy", "RB", "NYG")] }] }),
  rStory({ story_type: "activity", title: "Most active desk", summary: "Not Your Dad's Dih made 6 moves.", primary_team: rTeams[3], primary_roster_id: "4", metric_label: "Moves", metric_value: "6", history_filter: "All" }),
] } };
// News fixtures (GET /v1/news general feed + the roster-matched alerts digest on top), so /news renders its real rows, avatar strip and chips.
const nowTs = Date.now() / 1000;
const nItem = (title, ev, ago, extra = {}) => ({ title, link: `https://example.com/${encodeURIComponent(title).slice(0, 20)}`, source: "Beat writer", summary: null, published_ts: nowTs - ago, event_type: ev, speculative: false, ...extra });
const nAlert = (n, id, name, pos, team, title, ev, ago, rel, read = false) => ({ ...nItem(title, ev, ago), alert_key: `k${n}`, read, matched_player: name, matched_player_id: id, matched_player_position: pos, matched_player_team: team, matched_player_relation: rel });
const NEWS_ALERTS = [
  nAlert(1, "9221", "Jahmyr Gibbs", "RB", "DET", "Full practice, expects 22 touches in the Sunday matchup against a very physical front seven", "role/depth chart", 3600, "starter"),
  nAlert(2, "6804", "Trey Lawrence", "TE", "NYG", "Questionable with ankle, test Friday", "injury/status", 10800, "starter"),
  nAlert(3, "6794", "Malik Nabers", "WR", "NYG", "Limited again, role unchanged", "injury/status", 21600, "starter"),
  nAlert(4, "4881", "Christian Sutton-Washington", "QB", "HOU", "Throws for 3 TDs in the scrimmage", "role/depth chart", 86400, "starter"),
  nAlert(5, "1111", "Devon Henry", "RB", "MIA", "Signed to the practice squad", "transaction", 90000, "bench"),
  nAlert(6, "2222", "Amon-Ra St. Brown", "WR", "DET", "Back at practice", "injury/status", 95000, "starter"),
  nAlert(7, "3333", "Jordan Mason", "RB", "SF", "Expected to lead the backfield", "role/depth chart", 99000, "starter"),
];
const NEWS_GENERAL = [
  nItem("Example Eagles claim K. Allen off waivers", "transaction", 18000),
  nItem("Sample Sharks cut D. Henry", "transaction", 25000, { matched_player: "Devon Henry", matched_player_id: "1111", matched_player_position: "RB", matched_player_team: "MIA" }),
  nItem("Test Titans trade for P. Nacua in a blockbuster deal that reshapes the Supercalifragilisticexpialidocious division", "transaction", 32000),
];

// Batch E fixtures (docs/audits/2026-11-ui-audit-e2e.md B5): Account, Commissioner, Community, Trade Analyzer and Prospects render real layouts.
// The "-missing" routes below answer the same endpoints with {} (a partial / drifted payload) and must still render (no route error screen).
const cTeam = (n, band) => ({ roster_id: n, team_name: `Team ${n}`, owner_name: `Owner ${n}`, band, band_label: band === "fine" ? "Looks fine" : "Worth a look", score: band === "fine" ? 10 : 62, confidence: "medium", interpretation: band === "fine" ? "none" : "possible_tanking", context: "alive", weeks: { evaluated: 9, flagged: band === "fine" ? 0 : 4, longest_streak: 2, latest_streak: 1 }, evidence: band === "fine" ? [] : [{ kind: "lineup", week: 8, text: "Left 14 projected points on the bench." }], innocent_explanations: band === "fine" ? [] : ["A late injury change can look like this."], series: [1, 2, 3, 4].map((w) => ({ week: w, actual: 100 + w, optimal: 110 + w })) });
FIX["commissioner/integrity"] = { ok: true, reason: "", is_premium: true, draft_order_rule: "unknown", weeks_evaluated: 9, last_week: 9, week: 10, teams: [cTeam(1, "worth_a_look"), cTeam(2, "fine"), cTeam(3, "fine")], collusion: [], inactive: [{ roster_id: 4, team_name: "Team 4", owner_name: "Owner 4", evidence: ["No lineup change in 3 weeks."], innocent_explanations: ["May be on vacation."] }], summary: { fine: 2, worth_a_look: 1 }, limits: ["Prompts to check, not conclusions."], calendar: { trade_deadline_week: 11, current_week: 9, trade_deadline_passed: false, weeks_to_deadline: 2, deadline_phase: "open", playoff_week_start: 15, regular_season_weeks: 14, in_season: true } };
FIX["draft-order"] = { ok: true, draft_order: "unknown" };
FIX.rosters = { ok: true, rosters: [1, 2, 3, 4].map((i) => ({ roster_id: i, owner_id: `u${i}`, players: [`p${i}a`, `p${i}b`] })) };
const sAgg = (g, n) => ({ avg_grade: g, scout_count: n, avg_round_projection: g ? 1.5 : null });
const PROSPECTS = { ok: true, catalog_available: true, reason: "", is_premium: true, prospects: [["Test College Quarterback", "QB", "Ohio State", 82, 14], ["Test College Receiver", "WR", "Texas A&M Commerce", 74, 6], ["Test College Back", "RB", "Georgia", null, 0]].map(([name, position, school, g, n], i) => ({ id: `pr${i}`, name, position, school, draft_year: 2027, aggregate: sAgg(g, n), my_report: null, on_watchlist: i === 0 })) };
const cAsset = (name, position) => ({ name, position, player_id: name.replace(/\s/g, ""), value_score: 1200 });
const COMMUNITY = { ok: true, reaction_emoji: ["\u{1F525}", "\u{1F440}"], trades: [1, 2].map((n) => ({ id: `ct${n}`, send: [cAsset("Test Running Back", "RB")], receive: [cAsset("Opponent Wide Receiver", "WR"), cAsset("Test Tight End", "TE")], verdict: n === 1 ? "worked_out" : "didnt_pan_out", verdict_label: n === 1 ? "Worked out" : "Didn't pan out", confidence: "high", production: { net_points_ppr: 42.5, avg_net_per_week: 4.7, weeks_counted: 9 }, value: { sent_delta_pct: -4, received_delta_pct: 12, net_delta_pct: 8 }, occurred_at: "2026-10-01T12:00:00Z", reactions: { "\u{1F525}": 3 }, my_reactions: [] })) };
const SHARED = { ok: true, available: true, trades: [] };
const ME = { ok: true, user: { id: "u1", email: "t@example.com", entitlement: "premium", sleeper_username: "donk", profile_status: "ready", league_cap: 5, trial_ends_at: "" }, premium_benefits: ["Unlimited leagues"], premium_comparison: [{ key: "leagues", label: "Leagues", free: "1", pro: "Unlimited" }] };
// path -> fixture for the non-league endpoints; league endpoints nested under /v1/leagues/<id>/ are keyed by their tail.
const GLOBAL_FIX = { "/v1/scouting/prospects": PROSPECTS, "/v1/community/trades": COMMUNITY, "/v1/community/shared-trades": SHARED, "/v1/community/preferences": { ok: true, opted_out: false }, "/v1/me": ME };
// "-missing" routes: the same endpoints answer {} (fixtures off).
let MISSING = false;

const ROUTES = [
  { name: "today", path: `/dashboard/${LID}?name=Donk`, family: "none" },
  { name: "team", path: `/my-team/${LID}?name=Donk`, family: "team" },
  { name: "trades", path: `/trade-hub/${LID}?name=Donk`, family: "trades" },
  { name: "league", path: `/league-rankings/${LID}?name=Donk`, family: "league" },
  { name: "matchup", path: `/matchup/${LID}?name=Donk`, family: "team", expect: "matchup-hero" },
  { name: "waivers", path: `/waivers/${LID}?name=Donk`, family: "team", expect: "waiver-rec-row", maxTablists: 2, noModules: true },
  { name: "players", path: `/players/${LID}?name=Donk`, family: "team", noModules: true },
  { name: "trade-finder", path: `/trade-finder/${LID}?name=Donk`, family: "trades", maxTablists: 2, noModules: true },
  { name: "trade-analyzer", path: `/trade-analyzer/${LID}?name=Donk`, family: "trades", maxTablists: 2, noModules: true, expectText: "The tickle monster" },
  { name: "gm-plan", path: `/gm-plan/${LID}?name=Donk`, family: "none", maxTablists: 2 },
  { name: "games", path: `/games/${LID}?name=Donk`, family: "league" },
  { name: "recaps", path: `/league-recaps/${LID}?name=Donk`, family: "league", maxTablists: 3, expandAll: true, noTruncate: true },
  { name: "draft-center", path: `/draft-center/${LID}?name=Donk`, family: "none" },
  { name: "sample-league", path: `/sample-league`, family: "none", maxTablists: 2, noAuth: true },
  // Overflow-only routes (OVERFLOW=1, scripts/sim_layout_playwright/route_overflow in CI): every other main route, checked for sideways scroll only.
  // Fantasy Sim (batch H): Sim Home, the game shell with the simmock API after "Open game". Team / League / Players sit behind the bottom pill and are not reachable by the scan yet.
  { name: "sim-home", path: `/gm-game`, overflowOnly: true, sim: "" },
  { name: "news-nfl", path: `/news?league=${LID}&name=Donk`, overflowOnly: true },
  { name: "news-league", path: `/news?tab=league&league=${LID}&name=Donk`, overflowOnly: true },
  { name: "news-league-history", path: `/news?tab=league&recaps=history&league=${LID}&name=Donk`, overflowOnly: true },
  { name: "news-league-storylines", path: `/news?tab=league&recaps=storylines&league=${LID}&name=Donk`, overflowOnly: true },
  { name: "news-league-roundup", path: `/news?tab=league&recaps=roundup&league=${LID}&name=Donk`, overflowOnly: true },
  { name: "games-pickem", path: `/games/${LID}?name=Donk&tab=pickem`, overflowOnly: true },
  { name: "players-prospects", path: `/players/${LID}?name=Donk&tab=prospects`, overflowOnly: true, expectText: "Test College Quarterback" },
  { name: "waivers-explore", path: `/waivers/${LID}?name=Donk&tab=explore`, overflowOnly: true },
  { name: "waivers-watchlist", path: `/waivers/${LID}?name=Donk&tab=watchlist`, overflowOnly: true },
  { name: "trade-analyzer-missing", path: `/trade-analyzer/${LID}?name=Donk`, overflowOnly: true, missing: true },
  { name: "prospects-missing", path: `/players/${LID}?name=Donk&tab=prospects`, overflowOnly: true, missing: true },
  { name: "commissioner-missing", path: `/commissioner/${LID}?name=Donk`, overflowOnly: true, missing: true },
  { name: "community-missing", path: `/community?league=${LID}&name=Donk`, overflowOnly: true, missing: true },
  { name: "account-missing", path: `/account`, overflowOnly: true, missing: true },
  { name: "commissioner", path: `/commissioner/${LID}?name=Donk`, overflowOnly: true, expectText: "Team 1" },
  { name: "community", path: `/community?league=${LID}&name=Donk`, overflowOnly: true, expectText: "Opponent Wide Receiver" },
  { name: "fantasy-sim", path: `/fantasy-sim/${LID}?name=Donk`, overflowOnly: true },
  { name: "account", path: `/account`, overflowOnly: true, expectText: "t@example.com" },
  { name: "landing", path: `/`, overflowOnly: true, noAuth: true },
];
const session = { access_token: "a.b.c", refresh_token: "r", token_type: "bearer", expires_in: 99999, expires_at: Math.floor(Date.now() / 1000) + 99999, user: { id: "u1", aud: "authenticated", role: "authenticated", email: "t@example.com", app_metadata: {}, user_metadata: {}, created_at: "2026-01-01T00:00:00Z" } };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Elements whose box ends past the viewport (outside a deliberate horizontal scroller): the culprits when the document scrolls sideways. Innermost first.
const OFFENDERS = () => {
  const W = document.documentElement.clientWidth;
  const sel = (el) => { const id = el.getAttribute("data-testid"); const cls = typeof el.className === "string" ? el.className.trim().split(/\s+/).slice(0, 3).join(".") : ""; return `${el.tagName.toLowerCase()}${id ? `[data-testid=${id}]` : ""}${cls ? "." + cls : ""}`; };
  const inScroller = (el) => { for (let n = el.parentElement; n && n !== document.body; n = n.parentElement) { const o = getComputedStyle(n).overflowX; if (o === "auto" || o === "scroll" || o === "hidden" || o === "clip") return true; } return false; };
  const bad = [];
  for (const el of document.querySelectorAll("body *")) {
    if (el.closest("nextjs-portal,[data-nextjs-toast]") || ["SCRIPT", "STYLE"].includes(el.tagName)) continue;
    const r = el.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0 || (r.right <= W + 1 && r.left >= -1) || inScroller(el)) continue;
    bad.push(el);
  }
  // Innermost offenders (no offending descendant) are the elements that actually hold the too-wide content; each is listed with its ancestor chain's widths so a wide wrapper is visible too.
  const set = new Set(bad);
  const leaves = bad.filter((el) => ![...el.querySelectorAll("*")].some((d) => set.has(d)));
  return leaves.slice(0, 8).map((el) => {
    const r = el.getBoundingClientRect();
    const chain = []; for (let n = el.parentElement; n && n !== document.documentElement && chain.length < 12; n = n.parentElement) chain.push(`${sel(n)} w=${Math.round(n.getBoundingClientRect().width)}`);
    return `${sel(el)} right=${Math.round(r.right)} w=${Math.round(r.width)} "${(el.textContent || "").replace(/\s+/g, " ").trim().slice(0, 30)}" <- ${chain.join(" < ")}`;
  });
};

// First-module offset (docs/audits/2026-11-ui-audit-e2e.md P0-2, batch B): how far below the sticky nav (shell header + page tab strip) the first
// piece of page content starts. Walks into layout wrappers (no background/border/shadow) until it reaches a card, a control row or a heading.
const FIRST_MODULE = () => {
  const vis = (el) => { const r = el.getBoundingClientRect(); const cs = getComputedStyle(el); return r.width > 4 && r.height > 4 && cs.display !== "none" && cs.visibility !== "hidden" && cs.position !== "absolute" && !el.classList.contains("sr-only"); };
  const sticky = [...document.querySelectorAll(".shell-header, .pill-row-glass, body > header, [data-testid=sim-game-header]")].filter((el) => { const r = el.getBoundingClientRect(); return r.height > 0 && r.top < 140; });
  const navBottom = Math.max(0, ...sticky.map((el) => el.getBoundingClientRect().bottom));
  const isChrome = (el) => el.matches(".pill-row-glass, [data-testid=page-tab-bar]") || Boolean(el.querySelector(":scope > .pill-row-glass"));
  const isCard = (el) => { const cs = getComputedStyle(el); const bg = cs.backgroundColor; return (bg && bg !== "rgba(0, 0, 0, 0)" && bg !== "transparent") || cs.boxShadow !== "none" || parseFloat(cs.borderTopWidth) > 0 || cs.backdropFilter !== "none" && cs.backdropFilter !== undefined || el.matches("button,input,select,h1,h2,h3,p,[role=tablist]"); };
  let node = document.querySelector("main");
  if (!node) return null;
  for (let depth = 0; depth < 8; depth += 1) {
    const kids = [...node.children].filter((el) => vis(el) && !isChrome(el) && !el.matches("nextjs-portal,script,style"));
    if (!kids.length) break;
    const k = kids[0];
    if (isCard(k) || !k.children.length) { node = k; break; }
    node = k;
  }
  // First card/row: the first visible surface (shadow, backdrop blur or a list row) at least 48px tall that is not a control or the tab strip; what the owner means by "the first module".
  const cardEl = [...document.querySelectorAll("main *")].find((el) => {
    if (!vis(el) || isChrome(el) || el.closest(".pill-row-glass, [data-testid=sim-game-header]") || el.matches("button,input,select,a,[role=tab],[role=tablist]")) return false;
    const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
    return r.height >= 48 && r.width >= 200 && (cs.boxShadow !== "none" || (cs.backdropFilter && cs.backdropFilter !== "none") || el.matches("[data-testid$=-row],[data-testid=player-accordion-row]"));
  });
  const cardGap = cardEl ? Math.round(cardEl.getBoundingClientRect().top + scrollY - navBottom) : null;
  const r = node.getBoundingClientRect();
  const id = node.getAttribute("data-testid");
  const cid = cardEl && cardEl.getAttribute("data-testid");
  return { cardGap, card: cardEl ? `${cardEl.tagName.toLowerCase()}${cid ? `[${cid}]` : ""}` : null, top: Math.round(r.top + scrollY), navBottom: Math.round(navBottom), gap: Math.round(r.top + scrollY - navBottom), el: `${node.tagName.toLowerCase()}${id ? `[${id}]` : ""}`, text: (node.textContent || "").replace(/\s+/g, " ").trim().slice(0, 40) };
};

const PAGE_CHECK = () => {
  const W = document.documentElement.clientWidth;
  const out = { overflow: document.documentElement.scrollWidth > W + 1 ? { scrollWidth: document.documentElement.scrollWidth, width: W } : null, emptyHeaders: [], modules: 0, tablists: 0, height: document.documentElement.scrollHeight, heroes: document.querySelectorAll('[data-testid="hero-value"]').length, summaries: [] };
  for (const b of document.querySelectorAll('button[aria-expanded="false"][aria-label$=". Expand"], button[aria-expanded="true"][aria-label$=". Collapse"]')) {
    out.modules += 1;
    const label = b.getAttribute("aria-label") || "";
    const body = label.replace(/\. (Expand|Collapse)$/, "");
    const at = body.indexOf(": ");
    const title = at === -1 ? body : body.slice(0, at);
    const summary = at === -1 ? "" : body.slice(at + 2);
    out.summaries.push(`${title}: ${summary.slice(0, 60)}`);
    if (summary.trim().length < 12) out.emptyHeaders.push({ title, chars: summary.trim().length });
  }
  // Page tab strip geometry (PillRow glass): must be full-bleed (0..W), tabs evenly spread and centred, strip backing opaque.
  const strip = document.querySelector(".pill-row-glass");
  if (strip) {
    const r = strip.getBoundingClientRect();
    const tabs = [...strip.querySelectorAll('[role="tab"]')].map((t) => t.getBoundingClientRect());
    const hdr = document.querySelector(".shell-header");
    const m = getComputedStyle(strip).backgroundColor.match(/rgba?\(([^)]+)\)/);
    const parts = m ? m[1].split(/[,/ ]+/).filter(Boolean).map(parseFloat) : [];
    const alphas = [parts.length > 3 ? parts[3] : m ? 1 : 0];
    out.strip = {
      left: Math.round(r.left * 10) / 10, right: Math.round((W - r.right) * 10) / 10, top: Math.round(r.top), headerBottom: hdr ? Math.round(hdr.getBoundingClientRect().bottom) : null,
      tabLeft: Math.round(tabs[0].left * 10) / 10, tabRight: Math.round((W - tabs[tabs.length - 1].right) * 10) / 10,
      widths: tabs.map((t) => Math.round(t.width)), minAlpha: alphas.length ? Math.min(...alphas) : 1,
    };
  }
  const vis = (el) => { const r = el.getBoundingClientRect(); return r.height > 0 && r.width > 0 && getComputedStyle(el).display !== "none"; };
  out.headerBars = [...document.querySelectorAll("body header")].filter((h) => vis(h) && h.getBoundingClientRect().top < 120 && !h.closest("main") && !h.closest("section")).length;
  out.shellHeaderVisible = [...document.querySelectorAll('[data-testid="shell-header"]')].some(vis);
  // Names are never ellipsized: any clipped text inside the recap's identity blocks (the row meta line of a shared player row is the template's own one-line truncation).
  out.truncated = [];
  for (const el of document.querySelectorAll('[data-testid="recap-story"] *, [data-testid="recap-leader"] *, [data-testid="recap-trade-card"] *, [data-testid="status-headline"], [data-testid="status-context"]')) {
    if (el.children.length || !el.textContent.trim() || el.closest('[data-testid="row-meta"]')) continue;
    const cs = getComputedStyle(el);
    if (cs.textOverflow === "ellipsis" && el.scrollWidth > el.clientWidth + 1) out.truncated.push(el.textContent.trim().slice(0, 40));
    if (el.scrollWidth > el.clientWidth + 1 && cs.overflowX !== "visible") out.truncated.push("clipped:" + el.textContent.trim().slice(0, 40));
  }
  // "?" standard (docs/ui-patterns.md, One InfoMark): every explainer glyph must share its row with other content (never alone on its own row) and never overlap text.
  // Current marker: [data-info-mark]. Legacy selectors stay so a before/after run on an older checkout measures the retired variants too.
  out.marks = [];
  const GLYPHS = '[data-info-mark] span, .ui-why-corner-btn span, [data-info-tip] > button > span, [data-beginner-help] > button > span, [data-glossary-note] > button > span, #page-info-slot button span, #shell-page-info-slot button span';
  const ROOT = '[data-info-mark], .ui-why-corner-btn, [data-info-tip], [data-beginner-help], [data-glossary-note]';
  const rects = (n) => { const r = document.createRange(); r.selectNodeContents(n); return [...r.getClientRects()]; };
  const texts = [];
  for (const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT); w.nextNode();) {
    const n = w.currentNode;
    const pe = n.parentElement;
    if (!n.textContent.trim() || !pe || pe.closest("script,style,noscript,[aria-hidden=true],.sr-only,nextjs-portal")) continue;
    const cs = getComputedStyle(pe);
    if (cs.visibility !== "hidden" && cs.display !== "none") texts.push(n);
  }
  for (const g of document.querySelectorAll(GLYPHS)) {
    const gr = g.getBoundingClientRect();
    if (gr.width < 2 || gr.height < 2) continue;
    const root = g.closest(ROOT) || g.parentElement;
    let overlap = null, shares = false;
    for (const n of texts) {
      if (root.contains(n) || n.parentElement.closest("button") === g.closest("button")) continue;
      for (const r of rects(n)) {
        if (r.width < 1 || r.height < 1) continue;
        const ix = Math.min(gr.right, r.right) - Math.max(gr.left, r.left), iy = Math.min(gr.bottom, r.bottom) - Math.max(gr.top, r.top);
        if (ix > 1.5 && iy > 1.5) overlap = overlap || n.textContent.trim().slice(0, 30);
        if (iy > Math.min(gr.height, r.height) * 0.5) shares = true;
      }
    }
    out.marks.push({ kind: g.closest(ROOT)?.matches("[data-info-mark]") ? "InfoMark" : "legacy", glyph: Math.round(gr.width) + "x" + Math.round(gr.height), y: Math.round(gr.top + scrollY), ownRow: !shares, overlap });
  }
  out.crashed = /Something went wrong\. It.s been logged\./.test(document.body.innerText);
  out.bodyText = document.body.innerText;
  const main = document.querySelector("main");
  out.mainWidth = main ? Math.round(main.getBoundingClientRect().width) : 0;
  out.recRows = document.querySelectorAll('[data-testid="waiver-rec-row"]').length;
  out.recRowMaxH = Math.max(0, ...[...document.querySelectorAll('[data-testid="waiver-rec-row"]')].map((e) => Math.round(e.getBoundingClientRect().height)));
  const tl = [...document.querySelectorAll('[role="tablist"]')].filter((el) => el.getBoundingClientRect().height > 0);
  // The page tab row count: filter rows (aria-labelled pill rows) and view toggles inside a module are not page tabs.
  out.tablists = tl.filter((el) => !el.getAttribute("aria-label")?.match(/^(Position|Recommendation filter|What you want back|Season|Filter history|Recap week|Sample league views)$/) && !el.closest('[data-testid^="matchup-"],[data-testid^="players-"]')).length;
  out.tablistLabels = tl.map((el) => `${el.getAttribute("aria-label") || ""}|${[...el.querySelectorAll('[role="tab"]')].map((t) => t.textContent.trim()).join("/")}|inModule=${Boolean(el.closest('[data-testid^="matchup-"],[data-testid^="players-"]'))}`);
  return out;
};


// Token census: what the rendered page actually uses (visible elements only), so spacing/radius/type drift shows up as numbers.
const CENSUS = () => {
  const hist = (m, k) => { m[k] = (m[k] || 0) + 1; };
  const radii = {}, sizes = {}, weights = {}, btnH = {}, gold = [], pills = {};
  const isGold = (c) => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return false; const [r, g, b, a] = m[1].split(/[,/ ]+/).filter(Boolean).map(parseFloat); if (a === 0) return false; return r > 200 && g > 150 && b < 110 && r >= g; };
  for (const el of document.querySelectorAll("main *, header *")) {
    const r = el.getBoundingClientRect(); if (r.width < 2 || r.height < 2) continue;
    const cs = getComputedStyle(el); if (cs.display === "none" || cs.visibility === "hidden") continue;
    const rad = parseFloat(cs.borderTopLeftRadius) || 0; if (rad > 0 && r.height > 20) hist(radii, rad >= r.height / 2 - 1 ? "pill" : Math.round(rad) + "px");
    if (el.childNodes.length && [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim())) { hist(sizes, parseFloat(cs.fontSize).toFixed(1).replace(/\.0$/, "")); hist(weights, cs.fontWeight);
      if (isGold(cs.color)) gold.push((el.textContent || "").trim().slice(0, 28)); }
    if (el.tagName === "BUTTON" || el.getAttribute("role") === "button") hist(btnH, Math.round(r.height));
    if (isGold(cs.backgroundColor) || isGold(cs.borderTopColor) && parseFloat(cs.borderTopWidth) >= 2) gold.push("[bg/border] " + (el.getAttribute("data-testid") || el.className?.toString().slice(0, 30) || el.tagName));
  }
  const vis = (el) => { const r = el.getBoundingClientRect(); return r.width > 2 && r.height > 2 && getComputedStyle(el).display !== "none"; };
  const headings = [...document.querySelectorAll("main h2, main h3, main h4, main [data-testid*='heading'], main [class*='section-heading'], main [class*='eyebrow']")].filter(vis).slice(0, 40).map((h) => { const cs = getComputedStyle(h); return `${h.tagName.toLowerCase()} ${parseFloat(cs.fontSize)}px/${cs.fontWeight}${cs.textTransform === "uppercase" ? " UP" : ""} "${(h.textContent || "").trim().slice(0, 30)}"`; });
  const controls = [...document.querySelectorAll("main select, main input[type=search], main input[type=text], main [role=tablist], header select")].filter(vis).map((el) => { const cs = getComputedStyle(el), r = el.getBoundingClientRect(); const rad = parseFloat(cs.borderTopLeftRadius) || 0; return `${el.tagName.toLowerCase()}${el.getAttribute("role") ? "[" + el.getAttribute("role") + "]" : ""} r=${rad >= r.height / 2 - 1 ? "pill" : Math.round(rad)} h=${Math.round(r.height)} ${(el.getAttribute("aria-label") || el.getAttribute("placeholder") || "").slice(0, 24)}`; });
  const small = [...document.querySelectorAll("main button, main a[href], main [role=tab], main select, header button, header a")].filter(vis).map((e) => { const r = e.getBoundingClientRect(); return { t: (e.getAttribute("aria-label") || e.textContent || e.tagName).trim().replace(/\s+/g, " ").slice(0, 28), w: Math.round(r.width), h: Math.round(r.height), inline: getComputedStyle(e).display === "inline" }; }).filter((x) => x.h < 43 && !x.inline).slice(0, 25);
  return { radii, sizes, weights, btnH, headings, controls, small, gold: gold.slice(0, 40), goldCount: gold.length };
};

let SIM_ON = false;
const SIM_MOCK = createMock({ status: "in_season", week: 4 });
const browser = await engine.launch(process.env.CHROME ? { executablePath: process.env.CHROME } : {});
const results = [];
for (const w of WIDTHS) {
  const ctx = await browser.newContext({ viewport: { width: w, height: w >= 768 ? 900 : 844 }, hasTouch: w < 768, isMobile: w < 768 });
  await ctx.addInitScript(([s, nav, theme]) => { try { localStorage.clear(); localStorage.setItem("fgl:theme-mode", theme); localStorage.setItem("sb-dummy-auth-token", JSON.stringify(s)); localStorage.setItem("fgl:onboarding-complete", "1"); if (nav) localStorage.setItem("fgl:nav", nav); } catch (e) {} }, [session, NAV, process.env.THEME || "dark"]);
  await ctx.route("**/*", async (route) => {
    const u = new URL(route.request().url());
    const cors = { "access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "*" };
    if (u.hostname === "localhost" && u.port === "8000") {
      if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
      if (SIM_ON) {
        let json = null; try { json = route.request().postData() ? JSON.parse(route.request().postData()) : null; } catch {}
        const res = SIM_MOCK(route.request().method(), u.pathname, Object.fromEntries(u.searchParams.entries()), json);
        if (res) return route.fulfill({ status: res.status, contentType: "application/json", body: JSON.stringify(res.body), headers: cors });
      }
      if (u.pathname === "/v1/news") return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true, items: NEWS_GENERAL }), headers: cors });
      if (/\/alerts$/.test(u.pathname)) return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true, reason: "", items: NEWS_ALERTS }), headers: cors });
      const m = u.pathname.match(/\/v1\/leagues\/[^/]+\/(games\/season-sim|commissioner\/integrity)$/) || u.pathname.match(/\/v1\/leagues\/[^/]+\/([a-z-]+)$/) || u.pathname.match(/\/v1\/players\/(value-signals)$/) || (u.pathname.endsWith("/trade-ideas/multi") ? [0, "multi"] : null);
      const body = MISSING ? {} : (m && FIX[m[1]] ? FIX[m[1]] : GLOBAL_FIX[u.pathname] || {});
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body), headers: cors });
    }
    if (u.hostname === "dummy.supabase.co") return route.fulfill({ status: 200, contentType: "application/json", body: u.pathname.startsWith("/rest/v1/") ? "[]" : "{}", headers: cors });
    return route.continue();
  });
  const page = await ctx.newPage();
  page.on("pageerror", () => {});
  for (const r of ROUTES) {
    if (process.env.ONLY && !process.env.ONLY.split(",").includes(r.name)) continue;
    if (OVERFLOW_MODE ? false : r.overflowOnly) continue;
    MISSING = Boolean(r.missing);
    SIM_ON = r.sim !== undefined;
    try {
      await page.goto(`${BASE}${r.path}`, { waitUntil: "domcontentloaded", timeout: 90000 });
      await page.addStyleTag({ content: "nextjs-portal,[data-nextjs-toast]{display:none!important}" }).catch(() => {});
      await sleep(r.name === "today" && w === WIDTHS[0] ? 12000 : 5000);
      if (r.sim !== undefined) {
        await page.getByRole("button", { name: "Open game", exact: false }).first().click({ timeout: 8000 }).catch(() => {});
        await sleep(1500);
        if (r.sim) { await page.getByRole("tab", { name: r.sim, exact: false }).first().click({ timeout: 8000 }).catch(() => {}); await sleep(1200); }
      }
      // The app shell / Sim root carry an overflow-x: clip backstop; measure without it so a real overflow is still caught (and named).
      if (OVERFLOW_MODE) await page.addStyleTag({ content: ".app-shell,.sim-root{overflow-x:visible!important}" }).catch(() => {});
      if (LARGE) await page.addStyleTag({ content: `html{font-size:${process.env.LARGE_PCT || 125}%!important}` }).catch(() => {});
      const res = await page.evaluate(PAGE_CHECK);
      res.firstModule = await page.evaluate(FIRST_MODULE);
      if (res.overflow) res.overflow.offenders = await page.evaluate(OFFENDERS);
      if (r.expandAll) {
        // Open every collapsed module and the first player row, so the scan covers the bodies, then pick another week from the strip.
        for (let pass = 0; pass < 8; pass += 1) {
          const closed = page.locator('main button[aria-expanded="false"][aria-label$=". Expand"]').first();
          if (!(await closed.count())) break;
          await closed.click().catch(() => {});
          await sleep(250);
        }
        await page.locator('[data-testid="recap-waiver-row"] [data-row-toggle="true"]').first().click().catch(() => {});
        await sleep(400);
        const open = await page.evaluate(PAGE_CHECK);
        res.overflow = res.overflow || open.overflow;
        res.truncated = [...(res.truncated || []), ...(open.truncated || [])];
        res.openHeight = open.height;
        await page.screenshot({ path: `${OUT}/${r.name}-open-${w}.png`, fullPage: true });
      }
      if (GUARD_ON) {
        const state = async (tag) => {
          for (const v of await page.evaluate(GUARD, {})) guardViolations.push({ page: `${r.name}${tag}`, width: w, large: LARGE, ...v });
        };
        await state("");
        const row = page.locator('[data-testid="player-accordion-row"] button[aria-expanded]').first();
        if (await row.count()) { await row.dispatchEvent("click"); await sleep(700); await state(":row-open"); }
      }
      if (AXE_ON && AXE_ROUTES.includes(r.name)) {
        await page.addScriptTag({ content: axeSource });
        const out = await page.evaluate(async () => {
          // eslint-disable-next-line no-undef
          const res = await axe.run(document, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] }, resultTypes: ["violations"] });
          return res.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => ({ id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.slice(0, 4).map((n) => `${n.target.join(" ")} :: ${(n.failureSummary || "").split("\n").slice(1, 2).join("").trim().slice(0, 140)}`), count: v.nodes.length }));
        });
        for (const v of out) axeViolations.push({ page: r.name, width: w, ...v });
        res.axe = out.length;
      }
      if (METRICS) res.census = await page.evaluate(CENSUS);
      res.expectTextMissing = r.expectText ? !res.bodyText.includes(r.expectText) : false;
      delete res.bodyText;
      results.push({ page: r.name, width: w, maxTablists: r.maxTablists ?? 1, noModules: Boolean(r.noModules), expect: r.expect ? await page.locator(`[data-testid="${r.expect}"]`).count() : null, ...res });
      if (r.expect === "waiver-rec-row") await page.locator(`[data-testid="${r.expect}"]`).first().scrollIntoViewIfNeeded().catch(() => {});
      if (SHEET && w < 768) {
        await page.evaluate(() => window.scrollTo(0, 0)).catch(() => {});
        await sleep(700);
        const opener = SHEET === "search" ? page.getByRole("button", { name: "Search players and pages" }).first() : page.locator('[data-testid="shell-tab-bar"]').getByRole("button", { name: /^More/ }).first();
        // The footer hides on scroll down and sits at the end of the column; dispatch the click so a hidden/offscreen bar still opens the sheet.
        await opener.dispatchEvent("click", undefined, { timeout: 8000 }).catch((e) => console.log(`sheet opener (${SHEET}) not found: ${String(e).slice(0, 80)}`));
        await sleep(900);
        await page.screenshot({ path: `${OUT}/${r.name}-${SHEET}-${w}.png`, fullPage: false });
      } else await page.screenshot({ path: `${OUT}/${r.name}-${w}.png`, fullPage: FULL });
    } catch (e) {
      results.push({ page: r.name, width: w, error: String(e).slice(0, 160) });
    }
  }
  await ctx.close();
}
await browser.close();
fs.writeFileSync(`${OUT}/report.json`, JSON.stringify(results, null, 1));
let bad = 0;
for (const r of results) {
  const problems = [];
  if (r.error) problems.push(`error ${r.error}`);
  if (r.overflow) problems.push(`overflow ${r.overflow.scrollWidth}>${r.overflow.width}${r.overflow.offenders?.length ? " culprits: " + r.overflow.offenders.join(" || ") : ""}`);
  if (r.crashed) problems.push("route error screen (a missing or partial field blanked the page)");
  if (r.expectTextMissing) problems.push("fixture content not rendered");
  if (r.firstModule && r.width < 768) console.log(`first-module ${r.page}@${r.width}: top=${r.firstModule.top} navBottom=${r.firstModule.navBottom} gap=${r.firstModule.gap} cardGap=${r.firstModule.cardGap} <${r.firstModule.card}> first=<${r.firstModule.el}> "${r.firstModule.text}"`);
  if (r.firstModule && r.width < 768 && !TOP_EXEMPT.has(r.page)) {
    const offset = r.firstModule.cardGap ?? r.firstModule.gap;
    const budget = TOP_BUDGET_OVERRIDES[r.page] ?? TOP_BUDGET;
    if (offset > budget) problems.push(`first module starts ${offset}px below the nav (budget ${budget}px): one compact header + --page-top-gap, no stacked control rows`);
  }
  if (OVERFLOW_MODE) { console.log(`${problems.length ? "FAIL" : "ok  "} ${r.page}@${r.width}${problems.length ? "  " + problems.join("; ") : ""}`); if (problems.length) bad += 1; continue; }
  if (r.emptyHeaders?.length) problems.push(`empty collapsed headers: ${r.emptyHeaders.map((h) => h.title).join(", ")}`);
  // Strip geometry (equal, centred tabs) is a >= 360px rule: at 320px a long label (Standings, Notifications) makes a tab wider than its share and the row scrolls instead of cutting it.
  if (r.strip && !LARGE && r.width >= 360 && r.width < 768 && r.page !== "sample-league") {
    const s = r.strip, spread = Math.max(...s.widths) - Math.min(...s.widths);
    if (Math.abs(s.left) > 0.5 || Math.abs(s.right) > 0.5) problems.push(`tab strip not full-bleed (left ${s.left}, right gap ${s.right})`);
    if (Math.abs(s.tabLeft - s.tabRight) > 2) problems.push(`tabs not centred (left ${s.tabLeft}, right ${s.tabRight})`);
    if (spread > 8) problems.push(`tab widths uneven ${s.widths}`);
    if (s.minAlpha < 0.9) problems.push(`tab strip backing see-through (alpha ${s.minAlpha})`);
    if (s.headerBottom != null && Math.abs(s.top - s.headerBottom) > 1) problems.push(`tab strip top ${s.top} != header bottom ${s.headerBottom}`);
  }
  for (const m of r.marks ?? []) {
    if (m.ownRow) problems.push(`"?" alone on its own row (${m.kind} y=${m.y})`);
    if (m.overlap) problems.push(`"?" overlaps text "${m.overlap}" (${m.kind} y=${m.y})`);
  }
  if ((r.marks ?? []).some((m) => m.kind === "legacy")) problems.push(`${r.marks.filter((m) => m.kind === "legacy").length} retired "?" variant(s) rendered`);
  if (r.truncated?.length) problems.push(`ellipsized/clipped names: ${r.truncated.slice(0, 4).join(" | ")}`);
  if ((r.tablists ?? 0) > (r.maxTablists ?? 1)) problems.push(`${r.tablists} tab rows`);
  if (r.width >= 768 && r.shellHeaderVisible) problems.push("phone ShellHeader visible on desktop (double header)");
  if (r.width >= 768 && r.headerBars > 1) problems.push(`${r.headerBars} header bars on desktop`);
  if (r.expect === 0) problems.push("expected page content missing (fixture not applied?)");
  if (r.width >= 1024 && r.page === "sample-league" && r.mainWidth < 1000) problems.push(`sample league column only ${r.mainWidth}px wide at desktop`);
  if (r.width >= 1024 && r.page === "matchup" && r.mainWidth < 1000) problems.push(`matchup column only ${r.mainWidth}px wide at desktop`);
  if (r.recRowMaxH > 96 && r.width >= 390 && !LARGE) problems.push(`recommended-add row ${r.recRowMaxH}px tall (compact rows are <= 96)`);
  if (r.modules === 0 && !r.noModules) problems.push("no compact modules rendered (fixtures not applied?)");
  if (problems.length && !AXE_ONLY) bad += 1; // AXE_ONLY: layout budgets are the route-overflow step's job (CI fonts differ from local), this run fails on axe alone
  console.log(`${problems.length ? "FAIL" : "ok  "} ${r.page}@${r.width}: modules=${r.modules} heroes=${r.heroes} headers=${r.headerBars} main=${r.mainWidth} recRows=${r.recRows}/${r.recRowMaxH} tablists=${r.tablists} height=${r.height}${problems.length ? "  " + problems.join("; ") : ""}`);
}
if (GUARD_ON) {
  fs.writeFileSync(`${OUT}/desk-violations.json`, JSON.stringify(guardViolations, null, 1));
  const byKey = new Map();
  for (const v of guardViolations) { const k = `${v.kind} ${v.el} "${v.text}"`; const e = byKey.get(k) || { n: 0, where: new Set(), detail: v.detail }; e.n += 1; e.where.add(`${v.page}@${v.width}`); byKey.set(k, e); }
  for (const [k, e] of byKey) console.log(`GUARD ${k}  x${e.n}  e.g. ${[...e.where].slice(0, 3).join(", ")}  ${e.detail}`);
  console.log(`desk layout guard: ${byKey.size} distinct violations (${guardViolations.length} total)`);
  if (guardViolations.length) bad += 1;
}
if (AXE_ON) {
  fs.writeFileSync(`${OUT}/axe-violations.json`, JSON.stringify(axeViolations, null, 1));
  for (const v of axeViolations) console.log(`AXE ${v.page}@${v.width} [${v.impact}] ${v.id} x${v.count}: ${v.help}\n     ${v.nodes.join("\n     ")}`);
  console.log(`axe: ${axeViolations.length} serious/critical rule violation(s)`);
  if (axeViolations.length) bad += 1;
}
console.log(bad ? `${bad} page(s) with problems` : "module scan clean");
process.exit(bad ? 1 : 0);
