// Fantasy Sim Trades builder with the shared sheet picker. node simshots.mjs [outDir]
import { chromium } from "playwright-core";
import fs from "fs";
import { createMock } from "../sim_layout_playwright/simmock.mjs";

const OUT = process.argv[2] || "/private/tmp/claude-501/tsp-shots";
fs.mkdirSync(OUT, { recursive: true });
const exe = process.env.PW_CHROME || process.env.HOME + "/Library/Caches/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-mac-arm64/chrome-headless-shell";
const browser = await chromium.launch({ executablePath: exe });
const session = { access_token: "a.b.c", refresh_token: "r", token_type: "bearer", expires_in: 99999, expires_at: Math.floor(Date.now() / 1000) + 99999, user: { id: "u1", aud: "authenticated", role: "authenticated", email: "t@example.com", app_metadata: {}, user_metadata: {}, created_at: "2026-01-01T00:00:00Z" } };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let failed = 0;
for (const w of [390, 1280]) {
  const mock = createMock({ status: "in_season", week: 4 });
  const touch = w < 600;
  const ctx = await browser.newContext({ viewport: { width: w, height: w === 390 ? 844 : 900 }, hasTouch: touch, isMobile: touch, deviceScaleFactor: 2 });
  await ctx.addInitScript(([s]) => { try { localStorage.setItem("fgl:theme-mode", "dark"); localStorage.setItem("sb-dummy-auth-token", JSON.stringify(s)); localStorage.setItem("fgl:onboarding-complete", "1"); } catch (e) {} }, [session]);
  await ctx.route("**/*", async (route) => {
    const u = new URL(route.request().url());
    const cors = { "access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "*" };
    if (u.hostname === "localhost" && u.port === "8000") {
      if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
      const raw = route.request().postData(); let json = null; try { json = raw ? JSON.parse(raw) : null; } catch {}
      const res = mock(route.request().method(), u.pathname, Object.fromEntries(u.searchParams), json);
      return route.fulfill({ status: res?.status ?? 200, contentType: "application/json", body: JSON.stringify(res?.body ?? {}), headers: cors });
    }
    if (u.hostname === "dummy.supabase.co") return route.fulfill({ status: 200, contentType: "application/json", body: "{}", headers: cors });
    return route.continue();
  });
  const page = await ctx.newPage();
  page.on("pageerror", (e) => { console.log("PAGEERR", e.message); failed++; });
  const tap = async (loc) => { await loc.scrollIntoViewIfNeeded(); if (touch) { const b = await loc.boundingBox(); await page.touchscreen.tap(b.x + b.width / 2, b.y + b.height / 2); } else await loc.click(); await sleep(500); };
  await page.goto("http://localhost:3187/gm-game", { waitUntil: "domcontentloaded" });
  await page.addStyleTag({ content: "nextjs-portal,[data-nextjs-toast]{display:none!important}" }).catch(() => {});
  await page.waitForSelector("main", { timeout: 30000 }).catch(() => {});
  await sleep(4000);
  await page.screenshot({ path: `${OUT}/sim-debug-${w}.png` });
  await sleep(1500);
  await tap(page.getByRole("button", { name: "Open game" }).first());
  await sleep(1500);
  await tap(page.getByRole("tab", { name: "Trades" }).first());
  await tap(page.getByRole("tab", { name: "Make an offer" }).first());
  await sleep(1000);
  await tap(page.getByRole("button", { name: /Trade with Red Zone Rats/ }).first());
  await sleep(1000);
  await page.screenshot({ path: `${OUT}/sim-0-builder-${w}.png` });
  await tap(page.getByRole("button", { name: /^You send/ }).first());
  const dialog = page.getByRole("dialog");
  await page.screenshot({ path: `${OUT}/sim-1-sheet-${w}.png` });
  const rows = dialog.locator(".tps-row-main");
  await tap(rows.nth(0)); await tap(rows.nth(1));
  await tap(dialog.getByRole("button", { name: /^Add 2 to trade/ }));
  await tap(page.getByRole("button", { name: /^You receive/ }).first());
  await tap(page.getByRole("dialog").locator(".tps-row-main").nth(0));
  await tap(page.getByRole("dialog").getByRole("button", { name: /^Add 1 to trade/ }));
  await sleep(1500);
  const chips = await page.locator("[data-testid=trade-side-give] .tps-chip, [data-testid=trade-side-get] .tps-chip").count();
  console.log(w, "chips on page:", chips, "verdict:", await page.getByTestId("trade-verdict").count());
  if (chips !== 3) failed++;
  await page.screenshot({ path: `${OUT}/sim-2-summary-${w}.png`, fullPage: true });
  await ctx.close();
}
await browser.close();
process.exit(failed ? 1 : 0);
