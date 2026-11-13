// Fantasy Sim phone-layout check (manual tool, not part of CI).
// Mocks /v1/sim/games against `next dev -p 3187` (web-next/.env.local with dummy Supabase vars) and, per game
// screen, records total scroll height in viewport heights and document scrollWidth (must be <= viewport).
// Usage: npm i playwright-core (anywhere), then
//   CHROME_PATH=/path/to/chrome OUT=/tmp/sim-shots [SIZES=360,390,820,1100] [THEMES=dark] node measure.mjs [scenario-prefix]
// Writes PNGs plus measure.json ({ <scenario>: { height, vh, heads }, __overflow: { "<scenario>@<width>": scrollWidth } }).
import { chromium } from "playwright-core";
import fs from "fs";
import { createMock } from "./simmock.mjs";

const OUT = process.env.OUT || "/private/tmp/claude-501/sml-shots/before";
const MEAS = {};
fs.mkdirSync(OUT, { recursive: true });
const only = process.argv[2];
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH });

const session = {
  access_token: "a.b.c", refresh_token: "r", token_type: "bearer", expires_in: 99999, expires_at: Math.floor(Date.now() / 1000) + 99999,
  user: { id: "u1", aud: "authenticated", role: "authenticated", email: "t@example.com", app_metadata: {}, user_metadata: {}, created_at: "2026-01-01T00:00:00Z" },
};

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const ok = (name) => name;
const log = [];

const SIZES = process.env.SIZES ? process.env.SIZES.split(",").map(Number) : null;
const THEMES = process.env.THEMES ? process.env.THEMES.split(",") : null;
async function scenario(name, mockOpts, steps, { sizes = [390, 1280], themes = ["dark", "light"], extra = null } = {}) {
  if (SIZES) sizes = SIZES; if (THEMES) themes = THEMES;
  if (only && !name.startsWith(only)) return;
  for (const theme of themes) for (const w of sizes) {
    const mock = createMock(mockOpts);
    const ctx = await browser.newContext({ viewport: { width: w, height: w === 390 ? 844 : 900 }, deviceScaleFactor: 1 });
    await ctx.addInitScript(([t, s]) => { try { localStorage.setItem("fgl:theme-mode", t); localStorage.setItem("sb-dummy-auth-token", JSON.stringify(s)); localStorage.setItem("fgl:onboarding-complete", "1"); } catch (e) {} }, [theme, session]);
    await ctx.route("**/*", async (route) => {
      const url = new URL(route.request().url());
      if (url.hostname === "localhost" && url.port === "8000") {
        const body = route.request().postData();
        let json = null; try { json = body ? JSON.parse(body) : null; } catch {}
        const query = Object.fromEntries(url.searchParams.entries());
        const res = mock(route.request().method(), url.pathname, query, json);
        if (res) return route.fulfill({ status: res.status, contentType: "application/json", body: JSON.stringify(res.body), headers: { "access-control-allow-origin": "*" } });
        return route.fulfill({ status: 200, contentType: "application/json", body: "{}", headers: { "access-control-allow-origin": "*" } });
      }
      if (url.hostname === "dummy.supabase.co") return route.fulfill({ status: 200, contentType: "application/json", body: "{}", headers: { "access-control-allow-origin": "*" } });
      return route.continue();
    });
    const page = await ctx.newPage();
    page.on("pageerror", (e) => log.push(`PAGEERR ${name} ${w}: ${e.message}`));
    page.on("console", (m) => { if (m.type() === "error" && !/Failed to load resource|net::ERR/.test(m.text())) log.push(`CONSOLE ${name} ${w}: ${m.text().slice(0, 200)}`); });
    await page.goto("http://localhost:3187/gm-game", { waitUntil: "domcontentloaded" });
    await page.waitForSelector("main", { timeout: 30000 }).catch(() => {});
    await sleep(2500);
    try { await steps(page, w); } catch (e) { log.push(`STEPERR ${name} ${w} ${theme}: ${e.message.split("\n")[0]}`); }
    await sleep(500);
    const h = await page.evaluate(() => document.documentElement.scrollHeight);
    const sw = await page.evaluate(() => document.documentElement.scrollWidth);
    if (theme === (THEMES ? THEMES[0] : "dark")) (MEAS.__overflow ??= {})[`${name}@${w}`] = sw;
    if (w === 390 && theme === "dark") {
      const heads = await page.evaluate(() => Array.from(document.querySelectorAll("h1,h2,h3")).filter((e) => e.getBoundingClientRect().height > 0).map((e) => ({ t: (e.textContent || "").trim().slice(0, 40), y: Math.round(e.getBoundingClientRect().top + window.scrollY) })));
      MEAS[name] = { height: h, vh: Math.round((h / 844) * 100) / 100, heads };
    }
    if (process.env.VP) {
      await page.evaluate(() => window.scrollTo(0, 0)); await sleep(300);
      await page.screenshot({ path: `${OUT}/${name}-${theme}-${w}-vptop.png` });
      await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight)); await sleep(500);
      await page.screenshot({ path: `${OUT}/${name}-${theme}-${w}-vpbot.png` });
    }
    await page.screenshot({ path: `${OUT}/${name}-${theme}-${w}${process.env.CLIP ? "-c" + process.env.CLIP.split(",")[0] : ""}.png`, fullPage: true, clip: (() => { const [y, hh] = (process.env.CLIP || "0,9000").split(",").map(Number); return { x: 0, y, width: w, height: Math.max(50, Math.min(hh, h - y)) }; })() });
    await ctx.close();
  }
}

