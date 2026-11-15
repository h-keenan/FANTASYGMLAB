// Real-touch (CDP) check of the weekly recap story at 390px: swipe down ALWAYS closes the whole queued recap flow, never
// advances to the next recap; the forgiving story profile (sloppy diagonal pulls dismiss, jitter and sideways swipes do
// not); the toast / notice presence (shots). Manual tool, not part of CI.
// Mocks /v1/sim/games against `next dev -p 3187` (web-next/.env.local with dummy Supabase vars and
// NEXT_PUBLIC_API_BASE_URL=http://localhost:8000). The advance response is padded with 2 `also_played` recaps so the flow has 3.
//   PW_CORE=/path/to/playwright-core/index.mjs BASE=http://localhost:3187 OUT=/tmp/shots node scripts/sim_layout_playwright/story_swipe.mjs
import fs from "fs";
import { createMock } from "./simmock.mjs";

const { chromium } = await import(process.env.PW_CORE || "playwright-core");
const BASE = process.env.BASE || "http://localhost:3187";
const OUT = process.env.OUT || "/private/tmp/claude-501/story-swipe-shots";
fs.mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || process.env.HOME + "/Library/Caches/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-mac-arm64/chrome-headless-shell" });
const session = { access_token: "a.b.c", refresh_token: "r", token_type: "bearer", expires_in: 99999, expires_at: Math.floor(Date.now() / 1000) + 99999, user: { id: "u1", aud: "authenticated", role: "authenticated", email: "t@example.com", app_metadata: {}, user_metadata: {}, created_at: "2026-01-01T00:00:00Z" } };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let failed = 0;

/** A finger path as [dx, dy, ms] steps from (x0, y0): real CDP touches, with the delays between moves. */
async function touch(cdp, x0, y0, path, { hold = 0 } = {}) {
  await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x: x0, y: y0 }] });
  for (const [dx, dy, ms] of path) {
    await cdp.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: [{ x: x0 + dx, y: y0 + dy }] });
    await sleep(ms);
  }
  if (hold) await sleep(hold);
  return () => cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
}
/** `n` steps to (dx, dy) over `ms` with x/y jitter (deterministic). */
function drag(dx, dy, ms, jitter = 0, n = 14) {
  let seed = 7;
  const rnd = () => ((seed = (seed * 1664525 + 1013904223) >>> 0) / 4294967296 - 0.5) * 2;
  return Array.from({ length: n }, (_, i) => {
    const p = (i + 1) / n;
    return [Math.round(dx * p + rnd() * jitter), Math.round(dy * p + rnd() * jitter), Math.round(ms / n)];
  });
}

