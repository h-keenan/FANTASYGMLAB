// 390px screenshots of the Fantasy Sim trade block: inbox offer from the block, My block, League > Players > On the block, a team roster with block chips.
//   PW_CORE=... BASE=http://localhost:3197 OUT=/tmp/shots node scripts/sim_layout_playwright/block.mjs
import fs from "fs";
import { createMock } from "./simmock.mjs";

const { chromium } = await import(process.env.PW_CORE || "playwright-core");
const BASE = process.env.BASE || "http://localhost:3197";
const OUT = process.env.OUT || "/private/tmp/claude-501/tb-shots";
fs.mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.HOME + "/Library/Caches/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-mac-arm64/chrome-headless-shell" });
const session = { access_token: "a.b.c", refresh_token: "r", token_type: "bearer", expires_in: 99999, expires_at: Math.floor(Date.now() / 1000) + 99999, user: { id: "u1", aud: "authenticated", role: "authenticated", email: "t@example.com", app_metadata: {}, user_metadata: {}, created_at: "2026-01-01T00:00:00Z" } };
const J = (b) => ({ status: 200, contentType: "application/json", body: JSON.stringify(b), headers: { "access-control-allow-origin": "*" } });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const mock = createMock({ status: "in_season", week: 3 });
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
await ctx.addInitScript(([s]) => { try { localStorage.setItem("fgl:theme-mode", "dark"); localStorage.setItem("sb-dummy-auth-token", JSON.stringify(s)); localStorage.setItem("fgl:onboarding-complete", "1"); } catch (e) {} }, [session]);
await ctx.route("**/*", async (route) => {
  const url = new URL(route.request().url());
  if (url.hostname === "localhost" && url.port === "8000") {
    const body = route.request().postData(); let json = null; try { json = body ? JSON.parse(body) : null; } catch {}
    const res = mock(route.request().method(), url.pathname, Object.fromEntries(url.searchParams.entries()), json);
    if (res) return route.fulfill({ status: res.status, contentType: "application/json", body: JSON.stringify(res.body), headers: { "access-control-allow-origin": "*" } });
    return route.fulfill(J({ ok: true, status: "unavailable", points: [], items: [], history: null }));
  }
  if (url.hostname === "dummy.supabase.co") return route.fulfill(J({}));
  return route.continue();
});
const page = await ctx.newPage();
page.on("pageerror", (e) => console.log("PAGEERR", e.message));
page.on("console", (m) => { if (m.type() === "error" && !/Failed to load resource|net::ERR/.test(m.text())) console.log("CONSOLE", m.text().slice(0, 300)); });
await page.goto(`${BASE}/gm-game`, { waitUntil: "domcontentloaded" });
await page.waitForSelector("main", { timeout: 60000 }).catch(() => {}); await sleep(2500);
await page.screenshot({ path: `${OUT}/0-hub.png` });
await page.getByText("Continue", { exact: true }).first().click(); await sleep(2500);
const tab = async (name, exact = false) => { await page.getByRole("tab", { name, exact }).first().click(); await sleep(1300); };
// Phones navigate with the game orb (the page tabs render from md up).
const go = async (name) => { await page.getByTestId("sim-game-orb").click(); await sleep(700); await page.getByTestId("sim-game-nav").getByRole("button", { name: new RegExp("^" + name) }).click(); await sleep(1500); };
await go("Trades");
await page.screenshot({ path: `${OUT}/1-inbox-from-block.png` });
await tab("My block");
await page.getByRole("button", { name: /^Put .* on the block$/ }).first().click(); await sleep(900);
await page.getByRole("button", { name: /^Put .* on the block$/ }).first().click(); await sleep(900);
await page.getByRole("tab", { name: "RB", exact: true }).first().click().catch(() => {}); await sleep(800);
await page.screenshot({ path: `${OUT}/2-my-block-0.png` });
await page.evaluate(() => window.scrollTo(0, 800)); await sleep(400);
await page.screenshot({ path: `${OUT}/2-my-block-1.png` });
await page.evaluate(() => window.scrollTo(0, 1700)); await sleep(400);
await page.screenshot({ path: `${OUT}/2-my-block-2.png` });
await page.evaluate(() => window.scrollTo(0, 0));
await go("League");
await page.getByRole("tab", { name: "Players", exact: true }).last().click(); await sleep(1300);
await page.getByRole("tab", { name: /On the block/ }).click(); await sleep(900);
await page.screenshot({ path: `${OUT}/3-league-on-the-block.png` });
await page.getByRole("tab", { name: "Teams", exact: true }).first().click(); await sleep(1200);
await page.getByRole("button", { name: /Open roster/ }).nth(0).click(); await sleep(1500);
await page.getByRole("dialog").getByRole("tab", { name: "Roster" }).click(); await sleep(1200);
await page.screenshot({ path: `${OUT}/4-team-roster-chips.png` });
await browser.close();
