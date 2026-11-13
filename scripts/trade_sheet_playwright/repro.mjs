// Counts the taps needed to add players to a 2-team trade at a phone viewport with real touch.
// Usage: node repro.mjs [shotsDir] [label]   (dev server on :3187, mocked API)
import { chromium } from "playwright-core";
import fs from "fs";
import { createTradeMock, LEAGUE } from "./tradeMock.mjs";

const OUT = process.argv[2] || "/private/tmp/claude-501/tsp-shots";
const LABEL = process.argv[3] || "run";
fs.mkdirSync(OUT, { recursive: true });
const exe = process.env.PW_CHROME || process.env.HOME + "/Library/Caches/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-mac-arm64/chrome-headless-shell";
const browser = await chromium.launch({ executablePath: exe });
const session = { access_token: "a.b.c", refresh_token: "r", token_type: "bearer", expires_in: 99999, expires_at: Math.floor(Date.now() / 1000) + 99999, user: { id: "u1", aud: "authenticated", role: "authenticated", email: "t@example.com", app_metadata: {}, user_metadata: {}, created_at: "2026-01-01T00:00:00Z" } };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export async function openPage(w, h, { touch = true, theme = "dark", url, ready = "text=You send" } = {}) {
  const mock = createTradeMock();
  const ctx = await browser.newContext({ viewport: { width: w, height: h }, hasTouch: touch, isMobile: touch && w < 600, deviceScaleFactor: 2 });
  await ctx.addInitScript(([t, s]) => { try { localStorage.setItem("fgl:theme-mode", t); localStorage.setItem("sb-dummy-auth-token", JSON.stringify(s)); localStorage.setItem("fgl:onboarding-complete", "1"); } catch (e) {} }, [theme, session]);
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
  page.errors = [];
  page.__touch = touch;
  page.on("pageerror", (e) => page.errors.push(e.message));
  await page.goto(url ?? `http://localhost:${process.env.PORT || 3187}/trade-analyzer/${LEAGUE}?name=Mock%20League`, { waitUntil: "domcontentloaded" });
  await page.addStyleTag({ content: "nextjs-portal,[data-nextjs-toast]{display:none!important}" }).catch(() => {});
  await page.waitForSelector(ready, { timeout: 60000 });
  await sleep(1200);
  return { page, ctx, mock };
}

// A "tap" is a real touchscreen tap at the center of the target element (as a finger would), so anything that
// moves under the finger or overlays the target makes it miss, exactly like on a phone.
export async function tapAt(page, locator) {
  await locator.scrollIntoViewIfNeeded();
  const box = await locator.boundingBox();
  if (!box) throw new Error("no box");
  if (page.__touch === false) await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
  else await page.touchscreen.tap(box.x + box.width / 2, box.y + box.height / 2);
  await sleep(350);
}

if (process.argv[1].endsWith("repro.mjs")) {
  const { page, ctx } = await openPage(390, 844);
  let taps = 0;
  const T = async (loc, why) => { taps++; await tapAt(page, loc); console.log(`  tap ${taps}: ${why}`); };
  // Scenario: user wants to ADD to "You receive" (the other team's side), from a fresh page.
  console.log(`[${LABEL}] scenario A: add one player to You receive`);
  await page.screenshot({ path: `${OUT}/${LABEL}-0-start-390.png` });
  const before = await page.evaluate(() => document.documentElement.scrollHeight);
  await T(page.getByRole("button", { name: "You receive" }).first(), "tap 'You receive'");
  await page.screenshot({ path: `${OUT}/${LABEL}-1-after-side-tap-390.png` });
  const rows = page.locator("button:has-text('Jaxon')");
  console.log("  list rows visible after side tap:", await page.locator("button[aria-label], button").filter({ hasText: /Jaxon|Devin|Malik/ }).count());
  console.log("  page height", before);
  await page.screenshot({ path: `${OUT}/${LABEL}-2-390-full.png`, fullPage: true });
  await ctx.close();
  await browser.close();
}