async function scenario(name, run) {
  const mock = createMock({ status: "in_season", week: 4, pro: true });
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true, deviceScaleFactor: 2 });
  await ctx.addInitScript(([s]) => { try { localStorage.setItem("fgl:theme-mode", "dark"); localStorage.setItem("sb-dummy-auth-token", JSON.stringify(s)); localStorage.setItem("fgl:onboarding-complete", "1"); } catch (e) {} }, [session]);
  await ctx.route("**/*", async (route) => {
    const u = new URL(route.request().url());
    const cors = { "access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "*" };
    if (u.hostname === "localhost" && u.port === "8000") {
      if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
      const raw = route.request().postData(); let json = null; try { json = raw ? JSON.parse(raw) : null; } catch {}
      const res = u.pathname.startsWith("/v1/sim") ? mock(route.request().method(), u.pathname, Object.fromEntries(u.searchParams), json) : { status: 404, body: {} };
      if (u.pathname.endsWith("/advance") && res?.body?.recap) {
        const base = res.body.recap;
        res.body.recap.scores = [[0, 1, 102, 95.2], [2, 3, 110.4, 101], [4, 5, 140.7, 68.9]].map(([a, b, x, y]) => ({ home: String(a + 1), away: String(b + 1), home_pts: x, away_pts: y, winner: String(x > y ? a + 1 : b + 1) }));
        res.body.recap.standings = ["Gridiron Goats", "Blitz Brigade", "Hail Marys", "Bench Mob", "Flex Appeal", "Boom or Bust"].map((n, i) => ({ rank: i + 1, team_id: String(i + 1), name: n, is_you: false, wins: 3, losses: 1, ties: 0, pf: 400, pa: 380 }));
        res.body.also_played = [1, 2].map((k) => ({ ...JSON.parse(JSON.stringify(res.body.recap)), week: base.week + k }));
      }
      return route.fulfill({ status: res?.status ?? 200, contentType: "application/json", body: JSON.stringify(res?.body ?? {}), headers: cors });
    }
    if (u.hostname === "dummy.supabase.co") return route.fulfill({ status: 200, contentType: "application/json", body: "{}", headers: cors });
    return route.continue();
  });
  const page = await ctx.newPage();
  page.on("pageerror", (e) => console.log("PAGEERR", e.message.slice(0, 160)));
  await page.goto(`${BASE}/gm-game`, { waitUntil: "domcontentloaded", timeout: 180000 });
  await page.addStyleTag({ content: "nextjs-portal,[data-nextjs-toast]{display:none!important}" }).catch(() => {});
  await page.getByRole("button", { name: /Open game/ }).first().dispatchEvent("click");
  await sleep(2500);
  await page.getByRole("button", { name: /Advance/ }).last().dispatchEvent("click");
  // An empty / bye starter asks to confirm first ("Advance to week N" in the confirm prompt): take it when it shows.
  for (let i = 0; i < 20; i++) {
    await sleep(500);
    if (await page.locator('[data-testid="week-recap-story"]').count()) break;
    const again = page.getByRole("button", { name: /^Advance to week|Advance anyway|Sim anyway/ });
    if (await again.count()) { await again.last().dispatchEvent("click"); await sleep(1500); }
  }
  try {
    await page.waitForSelector('[data-testid="week-recap-story"]', { timeout: 30000 });
  } catch (error) {
    await page.screenshot({ path: `${OUT}/debug-no-story.png` });
    console.log("buttons:", (await page.getByRole("button").allInnerTexts()).slice(0, 30).join(" | "));
    throw error;
  }
  await sleep(600);
  const cdp = await ctx.newCDPSession(page);
  const api = {
    page,
    cdp,
    shot: (file) => page.screenshot({ path: `${OUT}/${file}.png` }),
    open: async () => (await page.locator('[data-testid="week-recap-story"]').count()) > 0,
    title: async () => (await page.locator('[data-testid="week-recap-story"]').getAttribute("aria-label")),
    pageNo: async () => Number(await page.locator('[role="progressbar"]').first().getAttribute("aria-valuenow")),
  };
  const ok = await run(api);
  if (!ok) failed++;
  console.log(`${ok ? "PASS" : "FAIL"} ${name}`);
  await ctx.close();
}

const X = 195;
await scenario("sloppy diagonal swipe down (drift 70px, jitter) closes the WHOLE flow, not the next recap", async ({ cdp, page, open, shot }) => {
  const end = await touch(cdp, X - 30, 300, drag(70, 230, 800, 6), { hold: 0 });
  await shot("story-swipe-mid-drag");
  await end();
  await sleep(1200);
  const stillOpen = await open();
  await shot("story-swipe-after-dismiss");
  return !stillOpen;
});
await scenario("a 260ms flick down closes the whole flow", async ({ cdp, open }) => {
  const end = await touch(cdp, X, 300, drag(4, 120, 160, 2, 8));
  await end();
  await sleep(1200);
  return !(await open());
});
await scenario("accidental 14px jitter does not close or advance", async ({ cdp, open, title, pageNo }) => {
  const before = await title();
  const end = await touch(cdp, X, 300, drag(5, 14, 200, 3, 6));
  await end();
  await sleep(800);
  return (await open()) && (await title()) === before && (await pageNo()) === 1;
});
await scenario("horizontal swipe turns the page, never closes", async ({ cdp, open, pageNo, shot }) => {
  const end = await touch(cdp, 300, 420, drag(-170, 28, 220, 3, 10));
  await end();
  await sleep(700);
  await shot("story-swipe-horizontal-page2");
  return (await open()) && (await pageNo()) === 2;
});
await scenario("Next round advances to the next queued recap (X then closes everything)", async ({ page, open, title, shot }) => {
  const first = await title();
  for (let i = 0; i < 5; i++) { await page.keyboard.press("ArrowRight"); await sleep(250); }
  await page.getByRole("button", { name: "Next round" }).click();
  await sleep(1200);
  const second = await title();
  await shot("story-next-recap");
  if (!(await open()) || second === first) return false;
  await page.getByRole("button", { name: /^Close / }).click();
  await sleep(900);
  return !(await open());
});
await scenario("swipe down on the SECOND queued recap still closes the whole flow", async ({ page, cdp, open, title }) => {
  const first = await title();
  for (let i = 0; i < 5; i++) { await page.keyboard.press("ArrowRight"); await sleep(250); }
  await page.getByRole("button", { name: "Next round" }).click();
  await sleep(1200);
  if ((await title()) === first) return false;
  const end = await touch(cdp, X, 300, drag(20, 200, 600, 4));
  await end();
  await sleep(1300);
  return !(await open());
});
await browser.close();
process.exit(failed ? 1 : 0);
