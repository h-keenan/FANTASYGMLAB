// 390px screenshots of the Fantasy Sim player sheet (it IS the real Player Quick View) for a veteran, an IR veteran
// with no market value and a generated rookie, next to the real PQV for the same real-id player.
//   PW_CORE=/path/to/playwright-core/index.mjs BASE=http://localhost:3199 OUT=/tmp/shots node scripts/sim_layout_playwright/pqv_sheet.mjs
import fs from "fs";
import { createMock } from "./simmock.mjs";

const { chromium } = await import(process.env.PW_CORE || "playwright-core");
const BASE = process.env.BASE || "http://localhost:3199";
const OUT = process.env.OUT || "/private/tmp/claude-501/pqv-sheet-shots";
fs.mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.HOME + "/Library/Caches/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-mac-arm64/chrome-headless-shell" });
const session = {
  access_token: "a.b.c", refresh_token: "r", token_type: "bearer", expires_in: 99999, expires_at: Math.floor(Date.now() / 1000) + 99999,
  user: { id: "u1", aud: "authenticated", role: "authenticated", email: "t@example.com", app_metadata: {}, user_metadata: {}, created_at: "2026-01-01T00:00:00Z" },
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const J = (b) => ({ status: 200, contentType: "application/json", body: JSON.stringify(b), headers: { "access-control-allow-origin": "*" } });
const stat = (label, value, percentile = 80) => ({ label, value, note: "", tone: "reference", percentile });
// What the real quick-view API returns for a real player (the real PQV).
const QV = {
  ok: true, reason: "", stats: { seasons: [{ season: 2026, season_type: "Regular Season", games: 8, complete: null, label: "2026 Regular Season", key_stats: [stat("Targets", "61"), stat("Receptions", "40")], fantasy: [stat("PPR", "98.4")], usage: [], efficiency: [] }], college: [], college_available: false, career_totals_available: false, position: "WR", overall_rating: 64, prime_window: null },
  bio: { years_in_league: "9 seasons", draft_capital: "2018 / Round 3", college: "Oklahoma", height: "6'0\"", weight: "198 lb", bye_week: "9", contract_status: "" },
  model: { market_score: 60, opportunity_score: 50, scarcity_score: 40, role_score: 55, age_score: 30, age_score_label: "Age Score", opportunity_confidence: 70, workload_trend: "Declining", usage_trend: { direction: "down", trend_pct: -22, confidence_label: "Medium confidence", arrow: "▼", tone: "negative" }, depth_chart_note: null, decision_fit_narrative: "Age is the biggest driver of this valuation.", market_rating: 61, opportunity_rating: 52, scarcity_rating: 44, role_rating: 58, durability_rating: 49 },
};
const WEEKS = Array.from({ length: 8 }, (_, i) => ({ week: i + 1, fantasy_points_ppr: Math.round((6 + ((i * 7) % 9)) * 10) / 10, snap_share: 0.6 }));

async function open(page, name) {
  await page.goto(`${BASE}/gm-game`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("main", { timeout: 60000 }).catch(() => {});
  await sleep(2500);
  await page.getByRole("button", { name: "Open game" }).first().click();
  await sleep(2500);
  await page.getByRole("tab", { name: "Players" }).first().click();
  await sleep(1500);
  await page.locator("input[type=search], input[type=text]").first().fill(name.split(" ")[1]);
  await sleep(1800);
  await page.getByText(name, { exact: false }).first().click();
  await sleep(4000);
}

const only = process.argv[2];
const cast = [["vet", "Jaxon Moore"], ["ir", "Dalton Reyes"], ["rookie", "Brock Briggs"]];
for (const theme of ["dark"]) for (const [kind, name] of cast) {
  if (only && kind !== only) continue;
  const w = 390;
  const mock = createMock({ status: "in_season", week: 3, sheetDemo: true, ...(globalThis.__mockOpts || {}) });
  const ctx = await browser.newContext({ viewport: { width: w, height: 844 }, deviceScaleFactor: 2 });
  await ctx.addInitScript(([t, s]) => { try { localStorage.setItem("fgl:theme-mode", t); localStorage.setItem("sb-dummy-auth-token", JSON.stringify(s)); localStorage.setItem("fgl:onboarding-complete", "1"); } catch (e) {} }, [theme, session]);
  await ctx.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.hostname === "localhost" && url.port === "8000") {
      const body = route.request().postData();
      let json = null; try { json = body ? JSON.parse(body) : null; } catch {}
      const res = mock(route.request().method(), url.pathname, Object.fromEntries(url.searchParams.entries()), json);
      if (res) return route.fulfill({ status: res.status, contentType: "application/json", body: JSON.stringify(res.body), headers: { "access-control-allow-origin": "*" } });
      if (url.pathname.endsWith("/quick-view")) return route.fulfill(J(QV));
      if (url.pathname.endsWith("/news")) return route.fulfill(J({ ok: true, injury_item: null, total: 0, has_more: false, items: [] }));
      if (url.pathname.endsWith("/awards")) return route.fulfill(J({ ok: true, awards: [] }));
      if (url.pathname.includes("weekly")) return route.fulfill(J({ ok: true, season: 2026, weeks: WEEKS }));
      if (url.pathname.endsWith("/preferences")) return route.fulfill(J({ ok: true, experience_level: "advanced" }));
      return route.fulfill(J({ ok: true, status: "unavailable", points: [], items: [], history: null }));
    }
    if (url.hostname === "dummy.supabase.co") return route.fulfill(J({}));
    return route.continue();
  });
  const page = await ctx.newPage();
  page.on("pageerror", (e) => console.log("PAGEERR", kind, e.message));
  try { await open(page, name); } catch (e) { console.log("OPENERR", kind, e.message.split("\n")[0]); }
  // the sheet scrolls inside .pqv-scroll: one screenshot per screenful (top, then scrolled)
  const full = await page.evaluate(() => { const el = document.querySelector(".pqv-scroll"); return el ? el.scrollHeight : 0; });
  const view = await page.evaluate(() => { const el = document.querySelector(".pqv-scroll"); return el ? el.clientHeight : 0; });
  for (let i = 0, y = 0; y < full && i < 8; i++, y += Math.max(300, view - 60)) {
    await page.evaluate((top) => { const el = document.querySelector(".pqv-scroll"); if (el) el.scrollTop = top; }, y);
    await sleep(500);
    await page.screenshot({ path: `${OUT}/${kind}-${theme}-${w}-s${i}.png` });
  }
  console.log(kind, "scrollHeight", full);
  await ctx.close();
}
await browser.close();