const click = async (page, text, opts = {}) => { await page.getByRole(opts.role ?? "button", { name: text, exact: opts.exact ?? false }).first().click(); await sleep(opts.wait ?? 700); };
const tab = async (page, name) => { await page.getByRole("tab", { name, exact: false }).first().click(); await sleep(900); };

await scenario("01-hub", { status: "complete", week: 17 }, async () => {});
await scenario("02-final-champion", { status: "complete", week: 17, variant: "champion" }, async (page) => { await click(page, "Open game"); await sleep(2500); });
await scenario("03-final-missed", { status: "complete", week: 17, variant: "missed" }, async (page) => { await click(page, "Open game"); await sleep(2500); });
await scenario("04-draft-players", { status: "drafting", pickStart: 14 }, async (page) => { await click(page, "Open game"); await sleep(2000); });
await scenario("05-draft-board", { status: "drafting", pickStart: 14 }, async (page) => { await click(page, "Open game"); await sleep(1500); await tab(page, "Board"); await sleep(800); });
await scenario("06-draft-queue", { status: "drafting", pickStart: 14 }, async (page, w) => {
  await click(page, "Open game"); await sleep(1500);
  await page.getByRole("button", { name: /^Queue /i }).nth(0).click(); await sleep(300);
  await page.getByRole("button", { name: /^Queue /i }).nth(1).click(); await sleep(300);
  if (w < 1000) await tab(page, "Queue");
});
await scenario("07-home", { status: "in_season", week: 4 }, async (page) => { await click(page, "Open game"); await sleep(1800); });
await scenario("08-team", { status: "in_season", week: 4 }, async (page) => { await click(page, "Open game"); await tab(page, "Team"); await sleep(1200); });
await scenario("09-players", { status: "in_season", week: 4 }, async (page) => { await click(page, "Open game"); await tab(page, "Players"); await sleep(1200); });
await scenario("10-trades", { status: "in_season", week: 4 }, async (page) => { await click(page, "Open game"); await tab(page, "Trades"); await sleep(1200); });
await scenario("10b-trades-build", { status: "in_season", week: 4 }, async (page) => { await click(page, "Open game"); await tab(page, "Trades"); await sleep(800); await click(page, "Make an offer", { role: "tab" }); await sleep(1200); await page.getByRole("button", { name: /Trade with Red Zone Rats/ }).first().click(); await sleep(1200); await page.getByRole("button", { name: /^Give / }).first().click(); await sleep(400); });
await scenario("11-league", { status: "in_season", week: 4 }, async (page) => { await click(page, "Open game"); await tab(page, "League"); await sleep(1200); });
await scenario("12-week-recap", { status: "in_season", week: 3 }, async (page) => { await click(page, "Open game"); await sleep(1000); await click(page, "Advance to week 4", { wait: 1800 }); });
fs.writeFileSync(`${OUT}/measure${only ? "-" + only : ""}.json`, JSON.stringify(MEAS, null, 1));
console.log(log.join("\n") || "no errors");
await browser.close();
