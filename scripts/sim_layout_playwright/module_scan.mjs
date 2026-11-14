// Module-template scan (docs/audits/2026-11-module-templates-rollout.md): Today, Team, Trades and League at phone width WITH data.
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
const WIDTHS = (process.env.WIDTHS || "360,390").split(",").map(Number);
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
const ROUTES = [
  { name: "today", path: `/dashboard/${LID}?name=Donk`, family: "none" },
  { name: "team", path: `/my-team/${LID}?name=Donk`, family: "team" },
  { name: "trades", path: `/trade-hub/${LID}?name=Donk`, family: "trades" },
  { name: "league", path: `/league-rankings/${LID}?name=Donk`, family: "league" },
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
  out.tablists = [...document.querySelectorAll('[role="tablist"]')].filter((el) => el.getBoundingClientRect().height > 0).length;
  return out;
};

const browser = await chromium.launch({ executablePath: process.env.CHROME || process.env.HOME + "/Library/Caches/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-mac-arm64/chrome-headless-shell" });
const results = [];
for (const w of WIDTHS) {
  const ctx = await browser.newContext({ viewport: { width: w, height: 844 }, hasTouch: true, isMobile: true });
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
      results.push({ page: r.name, width: w, ...res });
      if (w === 390) await page.screenshot({ path: `${OUT}/${r.name}-390.png`, fullPage: false });
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
  if (r.strip) {
    const s = r.strip, spread = Math.max(...s.widths) - Math.min(...s.widths);
    if (Math.abs(s.left) > 0.5 || Math.abs(s.right) > 0.5) problems.push(`tab strip not full-bleed (left ${s.left}, right gap ${s.right})`);
    if (Math.abs(s.tabLeft - s.tabRight) > 2) problems.push(`tabs not centred (left ${s.tabLeft}, right ${s.tabRight})`);
    if (spread > 8) problems.push(`tab widths uneven ${s.widths}`);
    if (s.minAlpha < 0.9) problems.push(`tab strip backing see-through (alpha ${s.minAlpha})`);
    if (s.headerBottom != null && Math.abs(s.top - s.headerBottom) > 1) problems.push(`tab strip top ${s.top} != header bottom ${s.headerBottom}`);
  }
  if ((r.tablists ?? 0) > 1) problems.push(`${r.tablists} tab rows`);
  if (r.modules === 0) problems.push("no compact modules rendered (fixtures not applied?)");
  if (problems.length) bad += 1;
  console.log(`${problems.length ? "FAIL" : "ok  "} ${r.page}@${r.width}: modules=${r.modules} heroes=${r.heroes} strip=${JSON.stringify(r.strip)} tablists=${r.tablists} height=${r.height}${problems.length ? "  " + problems.join("; ") : ""}`);
}
console.log(bad ? `${bad} page(s) with problems` : "module scan clean");
process.exit(bad ? 1 : 0);
