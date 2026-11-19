// Cold first visit of a real Desk page at 390px (manual tool, not CI). Companion to phone_perf.mjs, which only covers the
// sim flows and /sample-league: this one drives /dashboard/<league> (or any Desk path) with the API mocked from the bodies
// scripts/bench_endpoints.py --bodies-dir captured, delayed by that endpoint's MEASURED cold server time, so the client
// waterfall (auth -> lens detection -> fetch fan-out -> paint) is reproducible and attributable.
//
//   PW_CORE=<playwright-core>/index.mjs CHROME_PATH=".../Google Chrome" BASE=http://localhost:3190 BODIES=<dir> \
//   CPU=4 NET=4g RUNS=3 WARM=0|1 PAGE=/dashboard/L1?name=Test node scripts/perf/desk_cold.mjs
//
// COLD=1 (default): empty browser cache and localStorage, cold server cache (cold latencies). WARM=1: second visit in the same
// context (HTTP cache + stored lens), warm server latencies.
import fs from "fs";

const { chromium } = await import(process.env.PW_CORE || "playwright-core");
const BASE = process.env.BASE || "http://localhost:3190";
const BODIES = process.env.BODIES || "";
const CPU = Number(process.env.CPU || 4);
const NET = process.env.NET || "4g";
const RUNS = Number(process.env.RUNS || 3);
const PAGE = process.env.PAGE || "/dashboard/L1?name=Test%20League";
const READY = process.env.READY || "[data-testid], main h1, main section";
const PROFILES = { "4g": { latency: 70, down: 9e6 / 8, up: 4.5e6 / 8 }, fast3g: { latency: 150, down: 1.6e6 / 8, up: 0.75e6 / 8 }, none: null };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const median = (a) => [...a].sort((x, y) => x - y)[Math.floor(a.length / 2)];
const session = { access_token: "a.b.c", refresh_token: "r", token_type: "bearer", expires_in: 99999, expires_at: Math.floor(Date.now() / 1000) + 99999, user: { id: "u1", aud: "authenticated", role: "authenticated", email: "t@example.com", app_metadata: {}, user_metadata: {}, created_at: "2026-01-01T00:00:00Z" } };

// endpoint -> [body file, cold server ms, warm server ms] (cold/warm from scripts/bench_endpoints.py on the same fixture).
const ROUTES = [
  [/\/v1\/leagues\/[^/]+\/dashboard$/, (u) => (u.searchParams.get("defer_trade_ideas") ? "dashboard_deferred" : "dashboard"), { dashboard_deferred: [1230, 31], dashboard: [4200, 29] }],
  [/\/v1\/leagues\/[^/]+\/team-rankings$/, () => "team_rankings", { team_rankings: [555, 21] }],
  [/\/v1\/leagues\/[^/]+\/matchup$/, () => "matchup", { matchup: [417, 38] }],
  [/\/v1\/leagues\/[^/]+\/my-team$/, () => "my_team", { my_team: [440, 25] }],
  // The needs payload has a different shape from the my-team body; serving the wrong one crashed the page (positionGroups), so the
  // harness answers 404 and the page's best-effort path skips the section, like every other unmocked secondary endpoint.
  [/\/v1\/leagues\/[^/]+\/my-team-needs$/, () => "NOT_FOUND", null],
  // Round 4: the other Desk pages (cold/warm from scripts/bench_endpoints.py on the same fixture).
  [/\/v1\/leagues\/[^/]+\/waivers$/, () => "waivers", { waivers: [940, 100] }],
  [/\/v1\/leagues\/[^/]+\/gm-plan$/, () => "gm_plan", { gm_plan: [2250, 170] }],
  [/\/v1\/leagues\/[^/]+\/trade-finder$/, () => "trade_finder", { trade_finder: [40, 2] }],
  [/\/v1\/leagues\/[^/]+\/trade-hub$/, () => "trade_hub", { trade_hub: [2400, 6] }],
  [/\/v1\/leagues-glance$/, () => "leagues_glance", { leagues_glance: [3500, 2] }],
  [/\/v1\/leagues\/[^/]+$/, () => null, null],
  [/\/v1\/leagues$/, () => "LEAGUES", null],
];
const COLD_UNKNOWN = Number(process.env.COLD_UNKNOWN_MS || 120);
const WARM_UNKNOWN = Number(process.env.WARM_UNKNOWN_MS || 15);
const LEAGUE_COLD = Number(process.env.LEAGUE_COLD_MS || 150);

function respond(u, cold) {
  for (const [re, pick, ms] of ROUTES) {
    if (!re.test(u.pathname)) continue;
    const name = pick(u);
    if (name === "NOT_FOUND") return { ms: cold ? COLD_UNKNOWN : WARM_UNKNOWN, status: 404, body: { detail: "not mocked" } };
    if (name === "LEAGUES") return { ms: cold ? 200 : WARM_UNKNOWN, body: { ok: true, leagues: [{ league_id: "L1", league_name: "Test League", season: "2026" }] } };
    if (!name) return { ms: cold ? LEAGUE_COLD : WARM_UNKNOWN, body: { ok: true, default_lens: "Dynasty", id: "L1", name: "Test League" } };
    const file = BODIES ? `${BODIES}/${name}.${cold ? "cold" : "warm"}.json` : "";
    return { ms: ms[name][cold ? 0 : 1], body: file && fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, "utf8")) : {} };
  }
  return { ms: cold ? COLD_UNKNOWN : WARM_UNKNOWN, body: { ok: true, items: [], alerts: [], reason: "" } };
}

