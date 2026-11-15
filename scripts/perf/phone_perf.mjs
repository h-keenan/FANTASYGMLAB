// Phone-realistic performance harness for web-next (manual tool, not CI).
//
// Chrome (iPhone-sized viewport, touch, DPR 3) + CDP CPU throttle + network profile, against a PRODUCTION build
// (`next build && next start -p 3190`). The backend is a Playwright route mock (scripts/sim_layout_playwright/simmock.mjs:
// real response shapes, deterministic) with a fixed API latency, so numbers are comparable before/after on one box.
//
//   PW_CORE=/path/to/playwright-core/index.mjs CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
//   BASE=http://localhost:3190 CPU=4 NET=4g API_MS=60 RUNS=3 OUT=perf.json node scripts/perf/phone_perf.mjs [flow-prefix]
//
// Per cold load: FCP, LCP, TBT (sum of long-task time over 50 ms), CLS, JS bytes, request count/bytes/duplicates, heap.
// Per interaction step: INP-style event duration, long-task total, CDP Performance deltas (script / layout / style
// recalculation time and counts, task time), DOM mutation count (render-work proxy), backdrop-filter element count,
// requests started, and for scroll steps: rAF frame deltas (p95, frames over 25 ms) while a touch fling runs.
import fs from "fs";
import { createMock } from "../sim_layout_playwright/simmock.mjs";

const { chromium } = await import(process.env.PW_CORE || "playwright-core");
const BASE = process.env.BASE || "http://localhost:3190";
const CPU = Number(process.env.CPU || 4);
const NET = process.env.NET || "4g";
const API_MS = Number(process.env.API_MS || 60);
const RUNS = Number(process.env.RUNS || 3);
const OUT = process.env.OUT || "";
const only = process.argv[2] || "";
const PROFILES = { "4g": { latency: 70, down: 9e6 / 8, up: 4.5e6 / 8 }, fast3g: { latency: 150, down: 1.6e6 / 8, up: 0.75e6 / 8 }, none: null };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const session = { access_token: "a.b.c", refresh_token: "r", token_type: "bearer", expires_in: 99999, expires_at: Math.floor(Date.now() / 1000) + 99999, user: { id: "u1", aud: "authenticated", role: "authenticated", email: "t@example.com", app_metadata: {}, user_metadata: {}, created_at: "2026-01-01T00:00:00Z" } };

const INIT = () => {
  const w = window;
  w.__perf = { fcp: 0, lcp: 0, cls: 0, tasks: [], events: [], loaf: [], muts: 0 };
  const po = (type, cb, opts = {}) => { try { new PerformanceObserver((l) => l.getEntries().forEach(cb)).observe({ type, buffered: true, ...opts }); } catch {} };
  po("paint", (e) => { if (e.name === "first-contentful-paint") w.__perf.fcp = e.startTime; });
  po("largest-contentful-paint", (e) => { w.__perf.lcp = e.startTime; });
  po("layout-shift", (e) => { if (!e.hadRecentInput) w.__perf.cls += e.value; });
  po("longtask", (e) => w.__perf.tasks.push([e.startTime, e.duration]));
  po("long-animation-frame", (e) => w.__perf.loaf.push([e.startTime, e.duration, e.blockingDuration || 0]));
  po("event", (e) => w.__perf.events.push([e.startTime, e.duration, e.name]), { durationThreshold: 16 });
  const start = () => new MutationObserver((r) => { w.__perf.muts += r.length; }).observe(document, { subtree: true, childList: true, attributes: true, characterData: true });
  if (document.documentElement) start(); else document.addEventListener("DOMContentLoaded", start);
  w.__frames = { on: false, last: 0, d: [] };
  const tick = (t) => { const f = w.__frames; if (f.on) { if (f.last) f.d.push(t - f.last); f.last = t; } requestAnimationFrame(tick); };
  requestAnimationFrame(tick);
};

const pct = (a, p) => { if (!a.length) return 0; const s = [...a].sort((x, y) => x - y); return s[Math.min(s.length - 1, Math.floor((p / 100) * s.length))]; };
const median = (a) => pct(a, 50);

async function cdpMetrics(cdp) { const { metrics } = await cdp.send("Performance.getMetrics"); return Object.fromEntries(metrics.map((m) => [m.name, m.value])); }
const DIFF = ["TaskDuration", "ScriptDuration", "LayoutDuration", "RecalcStyleDuration", "LayoutCount", "RecalcStyleCount"];

