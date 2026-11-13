// Touch swipe-to-dismiss check for the web sheets (manual tool, not part of CI).
// Mocks /v1/sim/games against `next dev -p 3187` (web-next/.env.local with dummy Supabase vars), opens a player
// sheet on the draft board, and drags it with real CDP touch events: from the handle, from the header area, and a
// short drag that must spring back. Prints PASS/FAIL per case and exits 1 on any failure.
// Usage: CHROME_PATH=/path/to/chrome node sheet_drag.mjs   (or: BROWSER=webkit node sheet_drag.mjs)
import { chromium, webkit } from "playwright-core";
import { createMock } from "./simmock.mjs";

const session = {
  access_token: "a.b.c", refresh_token: "r", token_type: "bearer", expires_in: 99999, expires_at: Math.floor(Date.now() / 1000) + 99999,
  user: { id: "u1", aud: "authenticated", role: "authenticated", email: "t@example.com", app_metadata: {}, user_metadata: {}, created_at: "2026-01-01T00:00:00Z" },
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
// BROWSER=webkit runs Playwright's WebKit; it has no CDP, so touches are dispatched as real TouchEvents in the page.
const isWebkit = process.env.BROWSER === "webkit";
const browser = isWebkit ? await webkit.launch() : await chromium.launch({ executablePath: process.env.CHROME_PATH });
let failed = 0;

async function touchDrag(cdp, x, y0, y1, steps = 8, stepMs = 16, page = null) {
  if (isWebkit) {
    await page.evaluate(async ({ x, y0, y1, steps, stepMs }) => {
      const target = document.elementFromPoint(x, y0);
      const mk = (type, y, list = true) => {
        const t = new Touch({ identifier: 1, target, clientX: x, clientY: y, pageX: x, pageY: y });
        return new TouchEvent(type, { bubbles: true, cancelable: true, touches: list ? [t] : [], targetTouches: list ? [t] : [], changedTouches: [t] });
      };
      target.dispatchEvent(mk("touchstart", y0));
      for (let i = 1; i <= steps; i++) {
        target.dispatchEvent(mk("touchmove", y0 + ((y1 - y0) * i) / steps));
        await new Promise((r) => setTimeout(r, stepMs));
      }
      target.dispatchEvent(mk("touchend", y1, false));
    }, { x, y0, y1, steps, stepMs });
    return;
  }
  await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x, y: y0 }] });
  for (let i = 1; i <= steps; i++) {
    await cdp.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: [{ x, y: y0 + ((y1 - y0) * i) / steps }] });
    await sleep(stepMs);
  }
  await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
}

async function run(name, startSelector, distance, scenario = "draft") {
  const mock = scenario === "claim" ? createMock({ status: "in_season", week: 4, synthetic: true }) : createMock({ status: "drafting", pickStart: 14, synthetic: true });
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true, deviceScaleFactor: 1 });
  await ctx.addInitScript(([t, s]) => { try { localStorage.setItem("fgl:theme-mode", t); localStorage.setItem("sb-dummy-auth-token", JSON.stringify(s)); localStorage.setItem("fgl:onboarding-complete", "1"); } catch (e) {} }, ["dark", session]);
  await ctx.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.hostname === "localhost" && url.port === "8000") {
      const body = route.request().postData();
      let json = null; try { json = body ? JSON.parse(body) : null; } catch {}
      const res = mock(route.request().method(), url.pathname, Object.fromEntries(url.searchParams.entries()), json);
      return route.fulfill({ status: res?.status ?? 200, contentType: "application/json", body: JSON.stringify(res?.body ?? {}), headers: { "access-control-allow-origin": "*" } });
    }
    if (url.hostname === "dummy.supabase.co") return route.fulfill({ status: 200, contentType: "application/json", body: "{}", headers: { "access-control-allow-origin": "*" } });
    return route.continue();
  });
  const page = await ctx.newPage();
  page.on("pageerror", (e) => console.log("PAGEERR", e.message.slice(0, 200)));
  await page.goto("http://localhost:3187/gm-game", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: /Open game/ }).first().click({ timeout: 30000 });
  await sleep(2000);
  if (scenario === "claim") {
    // The claim sheet is a SimSheet (hand-built shell): Players tab, Waivers, Claim.
    await page.getByRole("tab", { name: /Players/ }).first().tap();
    await sleep(900);
    await page.getByRole("tab", { name: /Waivers/ }).first().tap();
    await sleep(1200);
    await page.getByRole("button", { name: /^Add / }).first().tap();
  } else {
    await page.getByRole("button", { name: /Open player details/ }).first().tap();
  }
  await page.waitForSelector('[role="dialog"]', { timeout: 15000 });
  await sleep(600);
  if (process.env.SHOT) await page.screenshot({ path: process.env.SHOT });
  const box = await page.locator(startSelector).first().boundingBox({ timeout: 5000 });
  const cdp = isWebkit ? null : await ctx.newCDPSession(page);
  await touchDrag(cdp, box.x + box.width / 2, box.y + box.height / 2, box.y + box.height / 2 + distance, 8, 16, page);
  await sleep(700);
  const open = (await page.locator('[role="dialog"]').count()) > 0;
  const want = distance < 100 ? "open" : "closed";
  const got = open ? "open" : "closed";
  const ok = want === got;
  if (!ok) failed++;
  console.log(`${ok ? "PASS" : "FAIL"} ${name}: expected ${want}, got ${got}`);
  await ctx.close();
}

await run("drag from the handle past 100px closes", "[data-sheet-handle]", 260);
await run("drag from the top area (title row) past 100px closes", "[role=dialog] h2, [role=dialog] .pqv-scroll", 260);
await run("short 40px drag springs back", "[data-sheet-handle]", 40);
await run("claim sheet (SimSheet): drag from the handle past 100px closes", "[data-sheet-handle]", 260, "claim");
await run("claim sheet (SimSheet): short drag springs back", "[data-sheet-handle]", 40, "claim");
await browser.close();
process.exit(failed ? 1 : 0);
