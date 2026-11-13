// 390px screenshots of every page of the weekly-recap story carousel.
//   PW_CORE=/path/to/playwright-core/index.mjs BASE=http://localhost:3197 OUT=/tmp/shots node scripts/sim_layout_playwright/story_recap.mjs
import fs from "fs";
import { createMock } from "./simmock.mjs";

const { chromium } = await import(process.env.PW_CORE || "playwright-core");
const BASE = process.env.BASE || "http://localhost:3197";
const OUT = process.env.OUT || "/private/tmp/claude-501/story-shots";
fs.mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.HOME + "/Library/Caches/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-mac-arm64/chrome-headless-shell" });
const session = { access_token: "a.b.c", refresh_token: "r", token_type: "bearer", expires_in: 99999, expires_at: Math.floor(Date.now() / 1000) + 99999, user: { id: "u1", aud: "authenticated", role: "authenticated", email: "t@example.com", app_metadata: {}, user_metadata: {}, created_at: "2026-01-01T00:00:00Z" } };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const mock = createMock({ status: "in_season", week: 4, pro: true });
const ctx = await browser.newContext({ viewport: { width: 900, height: 900 }, hasTouch: false, isMobile: false, deviceScaleFactor: 2 });
await ctx.addInitScript(([s]) => { try { localStorage.setItem("fgl:theme-mode", "dark"); localStorage.setItem("sb-dummy-auth-token", JSON.stringify(s)); localStorage.setItem("fgl:onboarding-complete", "1"); } catch (e) {} }, [session]);
await ctx.route("**/*", async (route) => {
  const u = new URL(route.request().url());
  const cors = { "access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "*" };
  if (u.hostname === "localhost" && u.port === "8000") {
    if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
    const raw = route.request().postData(); let json = null; try { json = raw ? JSON.parse(raw) : null; } catch {}
    const res = u.pathname.startsWith("/v1/sim") ? mock(route.request().method(), u.pathname, Object.fromEntries(u.searchParams), json) : { status: 404, body: {} };
    if (u.pathname.endsWith("/advance") && res?.body?.recap) {
      const names = ["Gridiron Goats", "Blitz Brigade", "Hail Marys", "Bench Mob", "Flex Appeal", "Boom or Bust"];
      res.body.recap.scores = [[0, 1, 102, 95.2], [2, 3, 110.4, 101], [4, 5, 140.7, 68.9]].map(([a, b, x, y]) => ({ home: String(a + 1), away: String(b + 1), home_pts: x, away_pts: y, winner: String(x > y ? a + 1 : b + 1) }));
      res.body.recap.standings = names.map((n, i) => ({ rank: i + 1, team_id: String(i + 1), name: n, is_you: false, wins: 3, losses: 1, ties: 0, pf: 400, pa: 380 }));
    }
    return route.fulfill({ status: res?.status ?? 200, contentType: "application/json", body: JSON.stringify(res?.body ?? {}), headers: cors });
  }
  if (u.hostname === "dummy.supabase.co") return route.fulfill({ status: 200, contentType: "application/json", body: "{}", headers: cors });
  return route.continue();
});
const page = await ctx.newPage();
page.on("request", (r) => { if (r.url().includes(":8000") && r.method() === "POST") console.log("POST", new URL(r.url()).pathname); });
page.on("console", (m) => { if (m.type() === "error") console.log("CONSOLE", m.text().slice(0, 160)); });
page.on("pageerror", (e) => console.log("PAGEERR", e.message));
await page.goto(`${BASE}/gm-game`, { waitUntil: "domcontentloaded" });
await page.addStyleTag({ content: "nextjs-portal,[data-nextjs-toast]{display:none!important}" }).catch(() => {});
await sleep(12000);
await page.screenshot({ path: `${OUT}/motion-start.png` });
await page.getByRole("button", { name: "Open game" }).first().dispatchEvent("click"); await sleep(2500);
await page.getByRole("tab", { name: "League" }).first().dispatchEvent("click"); await sleep(1500);
await page.screenshot({ path: `${OUT}/motion-league.png` });
await page.getByRole("tab", { name: "Scores" }).first().dispatchEvent("click"); await sleep(250);
await page.screenshot({ path: `${OUT}/motion-scores-early.png` });
await sleep(1500);
await page.screenshot({ path: `${OUT}/motion-scores-final.png` });
console.log("scrollWidth", await page.evaluate(() => document.documentElement.scrollWidth));
await browser.close();