async function visit(ctx, cold, label) {
  const reqs = [];
  const page = await ctx.newPage();
  const t0 = Date.now();
  if (process.env.DEBUG_ERR) page.on("console", (m) => { if (m.type() === "error") console.log("CON", m.text().slice(0, 260)); });
  page.on("request", (r) => { const u = new URL(r.url()); if (u.port === "8000") reqs.push({ k: `${r.method()} ${u.pathname}${u.search.slice(0, 40)}`, at: Date.now() - t0 }); });
  await page.addInitScript(() => {
    window.__p = { fcp: 0, lcp: 0 };
    new PerformanceObserver((l) => l.getEntries().forEach((e) => { if (e.name === "first-contentful-paint") window.__p.fcp = e.startTime; })).observe({ type: "paint", buffered: true });
    new PerformanceObserver((l) => l.getEntries().forEach((e) => { window.__p.lcp = e.startTime; })).observe({ type: "largest-contentful-paint", buffered: true });
  });
  const cdp = await ctx.newCDPSession(page);
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: CPU });
  const prof = PROFILES[NET];
  if (prof) await cdp.send("Network.emulateNetworkConditions", { offline: false, latency: prof.latency, downloadThroughput: prof.down, uploadThroughput: prof.up });
  await page.goto(BASE + PAGE, { waitUntil: "domcontentloaded" });
  // "useful content": the first compact module with a real summary line (skeletons are aria-busy regions).
  // TODAY=1 (default for /dashboard paths): the first Today module with a real summary. Any other page (Matchup, Team, League,
  // Players, Waivers, Trades, Sim Home): <main> has real text and no skeleton (aria-busy) region left.
  const isToday = (process.env.PAGE || PAGE).startsWith("/dashboard");
  await page.waitForFunction((today) => today
    ? document.querySelector('[data-testid="today-tiles"], [data-testid="today-matchup"], [data-testid="compact-summary"]') && !document.querySelector("main[aria-busy='true']")
    : document.querySelector("main") && document.querySelector("main").innerText.trim().length > 150 && !document.querySelector("main [aria-busy='true'], main[aria-busy='true']"), isToday, { timeout: Number(process.env.WAIT_MS || 60000) }).catch(async () => { console.log("TIMEOUT", await page.evaluate(() => [...document.querySelectorAll("[data-testid]")].map((e) => e.getAttribute("data-testid")).slice(0, 12).join(",") + " busy=" + document.querySelector("main")?.getAttribute("aria-busy") + " path=" + location.pathname + " main=" + (document.querySelector("main")?.innerText || "").replace(/\s+/g, " ").slice(0, 160))); await page.screenshot({ path: "/private/tmp/claude-501/s/timeout.png" }); });
  const usefulMs = Date.now() - t0;
  await sleep(800);
  const p = await page.evaluate(() => ({ ...window.__p, js: performance.getEntriesByType("resource").filter((e) => e.name.endsWith(".js")).reduce((a, e) => a + (e.transferSize || 0), 0) }));
  await page.close();
  return { label, usefulMs, fcp: Math.round(p.fcp), lcp: Math.round(p.lcp), jsKB: Math.round(p.js / 1024), waterfall: reqs.map((r) => `${r.at}ms ${r.k}`) };
}

const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH, headless: true });
const rows = [];
for (let i = 0; i < RUNS; i++) {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 3, hasTouch: true, isMobile: true, userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1" });
  await ctx.addInitScript(([s]) => { try { if (!localStorage.getItem("sb-dummy-auth-token")) { localStorage.setItem("sb-dummy-auth-token", JSON.stringify(s)); localStorage.setItem("fgl:onboarding-complete", "1"); } } catch {} }, [session]);
  let coldMode = true;
  await ctx.route("**/*", async (route) => {
    const req = route.request(); const u = new URL(req.url());
    const cors = { "access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "*" };
    if (u.hostname === "localhost" && u.port === "8000") {
      if (req.method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
      const r = respond(u, coldMode);
      await sleep(r.ms);
      return route.fulfill({ status: r.status || 200, contentType: "application/json", body: JSON.stringify(r.body), headers: cors });
    }
    if (u.hostname === "dummy.supabase.co") { await sleep(60); return route.fulfill({ status: 200, contentType: "application/json", body: u.pathname.startsWith("/rest/") ? "[]" : "{}", headers: cors }); }
    if (u.hostname === "localhost") return route.continue();
    return route.abort();
  });
  rows.push(await visit(ctx, true, "cold"));
  coldMode = false;
  rows.push(await visit(ctx, false, "warm"));
  await ctx.close();
}
await browser.close();
for (const label of ["cold", "warm"]) {
  const r = rows.filter((x) => x.label === label);
  console.log(`${label}: useful ${median(r.map((x) => x.usefulMs))} ms  FCP ${median(r.map((x) => x.fcp))}  LCP ${median(r.map((x) => x.lcp))}  JS ${r[0].jsKB} KB`);
}
console.log("cold waterfall:\n  " + rows.find((x) => x.label === "cold").waterfall.join("\n  "));
if (process.env.OUT) fs.writeFileSync(process.env.OUT, JSON.stringify(rows, null, 1));
