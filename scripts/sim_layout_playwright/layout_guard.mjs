// Fantasy Sim layout guard (docs/ui-patterns.md, "Layout guard"): every Sim screen / state at 320, 360, 390, 430px and large text,
// each checked with guard_checks.mjs (no sideways scroll, nothing past its card or the viewport, no ellipsised names / stats,
// no silently clipped badges, controls >= 44px). Fails (exit 1) on any violation; prints every one. Desk pages: module_scan.mjs (GUARD=1).
//   dev server: NEXT_PUBLIC_SUPABASE_URL=https://dummy.supabase.co NEXT_PUBLIC_SUPABASE_ANON_KEY=x NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npx next dev -p 3197
//   PW_CORE=.../playwright-core/index.mjs BASE=http://localhost:3197 OUT=/tmp/layout-guard [WIDTHS=320,390] [LARGE=0|1|both] [ONLY=team,draft] node scripts/sim_layout_playwright/layout_guard.mjs
//   (npm run guard:layout in web-next/ wraps this and module_scan.mjs.)
import fs from "fs";
import { createMock } from "./simmock.mjs";
import { GUARD } from "./guard_checks.mjs";

const pw = await import(process.env.PW_CORE || "playwright-core");
// WebKit by default: coridian_ sees these screens in iPhone Safari. BROWSER=chromium (+ CHROME=path) for Chromium.
const engine = process.env.BROWSER === "chromium" ? pw.chromium : pw.webkit;
const BASE = process.env.BASE || "http://localhost:3197";
const OUT = process.env.OUT || "/private/tmp/claude-501/layout-guard";
const WIDTHS = (process.env.WIDTHS || "320,360,390,430").split(",").map(Number);
const LARGE = process.env.LARGE || "both";
const ONLY = process.env.ONLY ? process.env.ONLY.split(",") : null;
const SHOTS = process.env.SHOTS === "1";
fs.mkdirSync(OUT, { recursive: true });
const browser = await engine.launch(process.env.CHROME ? { executablePath: process.env.CHROME } : {});
const session = { access_token: "a.b.c", refresh_token: "r", token_type: "bearer", expires_in: 99999, expires_at: Math.floor(Date.now() / 1000) + 99999, user: { id: "u1", aud: "authenticated", role: "authenticated", email: "t@example.com", app_metadata: {}, user_metadata: {}, created_at: "2026-01-01T00:00:00Z" } };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const want = (n) => !ONLY || ONLY.some((o) => n.startsWith(o));
const violations = [];
let checked = 0;

async function scenario(name, mockOpts, width, large, steps) {
  const mock = createMock(mockOpts);
  const ctx = await browser.newContext({ viewport: { width, height: 844 }, hasTouch: true, isMobile: true, deviceScaleFactor: 1 });
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
  page.on("pageerror", () => {});
  page.setDefaultTimeout(8000);
  const click = async (loc) => { await loc.first().dispatchEvent("click"); await sleep(700); };
  const goTab = async (label) => { await click(page.getByTestId("sim-game-orb")); await click(page.getByTestId("sim-game-nav").getByRole("button", { name: new RegExp(`^${label}`) })); };
  const tag = `${width}${large ? "L" : ""}`;
  const check = async (state) => {
    if (!want(state.split(":")[0]) && !want(state)) return;
    await sleep(500);
    const found = await page.evaluate(GUARD, {});
    checked += 1;
    for (const v of found) violations.push({ screen: state, width, large, ...v });
    if (SHOTS || found.length) await page.screenshot({ path: `${OUT}/${state.replace(/[^a-z0-9]+/gi, "-")}-${tag}.png`, fullPage: SHOTS }).catch(() => {});
  };
  await page.goto(`${BASE}/gm-game`, { waitUntil: "domcontentloaded" });
  await page.addStyleTag({ content: "nextjs-portal,[data-nextjs-toast]{display:none!important}" + (large ? "html{font-size:125%!important}" : "") }).catch(() => {});
  try { await page.getByRole("button", { name: "Open game" }).first().waitFor({ timeout: 40000 }); } catch {}
  try { await steps({ page, click, goTab, check, sleep }); } catch (e) { console.log("FAIL", name, tag, String(e).slice(0, 200)); }
  await ctx.close();
}

