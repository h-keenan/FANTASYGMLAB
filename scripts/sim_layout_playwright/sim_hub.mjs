// 390px screenshots + geometry of the Fantasy Sim hub: first-timer, returning (saved list), New game sheet.
//   PW_CORE=.../playwright-core/index.mjs BASE=http://localhost:3197 OUT=/tmp/hub node scripts/sim_layout_playwright/sim_hub.mjs
import fs from "fs";
import { createMock } from "./simmock.mjs";

const { chromium } = await import(process.env.PW_CORE || "playwright-core");
const BASE = process.env.BASE || "http://localhost:3197";
const OUT = process.env.OUT || "/private/tmp/claude-501/hub-shots";
fs.mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.HOME + "/Library/Caches/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-mac-arm64/chrome-headless-shell" });
const session = { access_token: "a.b.c", refresh_token: "r", token_type: "bearer", expires_in: 99999, expires_at: Math.floor(Date.now() / 1000) + 99999, user: { id: "u1", aud: "authenticated", role: "authenticated", email: "t@example.com", app_metadata: {}, user_metadata: {}, created_at: "2026-01-01T00:00:00Z" } };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let failed = 0;

async function scenario(name, mockOpts, steps) {
  const mock = createMock(mockOpts);
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true, deviceScaleFactor: 2 });
  await ctx.addInitScript(([s]) => { try { localStorage.setItem("fgl:theme-mode", "dark"); localStorage.setItem("sb-dummy-auth-token", JSON.stringify(s)); localStorage.setItem("fgl:onboarding-complete", "1"); } catch (e) {} }, [session]);
  await ctx.route("**/*", async (route) => {
    const u = new URL(route.request().url());
    const cors = { "access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "*" };
    if (u.hostname === "localhost" && u.port === "8000") {
      if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
      const raw = route.request().postData(); let json = null; try { json = raw ? JSON.parse(raw) : null; } catch {}
      if (u.pathname.endsWith("/notifications")) return route.fulfill({ status: 200, contentType: "application/json", headers: cors, body: JSON.stringify({ ok: true, reason: "", seq: 9, unread: 0, items: [] }) });
      const res = u.pathname.startsWith("/v1/sim") ? mock(route.request().method(), u.pathname, Object.fromEntries(u.searchParams), json) : { status: 404, body: {} };
      return route.fulfill({ status: res?.status ?? 200, contentType: "application/json", body: JSON.stringify(res?.body ?? {}), headers: cors });
    }
    if (u.hostname === "dummy.supabase.co") return route.fulfill({ status: 200, contentType: "application/json", body: "{}", headers: cors });
    return route.continue();
  });
  const page = await ctx.newPage();
  page.on("pageerror", (e) => console.log("PAGEERR", e.message));
  await page.goto(`${BASE}/gm-game`, { waitUntil: "domcontentloaded" });
  await page.addStyleTag({ content: "nextjs-portal,[data-nextjs-toast]{display:none!important}" }).catch(() => {});
  await page.getByRole("button", { name: "New game" }).waitFor({ timeout: 90000 }).catch(() => {});
  await sleep(1500);
  const geo = async (label) => {
    const g = await page.evaluate(() => {
      const bad = [];
      for (const el of document.querySelectorAll("main *, [role=dialog] *")) {
        const r = el.getBoundingClientRect();
        if (r.width && (r.right > innerWidth + 1 || r.left < -1)) bad.push(`${el.tagName}.${String(el.className).slice(0, 30)}`);
      }
      const names = [...document.querySelectorAll("[data-player-name], main h2, main h3")].map((e) => e.textContent);
      return { scrollWidth: document.documentElement.scrollWidth, innerWidth, overflow: bad.slice(0, 5), height: document.documentElement.scrollHeight, ellipsis: [...document.querySelectorAll("main *")].filter((e) => getComputedStyle(e).textOverflow === "ellipsis" && e.scrollWidth > e.clientWidth).length, names };
    });
    console.log(label.padEnd(18), JSON.stringify(g));
    if (g.scrollWidth > g.innerWidth || g.overflow.length) failed++;
  };
  const shot = async (n) => { await sleep(500); await geo(n); await page.screenshot({ path: `${OUT}/${n}.png`, fullPage: true }); };
  try { await steps({ page, shot, sleep }); } catch (e) { failed++; console.log("FAIL", name, String(e).slice(0, 300)); }
  await ctx.close();
}

await scenario("first", { noGames: true, status: "in_season", week: 1 }, async ({ page, shot }) => {
  await shot("hub-first-timer");
  await page.getByRole("button", { name: "New game" }).dispatchEvent("click");
  await shot("hub-first-sheet");
});
await scenario("returning", { status: "in_season", week: 4 }, async ({ page, shot, sleep }) => {
  await shot("hub-returning");
  await page.getByRole("button", { name: /What is Fantasy Sim/ }).dispatchEvent("click"); await sleep(400);
  await shot("hub-returning-about-open");
  await page.getByRole("button", { name: "New game" }).dispatchEvent("click");
  await shot("hub-returning-sheet");
});
await scenario("finished", { status: "complete", week: 17 }, async ({ shot }) => { await shot("hub-finished"); });
await browser.close();
process.exit(failed ? 1 : 0);
