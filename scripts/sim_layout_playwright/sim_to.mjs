// 390px screenshots of the Fantasy Sim "Sim to..." chooser, its progress and the result summary (stop reason + fix + undo).
//   PW_CORE=... BASE=http://localhost:3197 OUT=/tmp/shots node scripts/sim_layout_playwright/sim_to.mjs
import fs from "fs";
import { createMock } from "./simmock.mjs";

const { chromium } = await import(process.env.PW_CORE || "playwright-core");
const BASE = process.env.BASE || "http://localhost:3197";
const OUT = process.env.OUT || "/private/tmp/claude-501/st-shots";
fs.mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.HOME + "/Library/Caches/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-mac-arm64/chrome-headless-shell" });
const session = { access_token: "a.b.c", refresh_token: "r", token_type: "bearer", expires_in: 99999, expires_at: Math.floor(Date.now() / 1000) + 99999, user: { id: "u1", aud: "authenticated", role: "authenticated", email: "t@example.com", app_metadata: {}, user_metadata: {}, created_at: "2026-01-01T00:00:00Z" } };
const J = (b) => ({ status: 200, contentType: "application/json", body: JSON.stringify(b), headers: { "access-control-allow-origin": "*" } });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const mock = createMock({ status: "in_season", week: 3 });
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
await ctx.addInitScript(([s]) => { try { localStorage.setItem("fgl:theme-mode", "dark"); localStorage.setItem("sb-dummy-auth-token", JSON.stringify(s)); localStorage.setItem("fgl:onboarding-complete", "1"); } catch (e) {} }, [session]);
const calls = [];
await ctx.route("**/*", async (route) => {
  const url = new URL(route.request().url());
  if (url.hostname === "localhost" && url.port === "8000") {
    const body = route.request().postData(); let json = null; try { json = body ? JSON.parse(body) : null; } catch {}
    if (url.pathname.includes("/sim-to") || url.pathname.includes("/advance")) calls.push(`${route.request().method()} ${url.pathname.split("/games/")[1]}`);
    if (url.pathname.endsWith("/sim-to") ) await sleep(900); // so the progress line can be captured
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
await page.getByRole("button", { name: "Open game" }).first().click(); await sleep(2500);
await page.screenshot({ path: `${OUT}/1-bar.png` });
await page.getByTestId("sim-to-button").click(); await sleep(1200);
await page.screenshot({ path: `${OUT}/2-chooser.png` });
await page.getByRole("button", { name: "Trade deadline (week 10)" }).click(); await sleep(350);
await page.screenshot({ path: `${OUT}/3-progress.png` });
await sleep(1800);
for (let i = 0; i < 3; i++) { await page.evaluate((y) => window.scrollTo(0, y), i * 700); await sleep(300); await page.screenshot({ path: `${OUT}/4-result-${i}.png` }); }
console.log(calls.join("\n"));
await browser.close();
