// Module-template scan (docs/audits/2026-11-module-templates-rollout.md): Today, Team, Trades, League, Matchup, Waivers and Players at 390 and 1440 WITH data (desktop also checks one header bar).
// Unlike app_audit.mjs (empty stubs) this answers the league endpoints with fixtures, then checks per page:
//   - no horizontal overflow (scrollWidth <= width),
//   - every collapsed compact module shows >= 12 characters of summary (the same rule as the unit tests),
//   - at most one tablist/tab row of the page family (the family strip) and no empty section headers,
//   - total scroll height and module count (reported, so a page that grows shows up in the diff).
// Start the dev server first:
//   NEXT_PUBLIC_SUPABASE_URL=https://dummy.supabase.co NEXT_PUBLIC_SUPABASE_ANON_KEY=x NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npx next dev -p 3197
//   PW_CORE=.../playwright-core/index.mjs BASE=http://localhost:3197 OUT=/tmp/module-scan [WIDTHS=360,390] node scripts/sim_layout_playwright/module_scan.mjs
import fs from "fs";

const { chromium } = await import(process.env.PW_CORE || "playwright-core");
const BASE = process.env.BASE || "http://localhost:3197";
const OUT = process.env.OUT || "/private/tmp/claude-501/module-scan";
const WIDTHS = (process.env.WIDTHS || "390,1440").split(",").map(Number);
const LID = "1221647449446162432";
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
    ideas: [1, 2, 3].map((n) => ({ partner_team_name: `Team ${n + 1}`, partner_team_avatar_url: null, rationale: "Fills your WR need with a surplus RB.", trade_gain: 400 * n, confidence_label: "High", market_realism_label: "Realistic", reasoning_tags: [], package: { send: [], receive: [] }, category: "need", value_edge_band: "Fair", impact_tag: "Lineup", landed_gm_target_player_ids: [], send_score: 1000, receive_score: 1400, recommendation_id: `idea-${n}` })),
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
const ROUTES = [
  { name: "today", path: `/dashboard/${LID}?name=Donk`, family: "none" },
  { name: "team", path: `/my-team/${LID}?name=Donk`, family: "team" },
  { name: "trades", path: `/trade-hub/${LID}?name=Donk`, family: "trades" },
  { name: "league", path: `/league-rankings/${LID}?name=Donk`, family: "league" },
  { name: "matchup", path: `/matchup/${LID}?name=Donk`, family: "team", expect: "matchup-hero" },
  { name: "waivers", path: `/waivers/${LID}?name=Donk`, family: "team", expect: "waiver-rec-row", maxTablists: 2, noModules: true },
  { name: "players", path: `/players/${LID}?name=Donk`, family: "team", noModules: true },
];
const session = { access_token: "a.b.c", refresh_token: "r", token_type: "bearer", expires_in: 99999, expires_at: Math.floor(Date.now() / 1000) + 99999, user: { id: "u1", aud: "authenticated", role: "authenticated", email: "t@example.com", app_metadata: {}, user_metadata: {}, created_at: "2026-01-01T00:00:00Z" } };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

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
  const vis = (el) => { const r = el.getBoundingClientRect(); return r.height > 0 && r.width > 0 && getComputedStyle(el).display !== "none"; };
  out.headerBars = [...document.querySelectorAll("body header")].filter((h) => vis(h) && h.getBoundingClientRect().top < 120 && !h.closest("main") && !h.closest("section")).length;
  out.shellHeaderVisible = [...document.querySelectorAll('[data-testid="shell-header"]')].some(vis);
  const main = document.querySelector("main");
  out.mainWidth = main ? Math.round(main.getBoundingClientRect().width) : 0;
  out.recRows = document.querySelectorAll('[data-testid="waiver-rec-row"]').length;
  out.recRowMaxH = Math.max(0, ...[...document.querySelectorAll('[data-testid="waiver-rec-row"]')].map((e) => Math.round(e.getBoundingClientRect().height)));
  const tl = [...document.querySelectorAll('[role="tablist"]')].filter((el) => el.getBoundingClientRect().height > 0);
  // The page tab row count: filter rows (aria-labelled pill rows) and view toggles inside a module are not page tabs.
  out.tablists = tl.filter((el) => !el.getAttribute("aria-label")?.match(/^(Position|Recommendation filter)$/) && !el.closest('[data-testid^="matchup-"],[data-testid^="players-"]')).length;
  out.tablistLabels = tl.map((el) => `${el.getAttribute("aria-label") || ""}|${[...el.querySelectorAll('[role="tab"]')].map((t) => t.textContent.trim()).join("/")}|inModule=${Boolean(el.closest('[data-testid^="matchup-"],[data-testid^="players-"]'))}`);
  return out;
};