const heavy = () => {
  // backdrop-filter elements currently rendered (the GPU-cost suspect), plus total DOM nodes.
  let bf = 0; const all = document.body.getElementsByTagName("*");
  for (const el of all) { const s = getComputedStyle(el); if (s.backdropFilter && s.backdropFilter !== "none") bf++; }
  return { nodes: all.length, backdrop: bf, heapMB: performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1048576) : 0 };
};

async function runFlow(browser, flow) {
  const mock = createMock(flow.mock);
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 3, hasTouch: true, isMobile: true, userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1" });
  await ctx.addInitScript(([s]) => { try { localStorage.setItem("fgl:theme-mode", "dark"); localStorage.setItem("sb-dummy-auth-token", JSON.stringify(s)); localStorage.setItem("fgl:onboarding-complete", "1"); } catch {} }, [session]);
  await ctx.addInitScript(INIT);
  const reqs = [];
  let stepReqs = 0;
  await ctx.route("**/*", async (route) => {
    const req = route.request(); const u = new URL(req.url());
    const cors = { "access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "*" };
    if (u.hostname === "localhost" && u.port === "8000") {
      if (req.method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
      stepReqs++;
      const raw = req.postData(); let json = null; try { json = raw ? JSON.parse(raw) : null; } catch {}
      let res = u.pathname.startsWith("/v1/sim") ? mock(req.method(), u.pathname, Object.fromEntries(u.searchParams), json) : null;
      if (u.pathname.endsWith("/notifications")) res = { status: 200, body: { ok: true, reason: "", seq: 9, unread: 0, items: [] } };
      await sleep(API_MS);
      const body = JSON.stringify(res?.body ?? {});
      reqs.push({ kind: "api", key: `${req.method()} ${u.pathname}`, bytes: body.length, at: Date.now() - t0 - API_MS });
      return route.fulfill({ status: res?.status ?? 200, contentType: "application/json", body, headers: cors });
    }
    if (u.hostname === "dummy.supabase.co") { await sleep(API_MS); return route.fulfill({ status: 200, contentType: "application/json", body: "{}", headers: cors }); }
    if (u.hostname === "localhost") { reqs.push({ kind: "asset", key: u.pathname + u.search, type: req.resourceType() }); return route.continue(); }
    return route.abort(); // third parties (fonts CDN, analytics, avatars): excluded so runs are deterministic
  });
  const page = await ctx.newPage();
  const cdp = await ctx.newCDPSession(page);
  await cdp.send("Performance.enable");
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: CPU });
  const prof = PROFILES[NET];
  if (prof) await cdp.send("Network.emulateNetworkConditions", { offline: false, latency: prof.latency, downloadThroughput: prof.down, uploadThroughput: prof.up });
  const errors = []; page.on("pageerror", (e) => errors.push(e.message));
  const sizes = {}; cdp.on("Network.loadingFinished", (e) => { sizes[e.requestId] = e.encodedDataLength; });
  await cdp.send("Network.enable");
  const out = { cold: {}, steps: {} };
  const t0 = Date.now();

  await page.goto(BASE + flow.path, { waitUntil: "domcontentloaded" });
  await flow.ready(page);
  const loadMs = Date.now() - t0;
  await sleep(1200);
  const p = await page.evaluate(() => ({ ...window.__perf, ...(() => { const r = performance.getEntriesByType("resource"); return { jsBytes: r.filter((e) => e.name.endsWith(".js")).reduce((a, e) => a + (e.transferSize || 0), 0), cssBytes: r.filter((e) => e.name.endsWith(".css")).reduce((a, e) => a + (e.transferSize || 0), 0) }; })() }));
  const dupes = {}; for (const r of reqs.filter((r) => r.kind === "api")) dupes[r.key] = (dupes[r.key] || 0) + 1;
  out.cold = {
    fcp: Math.round(p.fcp), lcp: Math.round(p.lcp), tbt: Math.round(p.tasks.reduce((a, [, d]) => a + Math.max(0, d - 50), 0)), longTasks: p.tasks.length, cls: +p.cls.toFixed(3),
    readyMs: loadMs, jsKB: Math.round(p.jsBytes / 1024), cssKB: Math.round(p.cssBytes / 1024), muts: p.muts,
    waterfall: reqs.filter((r) => r.kind === "api").map((r) => `${r.at}ms ${r.key.replace(/[0-9a-f-]{36}/, ":id")}`), apiCalls: reqs.filter((r) => r.kind === "api").length, apiKB: Math.round(reqs.filter((r) => r.kind === "api").reduce((a, r) => a + r.bytes, 0) / 1024),
    assetReqs: reqs.filter((r) => r.kind === "asset").length, dupApi: Object.entries(dupes).filter(([, n]) => n > 1).map(([k, n]) => `${k} x${n}`), ...(await page.evaluate(heavy)),
  };

  const step = async (name, fn, { scroll = false } = {}) => {
    const before = await cdpMetrics(cdp); const m0 = await page.evaluate(() => { const w = window; w.__perf.tasks.length = 0; w.__perf.events.length = 0; w.__perf.loaf.length = 0; const m = w.__perf.muts; w.__frames.d = []; return m; });
    stepReqs = 0; const stepT0 = Date.now() - t0; const reqIdx = reqs.length;
    try {
      if (scroll) await page.evaluate(() => { window.__frames.on = true; window.__frames.last = 0; });
      await fn(page, cdp);
      await sleep(scroll ? 200 : 700);
    } catch (e) { out.steps[name] = { error: e.message.split("\n")[0] }; return; }
    const after = await cdpMetrics(cdp);
    const q = await page.evaluate(() => { window.__frames.on = false; const w = window; return { tasks: w.__perf.tasks, ev: w.__perf.events, loaf: w.__perf.loaf, muts: w.__perf.muts, frames: w.__frames.d, ...(() => { let bf = 0; for (const el of document.body.getElementsByTagName("*")) { const s = getComputedStyle(el); if (s.backdropFilter && s.backdropFilter !== "none") bf++; } return { backdrop: bf, nodes: document.body.getElementsByTagName("*").length, heapMB: performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1048576) : 0 }; })() }; });
    const d = {}; for (const k of DIFF) d[k] = +(after[k] - before[k]).toFixed(3);
    const s = {
      inpMs: Math.round(Math.max(0, ...q.ev.map((e) => e[1]))), longTaskMs: Math.round(q.tasks.reduce((a, [, x]) => a + x, 0)), loafBlockMs: Math.round(q.loaf.reduce((a, l) => a + l[2], 0)),
      taskMs: Math.round(d.TaskDuration * 1000), scriptMs: Math.round(d.ScriptDuration * 1000), layoutMs: Math.round(d.LayoutDuration * 1000), styleMs: Math.round(d.RecalcStyleDuration * 1000),
      layouts: d.LayoutCount, styleRecalcs: d.RecalcStyleCount, muts: q.muts - m0, api: stepReqs, backdrop: q.backdrop, nodes: q.nodes, heapMB: q.heapMB,
    };
    s.waterfall = reqs.slice(reqIdx).filter((r) => r.kind === "api").map((r) => `${r.at - stepT0}ms ${r.key.replace(/[0-9a-f]{8}-[0-9a-f-]{27}/, ":id")}`);
    if (scroll) { const f = q.frames; s.frames = f.length; s.frameP95 = Math.round(pct(f, 95)); s.slowFrames = f.filter((x) => x > 25).length; s.worstFrame = Math.round(Math.max(0, ...f)); }
    out.steps[name] = s;
  };
  await flow.steps(step, page, cdp);
  out.errors = errors.slice(0, 5);
  await ctx.close();
  return out;
}

