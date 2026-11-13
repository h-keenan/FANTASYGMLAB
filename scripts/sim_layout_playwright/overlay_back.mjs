// One-pop-up-at-a-time + back-stack check in a real browser (manual tool, not part of CI).
// Mocks /v1/sim/games against `next dev -p 3187` (web-next/.env.local with dummy Supabase vars). Checks that
//  1. browser Back closes a pop-up without leaving or reloading the page,
//  2. a player card opened from the trade picker REPLACES it (picker hidden, not stacked behind), shows "Back to ...",
//     and Back returns to the picker with its selection intact,
//  3. the X closes everything and leaves history as it was.
// Usage: CHROME_PATH=/path/to/chrome node overlay_back.mjs   (exit 1 on any failure)
import { chromium } from "playwright-core";
import { createMock } from "./simmock.mjs";

const session = {
  access_token: "a.b.c", refresh_token: "r", token_type: "bearer", expires_in: 99999, expires_at: Math.floor(Date.now() / 1000) + 99999,
  user: { id: "u1", aud: "authenticated", role: "authenticated", email: "t@example.com", app_metadata: {}, user_metadata: {}, created_at: "2026-01-01T00:00:00Z" },
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH });
let failed = 0;
const check = (name, ok, extra = "") => { console.log(`${ok ? "PASS" : "FAIL"} ${name}${extra ? " (" + extra + ")" : ""}`); if (!ok) failed++; };

async function newPage(opts) {
  const mock = createMock({ synthetic: true, ...opts });
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 });
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
  await page.goto("http://localhost:3187/gm-game", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: /Open game/ }).first().click({ timeout: 30000 });
  await sleep(2000);
  await page.evaluate(() => { window.__marker = "still-here"; });
  return { page, ctx };
}
async function openPicker(page) {
  if (process.env.SHOT) await page.screenshot({ path: process.env.SHOT });
  await page.getByTestId("sim-game-orb").click(); await sleep(700);
  await page.getByTestId("sim-game-nav").getByText("Trades").first().click(); await sleep(1000);
  await page.getByRole("tab", { name: "Make an offer", exact: false }).first().click(); await sleep(1200);
  await page.getByRole("button", { name: /Trade with Red Zone Rats/ }).first().click(); await sleep(1200);
  await page.getByText("Add from your roster").first().click(); await sleep(1200);
}
const dialogs = (page) => page.locator('[role="dialog"]:visible').count();

{ // 1. browser back closes a pop-up, same page, no reload
  const { page, ctx } = await newPage({ status: "drafting", pickStart: 14 });
  const before = page.url();
  await page.getByRole("button", { name: /Open player details/ }).first().click();
  await page.waitForSelector('[role="dialog"]');
  await sleep(500);
  await page.goBack();
  await sleep(800);
  check("browser back closes the pop-up", (await dialogs(page)) === 0);
  check("...without leaving or reloading the page", page.url() === before && (await page.evaluate(() => window.__marker)) === "still-here");
  await ctx.close();
}
{ // 2. replace, Back label, selection survives
  const { page, ctx } = await newPage({ status: "in_season", week: 4 });
  await openPicker(page);
  await page.getByRole("checkbox").nth(0).click(); await sleep(300);
  await page.getByRole("button", { name: /Open player details/ }).nth(1).click(); await sleep(1200);
  if (process.env.SHOT_CARD) await page.screenshot({ path: process.env.SHOT_CARD });
  const visible = await dialogs(page);
  check("card opened from the picker is the only visible pop-up", visible === 1, `visible=${visible}`);
  const back = page.getByTestId("overlay-back");
  check("card shows ‹ Back to the picker", (await back.count()) === 1 && /Back to/.test(await back.first().innerText()));
  await back.first().click(); await sleep(600);
  check("Back returns to the picker", (await page.getByTestId("trade-picker").isVisible()));
  check("...with its selection intact", (await page.getByRole("checkbox", { checked: true }).count()) === 1);
  await page.getByRole("button", { name: /Open player details/ }).nth(1).click(); await sleep(1000);
  await page.goBack(); await sleep(800);
  check("browser back from the card also returns to the picker", (await page.getByTestId("trade-picker").isVisible()) && (await dialogs(page)) === 1);
  await ctx.close();
}
{ // 3. X closes everything
  const { page, ctx } = await newPage({ status: "in_season", week: 4 });
  await openPicker(page);
  await page.getByRole("button", { name: /Open player details/ }).nth(1).click(); await sleep(1200);
  await page.getByRole("button", { name: /^Close / }).last().click(); await sleep(800);
  check("the X closes everything and returns to the page", (await dialogs(page)) === 0 && (await page.locator("[data-testid=trade-picker]").count()) === 0);
  await ctx.close();
}
await browser.close();
process.exit(failed ? 1 : 0);
