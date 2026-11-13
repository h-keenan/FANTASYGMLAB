// 390px screenshots of the Fantasy Sim League tab's who-has-who views, a team's roster sheet and the trade partner list.
//   PW_CORE=/path/to/playwright-core/index.mjs BASE=http://localhost:3197 OUT=/tmp/shots node scripts/sim_layout_playwright/league_who.mjs [scenario]
import fs from "fs";
import { createMock } from "./simmock.mjs";

const { chromium } = await import(process.env.PW_CORE || "playwright-core");
const BASE = process.env.BASE || "http://localhost:3197";
const OUT = process.env.OUT || "/private/tmp/claude-501/lr-shots";
fs.mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.HOME + "/Library/Caches/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-mac-arm64/chrome-headless-shell" });
const session = {
  access_token: "a.b.c", refresh_token: "r", token_type: "bearer", expires_in: 99999, expires_at: Math.floor(Date.now() / 1000) + 99999,
  user: { id: "u1", aud: "authenticated", role: "authenticated", email: "t@example.com", app_metadata: {}, user_metadata: {}, created_at: "2026-01-01T00:00:00Z" },
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const J = (b) => ({ status: 200, contentType: "application/json", body: JSON.stringify(b), headers: { "access-control-allow-origin": "*" } });
const only = process.argv[2];
const requests = [];

async function scenario(name, steps, { theme = "dark", w = 390, shots = 1 } = {}) {
  if (only && !name.startsWith(only)) return;
  const mock = createMock({ status: "in_season", week: 3 });
  const ctx = await browser.newContext({ viewport: { width: w, height: 844 }, deviceScaleFactor: 2 });
  await ctx.addInitScript(([t, s]) => { try { localStorage.setItem("fgl:theme-mode", t); localStorage.setItem("sb-dummy-auth-token", JSON.stringify(s)); localStorage.setItem("fgl:onboarding-complete", "1"); } catch (e) {} }, [theme, session]);
  await ctx.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.hostname === "localhost" && url.port === "8000") {
      requests.push(`${name}: ${route.request().method()} ${url.pathname}`);
      const body = route.request().postData();
      let json = null; try { json = body ? JSON.parse(body) : null; } catch {}
      const res = mock(route.request().method(), url.pathname, Object.fromEntries(url.searchParams.entries()), json);
      if (res) return route.fulfill({ status: res.status, contentType: "application/json", body: JSON.stringify(res.body), headers: { "access-control-allow-origin": "*" } });
      if (url.pathname.endsWith("/preferences")) return route.fulfill(J({ ok: true, experience_level: "advanced" }));
      return route.fulfill(J({ ok: true, status: "unavailable", points: [], items: [], history: null }));
    }
    if (url.hostname === "dummy.supabase.co") return route.fulfill(J({}));
    return route.continue();
  });
  const page = await ctx.newPage();
  page.on("pageerror", (e) => console.log("PAGEERR", name, e.message));
  page.on("console", (m) => { if (m.type() === "error" && !/Failed to load resource|net::ERR/.test(m.text())) console.log("CONSOLE", name, m.text().slice(0, 300)); });
  try {
    await page.goto(`${BASE}/gm-game`, { waitUntil: "domcontentloaded" });
    await page.waitForSelector("main", { timeout: 60000 }).catch(() => {});
    await sleep(2500);
    await page.getByRole("button", { name: "Open game" }).first().click();
    await sleep(2500);
    await steps(page);
  } catch (e) { console.log("STEPERR", name, e.message.split("\n")[0]); }
  const scroller = () => page.evaluate(() => { const el = document.querySelector(".pqv-scroll"); return el ? [el.scrollHeight, el.clientHeight] : [document.documentElement.scrollHeight, innerHeight]; });
  const [full, view] = await scroller();
  for (let i = 0, y = 0; i < shots && (i === 0 || y < full); i++, y += Math.max(300, view - 80)) {
    await page.evaluate((top) => { const el = document.querySelector(".pqv-scroll"); if (el) el.scrollTop = top; else window.scrollTo(0, top); }, y);
    await sleep(500);
    await page.screenshot({ path: `${OUT}/${name}-${theme}-${w}-s${i}.png` });
  }
  await ctx.close();
}

const tab = async (page, name) => { await page.getByRole("tab", { name, exact: false }).first().click(); await sleep(1200); };

await scenario("1-league-teams", async (page) => { await tab(page, "League"); await tab(page, "Teams"); await sleep(800); }, { shots: 3 });
await scenario("2-league-qbs", async (page) => { await tab(page, "League"); await page.getByRole("tab", { name: "Players", exact: true }).last().click(); await sleep(1200); await page.getByRole("tab", { name: "QB", exact: true }).click(); await sleep(800); });
await scenario("3-find-player", async (page) => { await tab(page, "League"); await page.getByRole("tab", { name: "Players", exact: true }).last().click(); await sleep(1200); await page.getByLabel("Find a player").fill("moore"); await sleep(800); });
await scenario("4-team-roster", async (page) => { await tab(page, "League"); await tab(page, "Teams"); await page.getByRole("button", { name: /Open roster/ }).nth(4).click(); await sleep(1800); }, { shots: 6 });
for (const [i, name] of ["Overview", "Roster", "Trades", "History"].entries()) {
  await scenario(`6-team-tab-${i + 1}-${name.toLowerCase()}`, async (page) => {
    await tab(page, "League"); await tab(page, "Teams");
    await page.getByRole("button", { name: /Open roster/ }).nth(4).click(); await sleep(1500);
    await page.getByRole("dialog").getByRole("tab", { name }).click(); await sleep(1200);
  }, { shots: name === "Overview" || name === "History" ? 2 : 1 });
}
await scenario("5-trade-partner", async (page) => { await tab(page, "Trades"); await tab(page, "Make an offer"); await sleep(800); }, { shots: 2 });
console.log([...new Set(requests)].join("\n"));
await browser.close();