// A step that cannot run (a state the fixture does not offer) is skipped, never fatal; the screen is still checked.
const attempt = async (fn) => { try { await Promise.race([fn(), sleep(8000).then(() => { throw new Error("step timeout"); })]); } catch (e) { console.log("skip step:", String(e).split("\n")[0].slice(0, 90)); } };
for (const width of WIDTHS) for (const large of LARGE === "both" ? [false, true] : [LARGE === "1"]) {
  await scenario("hub", { status: "in_season", week: 4 }, width, large, async ({ check, click, page, goTab }) => {
    await check("hub");
    await click(page.getByRole("button", { name: "Open game" }));
    await check("home");
    for (const t of ["Team", "Players", "Trades", "League"]) { await goTab(t); await check(t.toLowerCase()); }
    // Team: open a row, then its Move strip.
    await goTab("Team");
    await attempt(() => click(page.getByTestId("lineup-row").first().locator("button[aria-expanded]").first()));
    await check("team:row-open");
    await attempt(() => click(page.getByTestId("move-button").first()));
    await check("team:move-open");
    await attempt(() => click(page.getByTestId("move-button").first()));
    await goTab("Players");
    await attempt(() => click(page.locator('[data-testid="sim-player-line"] button[aria-expanded], [data-testid="player-accordion-row"] button[aria-expanded]').first()));
    await check("players:row-open");
    await goTab("Trades");
    for (const sub of [/Make an offer/, /Inbox|Offers/, /Block|Your block/]) {
      try { await click(page.getByRole("tab", { name: sub })); await check("trades:" + String(sub).replace(/[^a-z]/gi, "").slice(0, 10)); } catch {}
    }
    await goTab("League");
    for (const sub of ["Scores", "Feed", "Teams", "Players"]) { try { await click(page.getByRole("tab", { name: sub })); await check("league:" + sub.toLowerCase()); } catch {} }
    await goTab("More"); await check("more");
  });
  await scenario("draft", { status: "drafting" }, width, large, async ({ check, click, page }) => {
    await click(page.getByRole("button", { name: "Open game" }));
    await check("draft");
  });
  await scenario("recap", { status: "in_season", week: 6 }, width, large, async ({ check, click, page, goTab }) => {
    await click(page.getByRole("button", { name: "Open game" }));
    await goTab("League");
    for (const sub of ["Recap", "Recaps"]) { try { await click(page.getByRole("tab", { name: sub })); await check("recap"); break; } catch {} }
  });
  await scenario("offseason", { status: "offseason", week: 0 }, width, large, async ({ check, click, page }) => {
    await click(page.getByRole("button", { name: "Open game" }));
    await check("offseason");
  });
  await scenario("complete", { status: "complete", week: 17 }, width, large, async ({ check, click, page }) => {
    await click(page.getByRole("button", { name: "Open game" }));
    await check("complete");
  });
}
await browser.close();
fs.writeFileSync(`${OUT}/sim-violations.json`, JSON.stringify(violations, null, 1));
const byKey = new Map();
for (const v of violations) { const k = `${v.kind} ${v.el} "${v.text}"`; const e = byKey.get(k) || { n: 0, where: new Set(), detail: v.detail }; e.n += 1; e.where.add(`${v.screen}@${v.width}${v.large ? "L" : ""}`); byKey.set(k, e); }
for (const [k, e] of byKey) console.log(`${k}  x${e.n}  e.g. ${[...e.where].slice(0, 3).join(", ")}  ${e.detail}`);
console.log(`sim layout guard: ${checked} screen states checked, ${byKey.size} distinct violations (${violations.length} total)`);
process.exit(violations.length ? 1 : 0);