async function fling(page, dist = 2400) {
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Input.synthesizeScrollGesture", { x: 195, y: 600, yDistance: -dist, speed: 1800, gestureSourceType: "touch" });
  await cdp.send("Input.synthesizeScrollGesture", { x: 195, y: 300, yDistance: dist, speed: 2400, gestureSourceType: "touch" });
  await cdp.detach();
}
const clickBtn = async (page, name, role = "button") => { await page.getByRole(role, { name, exact: false }).first().click({ timeout: 8000 }); };
// On a phone the section tabs live behind the footer orb: open the menu sheet, then tap the destination.
const reachOrb = async (page) => {
  // On pages with a context pill (Team lineup etc.) the orb is folded away until "Sections menu" is tapped.
  const pm = page.getByTestId("pill-menu");
  if (await pm.count() && await pm.first().isVisible().catch(() => false)) { await pm.first().click({ timeout: 8000 }); await sleep(450); }
  await page.getByTestId("sim-game-orb").first().click({ timeout: 8000 });
};
const tab = (name) => async (page) => { await reachOrb(page); await page.getByTestId("sim-game-nav").getByRole("button", { name: new RegExp(`^${name}`) }).first().click({ timeout: 8000 }); };
const openMenu = async (page) => { await reachOrb(page); await sleep(500); };