const browser = await chromium.launch({ executablePath: process.env.CHROME || process.env.HOME + "/Library/Caches/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-mac-arm64/chrome-headless-shell" });
const results = [];
for (const w of WIDTHS) {
  const ctx = await browser.newContext({ viewport: { width: w, height: w >= 768 ? 900 : 844 }, hasTouch: w < 768, isMobile: w < 768 });
  await ctx.addInitScript(([s]) => { try { localStorage.clear(); localStorage.setItem("fgl:theme-mode", "dark"); localStorage.setItem("sb-dummy-auth-token", JSON.stringify(s)); localStorage.setItem("fgl:onboarding-complete", "1"); } catch (e) {} }, [session]);
  await ctx.route("**/*", async (route) => {
    const u = new URL(route.request().url());
    const cors = { "access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "*" };
    if (u.hostname === "localhost" && u.port === "8000") {
      if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
      const m = u.pathname.match(/\/v1\/leagues\/[^/]+\/([a-z-]+)$/) || u.pathname.match(/\/v1\/players\/(value-signals)$/) || (u.pathname.endsWith("/trade-ideas/multi") ? [0, "multi"] : null);
      const body = m && FIX[m[1]] ? FIX[m[1]] : {};
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body), headers: cors });
    }
    if (u.hostname === "dummy.supabase.co") return route.fulfill({ status: 200, contentType: "application/json", body: u.pathname.startsWith("/rest/v1/") ? "[]" : "{}", headers: cors });
    return route.continue();
  });
  const page = await ctx.newPage();
  page.on("pageerror", () => {});
  for (const r of ROUTES) {
    try {
      await page.goto(`${BASE}${r.path}`, { waitUntil: "domcontentloaded", timeout: 90000 });
      await page.addStyleTag({ content: "nextjs-portal,[data-nextjs-toast]{display:none!important}" }).catch(() => {});
      await sleep(r.name === "today" && w === WIDTHS[0] ? 12000 : 5000);
      const res = await page.evaluate(PAGE_CHECK);
      results.push({ page: r.name, width: w, maxTablists: r.maxTablists ?? 1, noModules: Boolean(r.noModules), expect: r.expect ? await page.locator(`[data-testid="${r.expect}"]`).count() : null, ...res });
      if (r.expect === "waiver-rec-row") await page.locator(`[data-testid="${r.expect}"]`).first().scrollIntoViewIfNeeded().catch(() => {});
      await page.screenshot({ path: `${OUT}/${r.name}-${w}.png`, fullPage: false });
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
  if (r.overflow) problems.push(`overflow ${r.overflow.scrollWidth}>${r.overflow.width}`);
  if (r.emptyHeaders?.length) problems.push(`empty collapsed headers: ${r.emptyHeaders.map((h) => h.title).join(", ")}`);
  if ((r.tablists ?? 0) > (r.maxTablists ?? 1)) problems.push(`${r.tablists} tab rows`);
  if (r.width >= 768 && r.shellHeaderVisible) problems.push("phone ShellHeader visible on desktop (double header)");
  if (r.width >= 768 && r.headerBars > 1) problems.push(`${r.headerBars} header bars on desktop`);
  if (r.expect === 0) problems.push("expected page content missing (fixture not applied?)");
  if (r.width >= 1024 && r.page === "matchup" && r.mainWidth < 1000) problems.push(`matchup column only ${r.mainWidth}px wide at desktop`);
  if (r.recRowMaxH > 96) problems.push(`recommended-add row ${r.recRowMaxH}px tall (compact rows are <= 96)`);
  if (r.modules === 0 && !r.noModules) problems.push("no compact modules rendered (fixtures not applied?)");
  if (problems.length) bad += 1;
  console.log(`${problems.length ? "FAIL" : "ok  "} ${r.page}@${r.width}: modules=${r.modules} heroes=${r.heroes} headers=${r.headerBars} main=${r.mainWidth} recRows=${r.recRows}/${r.recRowMaxH} tablists=${r.tablists} height=${r.height}${problems.length ? "  " + problems.join("; ") : ""}`);
}
console.log(bad ? `${bad} page(s) with problems` : "module scan clean");
process.exit(bad ? 1 : 0);