const simFlow = (name, mockOpts, steps, ready) => ({ name, path: "/gm-game", mock: mockOpts, ready: ready || (async (page) => { await page.getByRole("button", { name: "Open game" }).first().waitFor({ timeout: 60000 }); }), steps });
const FLOWS = [
  simFlow("sim-inseason", { status: "in_season", week: 4 }, async (step, page) => {
    await step("open-game(Home)", async () => { await clickBtn(page, "Open game"); await page.getByTestId("sim-game-orb").waitFor({ timeout: 30000 }); });
    await step("scroll-home", () => fling(page, 2000), { scroll: true });
    await step("footer-menu-open", openMenu);
    await step("footer-menu-close", async () => { await page.keyboard.press("Escape"); });
    await step("tab:Team(28 rows)", tab("Team"));
    await step("scroll-team", () => fling(page, 2400), { scroll: true });
    await step("tab:Players(200)", tab("Players"));
    await step("scroll-players", () => fling(page, 6000), { scroll: true });
    await step("player-sheet-open", async () => { await page.locator("[data-player-name]").first().click({ timeout: 8000 }); await sleep(900); });
    await step("player-sheet-close", async () => { await page.keyboard.press("Escape"); await sleep(400); });
    await step("tab:Trades", tab("Trades"));
    await step("tab:League", tab("League"));
    await step("scroll-league", () => fling(page, 2400), { scroll: true });
    await step("tab:Home", tab("Home"));
    await step("tab-switch-x4", async () => { for (const t of ["Team", "Players", "Trades", "League"]) { await tab(t)(page); await sleep(900); } });
  }),
  { name: "desk-sample", path: "/sample-league", mock: {}, ready: async (page) => { await page.getByRole("button", { name: "Roster", exact: false }).first().waitFor({ timeout: 60000 }); await sleep(500); }, steps: async (step, page) => {
    for (const t of ["Roster", "Top moves", "Trade", "Today"]) await step(`desk-tab:${t}`, async () => { await page.getByRole("button", { name: t, exact: false }).first().click({ timeout: 8000 }); await sleep(600); });
    await step("desk-roster-row-expand", async () => { await page.getByRole("button", { name: "Roster", exact: false }).first().click(); await sleep(600); await page.getByTestId("sample-player").first().locator("button").first().click({ timeout: 8000 }); });
    await step("desk-scroll", () => fling(page, 2400), { scroll: true });
  } },
  simFlow("sim-advance", { status: "in_season", week: 3 }, async (step, page) => {
    await step("open-game", async () => { await clickBtn(page, "Open game"); await sleep(1500); });
    await step("advance-week", async () => { await clickBtn(page, "Advance to week 4"); await sleep(1500); });
  }),
];

const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH, headless: true });
const results = {};
for (const flow of FLOWS) {
  if (only && !flow.name.startsWith(only)) continue;
  const runs = [];
  for (let i = 0; i < RUNS; i++) { runs.push(await runFlow(browser, flow)); process.stderr.write(`${flow.name} run ${i + 1}/${RUNS}\n`); }
  // median of each numeric leaf
  const med = (key, get) => { const v = runs.map(get).filter((x) => typeof x === "number"); return v.length ? median(v) : undefined; };
  const agg = { cold: {}, steps: {}, errors: runs.flatMap((r) => r.errors).slice(0, 5) };
  for (const k of Object.keys(runs[0].cold)) agg.cold[k] = typeof runs[0].cold[k] === "number" ? med(k, (r) => r.cold[k]) : runs[0].cold[k];
  for (const sname of Object.keys(runs[0].steps)) {
    const base = runs[0].steps[sname]; agg.steps[sname] = {};
    if (base.error) { agg.steps[sname] = base; continue; }
    for (const k of Object.keys(base)) if (Array.isArray(base[k])) agg.steps[sname][k] = base[k]; else agg.steps[sname][k] = +(median(runs.map((r) => r.steps[sname]?.[k]).filter((x) => typeof x === "number")) ?? 0).toFixed(3);
  }
  results[flow.name] = agg;
}
await browser.close();
const cfg = { cpu: CPU, net: NET, apiMs: API_MS, runs: RUNS, base: BASE };
if (OUT) fs.writeFileSync(OUT, JSON.stringify({ cfg, results }, null, 1));
console.log(JSON.stringify({ cfg, results }, null, 1));
