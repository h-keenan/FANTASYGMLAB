// New-user smoke ("new-user-smoke" CI job): the first-run journey at 390px against the PRODUCTION build of web-next, every API mocked.
// No real Sleeper, Supabase or Stripe call and no secret: localhost:8000 (the API) and dummy.supabase.co (auth + saved_leagues) are answered by
// route handlers below; any other host is aborted. Waits are on selectors / locator state, never fixed sleeps.
//
//   1  signed-out landing renders; "Try a sample league" opens the sample league whose Today has real modules
//   2  signed-out connect: Sleeper username -> mocked lookup + save -> /dashboard/<id> Today with modules filled
//   2b signed-in (stubbed session) with no league: onboarding intro, then the connect step, then Today
//   3  free account, no league: "No saved league yet" with Connect + Sample actions
//   4  bare /dashboard: signed out -> /, no league -> /connect-league, one league -> its Today
//   6  Pro vs Free (planOf, web-next/src/lib/plan.ts): Pro sees the GM Plan module + "Pro" plan, Free sees the paywall + "Free"
// Every step also asserts (5): no console errors / page errors, no "Something went wrong" boundary, no horizontal overflow, and (app pages) the first
// module within the 110px budget (module_scan.mjs TOP_BUDGET).
//
// Local run:  cd web-next && NEXT_PUBLIC_SUPABASE_URL=https://dummy.supabase.co NEXT_PUBLIC_SUPABASE_ANON_KEY=x NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npm run build && npx next start -p 3232
//             PW_CORE=.../playwright-core/index.mjs BASE=http://localhost:3232 node scripts/sim_layout_playwright/new_user_smoke.mjs
import fs from "fs";
import { FIX, FREE_GM_PLAN, FREE_PORTFOLIO, LEAGUE_NAME, LID, SLEEPER_USERNAME, me, session, sleeperLookup } from "./new_user_fixtures.mjs";
import { FIRST_MODULE, OFFENDERS } from "./new_user_checks.mjs";

const pw = await import(process.env.PW_CORE || "playwright-core");
const BASE = process.env.BASE || "http://localhost:3232";
const OUT = process.env.OUT || "/tmp/new-user-smoke";
const TOP_BUDGET = 110;
const WIDTH = 390;
const T = 30000; // generous selector timeout: waits return the moment the selector appears, so it costs nothing when healthy
const TODAY_HEADLINE = FIX.dashboard.items[0].headline;
fs.mkdirSync(OUT, { recursive: true });

const cors = { "access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "*" };
const json = (route, body, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body), headers: cors });

// One mocked world per scenario: who is signed in, their plan, and which leagues Supabase says they have saved.
function world(opts) {
  const w = { entitlement: "free", saved: [], signedIn: false, unmocked: [], ...opts };
  return w;
}

async function newPage(browser, w) {
  const ctx = await browser.newContext({ viewport: { width: WIDTH, height: 844 }, hasTouch: true, isMobile: true });
  // Fresh storage; the dashboard/onboarding state is whatever the scenario sets. Theme pinned so the run is deterministic.
  await ctx.addInitScript(([s, theme]) => {
    try {
      localStorage.clear();
      localStorage.setItem("fgl:theme-mode", theme);
      if (s) localStorage.setItem("sb-dummy-auth-token", JSON.stringify(s));
    } catch (e) { /* storage unavailable: the scenario will fail loudly */ }
  }, [w.signedIn ? session() : null, "dark"]);
  await ctx.route("**/*", async (route) => {
    const req = route.request();
    const u = new URL(req.url());
    if (u.hostname === "localhost" && u.port === new URL(BASE).port) {
      // Next's link prefetches of other routes render those routes server-side, which would call the (absent) real API: not part of the journey.
      if (u.searchParams.has("_rsc") && req.headers()["next-router-prefetch"]) return route.fulfill({ status: 204, headers: cors });
      return route.continue();
    }
    if (req.method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
    if (u.hostname === "dummy.supabase.co") {
      if (u.pathname.startsWith("/auth/v1/")) {
        if (u.pathname.endsWith("/user")) return json(route, session().user);
        return json(route, session()); // anonymous sign-up and password grant both answer with the stub session
      }
      if (u.pathname === "/rest/v1/saved_leagues") return json(route, w.saved);
      return json(route, []);
    }
    if (u.hostname === "localhost" && u.port === "8000") {
      const p = u.pathname;
      if (p === "/v1/e") return route.fulfill({ status: 204, headers: cors });
      if (p === "/v1/preferences") return json(route, { ok: true, ui_density: "guided", theme_mode: "dark", theme_mode_set: true, experience_level: "advanced", experience_goal: "win_now", last_league: null });
      if (p === "/v1/trade-outcomes/pending") return json(route, { ok: true, items: [] });
      if (/\/v1\/leagues\/[^/]+\/alerts$/.test(p)) return json(route, { ok: true, reason: "", items: [] });
      if (p === "/v1/me") return json(route, me(w.entitlement));
      if (p === "/v1/sleeper/leagues") return json(route, sleeperLookup);
      if (p === "/v1/me/link-sleeper") return json(route, { ok: true, sleeper_username: SLEEPER_USERNAME });
      if (p === "/v1/leagues/save") {
        w.saved = [{ league_id: LID, league_name: LEAGUE_NAME }];
        return json(route, { ok: true, reason: "", cap: 5, warming: false });
      }
      if (p === "/v1/portfolio/leagues") return json(route, w.entitlement === "free" ? FREE_PORTFOLIO : { ...FREE_PORTFOLIO, is_premium: true });
      const m = p.match(/\/v1\/leagues\/[^/]+\/([a-z-]+)$/) || p.match(/\/v1\/players\/(value-signals)$/) || (p.endsWith("/trade-ideas/multi") ? [0, "multi"] : null);
      if (m && m[1] === "gm-plan") return json(route, w.entitlement === "free" ? FREE_GM_PLAN : FIX["gm-plan"]);
      if (m && FIX[m[1]]) return json(route, FIX[m[1]]);
      w.unmocked.push(p);
      return json(route, {});
    }
    return route.abort(); // fonts, analytics, anything external: never reached
  });
  const page = await ctx.newPage();
  const problems = [];
  const external = (url) => { try { const h = new URL(url).hostname; return h !== "localhost" && h !== "dummy.supabase.co"; } catch { return false; } };
  page.on("console", (msg) => { if (msg.type() === "error" && !external(msg.location().url || "")) problems.push(`console.error: ${msg.text().slice(0, 200)}`); });
  page.on("response", (res) => { if (res.status() >= 400 && !external(res.url())) problems.push(`HTTP ${res.status()} ${res.request().method()} ${res.url().replace(BASE, "")}`); });
  page.on("pageerror", (err) => problems.push(`pageerror: ${String(err).slice(0, 200)}`));
  return { ctx, page, problems, w };
}

const results = [];
// Common per-step assertions (5). `app` pages (nav shell) also get the first-module budget; landing / onboarding / sample are exempt like module_scan's TOP_EXEMPT.
async function check(env, name, { app = false, expectText = [], expectSel = [] } = {}) {
  const { page, problems } = env;
  const fails = [];
  try {
    for (const sel of expectSel) await page.locator(sel).first().waitFor({ state: "visible", timeout: T });
    for (const text of expectText) await page.getByText(text, { exact: false }).filter({ visible: true }).first().waitFor({ state: "visible", timeout: T });
    await page.evaluate(() => document.fonts && document.fonts.ready);
    await page.addStyleTag({ content: ".app-shell,.sim-root{overflow-x:visible!important}" }); // measure without the clip backstop so a real overflow is caught
    const res = await page.evaluate(() => ({ w: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth, crashed: /Something went wrong/i.test(document.body.innerText), empty: document.body.innerText.trim().length < 40 }));
    if (res.w > res.cw + 1) fails.push(`horizontal overflow ${res.w}>${res.cw}: ${(await page.evaluate(OFFENDERS)).join(" || ")}`);
    if (res.crashed) fails.push('"Something went wrong" error boundary rendered');
    if (res.empty) fails.push("page is blank");
    const fm = await page.evaluate(FIRST_MODULE);
    const offset = fm ? (fm.cardGap ?? fm.gap) : null;
    if (app && offset != null && offset > TOP_BUDGET) fails.push(`first module ${offset}px below the nav (budget ${TOP_BUDGET}px)`);
    await page.screenshot({ path: `${OUT}/${name.replace(/\W+/g, "-")}.png` });
    // Console errors can land a beat after the content is visible: one more settle on the network, then read them.
    await page.waitForLoadState("networkidle", { timeout: T }).catch(() => {});
    fails.push(...problems.splice(0));
    if (env.w.unmocked.length) { console.log(`     unmocked API paths: ${[...new Set(env.w.unmocked.splice(0))].join(", ")}`); }
    console.log(`${fails.length ? "FAIL" : "ok  "} ${name}${offset != null ? `  (first module ${offset}px)` : ""}${fails.length ? "  " + fails.join("; ") : ""}`);
  } catch (e) {
    fails.push(String(e).split("\n")[0].slice(0, 220));
    fails.push(...problems.splice(0));
    await page.screenshot({ path: `${OUT}/${name.replace(/\W+/g, "-")}-FAIL.png` }).catch(() => {});
    console.log(`FAIL ${name}  ${fails.join("; ")}`);
  }
  results.push({ name, fails });
}

const browser = await pw.chromium.launch(process.env.CHROME ? { executablePath: process.env.CHROME } : {});
const goto = (env, path) => env.page.goto(`${BASE}${path}`, { waitUntil: "domcontentloaded", timeout: 60000 });

// 1. Signed-out landing, then the sample league.
{
  const env = await newPage(browser, world());
  await goto(env, "/");
  await check(env, "1a landing (signed out)", { expectSel: ['[data-testid="connect-hero"] input'], expectText: ["Connect your league"] });
  await env.page.getByTestId("sample-league-button").first().click();
  await env.page.waitForURL("**/sample-league", { timeout: T });
  await check(env, "1b sample league Today", { expectSel: ['[data-testid="sample-banner"]'], expectText: ["Sample league"] });
  const modules = await env.page.locator("main section, main article, main [class*=glass-surface], main [class*=accent-card]").count();
  if (modules < 2) { console.log(`FAIL 1b sample league Today has no modules (${modules})`); results.push({ name: "1b modules", fails: ["sample Today empty"] }); }
  await env.ctx.close();
}

// 2. Signed-out connect: username -> guest session (stubbed) -> mocked Sleeper lookup + save -> Today.
{
  const env = await newPage(browser, world());
  await goto(env, "/");
  await env.page.locator('[data-testid="connect-hero"] input').first().fill(SLEEPER_USERNAME);
  await env.page.locator('[data-testid="connect-hero"] button[type="submit"], [data-testid="connect-hero"] form button').first().click();
  await env.page.waitForURL(`**/dashboard/${LID}**`, { timeout: T });
  await check(env, "2 connect league -> Today", { app: true, expectText: [TODAY_HEADLINE] });
  await env.ctx.close();
}

// 2b. A signed-in account (stubbed session) with no league: onboarding intro -> connect step -> Today.
{
  const env = await newPage(browser, world({ signedIn: true }));
  await goto(env, "/");
  await check(env, "2b onboarding intro", { expectSel: [".onboarding-skip"] });
  await env.page.locator(".onboarding-skip").first().click();
  await check(env, "2b onboarding connect step", { expectSel: ['[data-testid="connect-first-heading"] input'], expectText: ["Connect your league"] });
  await env.page.locator('[data-testid="connect-first-heading"] input').first().fill(SLEEPER_USERNAME);
  await env.page.locator('[data-testid="connect-first-heading"] form button, [data-testid="connect-first-heading"] button[type="submit"]').first().click();
  await env.page.waitForURL(`**/dashboard/${LID}**`, { timeout: T });
  await check(env, "2b onboarding -> Today", { app: true, expectText: [TODAY_HEADLINE] });
  await env.ctx.close();
}

// 3. Free account with no saved league: the #2048 "No saved league yet" next step.
{
  const env = await newPage(browser, world({ signedIn: true, entitlement: "free" }));
  await goto(env, "/leagues");
  await check(env, "3 free, no league (Your leagues)", { app: true, expectText: ["No saved league yet", "Connect a league"], expectSel: ['a[href="/connect-league"]', 'a[href="/sample-league"]'] });
  await env.ctx.close();
}

// 4. Bare /dashboard (#2056).
{
  const env = await newPage(browser, world());
  await goto(env, "/dashboard");
  await env.page.waitForURL(`${BASE}/`, { timeout: T });
  await check(env, "4a /dashboard signed out -> /", { expectSel: ['[data-testid="connect-hero"]'] });
  await env.ctx.close();
}
{
  const env = await newPage(browser, world({ signedIn: true }));
  await goto(env, "/dashboard");
  await env.page.waitForURL("**/connect-league", { timeout: T });
  await check(env, "4b /dashboard, no league -> /connect-league", { expectText: ["Add a league"] });
  await env.ctx.close();
}
{
  const env = await newPage(browser, world({ signedIn: true, saved: [{ league_id: LID, league_name: LEAGUE_NAME }] }));
  await goto(env, "/dashboard");
  await env.page.waitForURL(`**/dashboard/${LID}**`, { timeout: T });
  await check(env, "4c /dashboard, one league -> its Today", { app: true, expectText: [TODAY_HEADLINE] });
  await env.ctx.close();
}

// 6. Pro vs Free through the shared planOf(): same route, the plan decides module vs paywall (and the Account plan label).
for (const [plan, entitlement] of [["Pro", "premium"], ["Free", "free"]]) {
  const env = await newPage(browser, world({ signedIn: true, entitlement, saved: [{ league_id: LID, league_name: LEAGUE_NAME }] }));
  await goto(env, `/gm-plan/${LID}?name=${encodeURIComponent(LEAGUE_NAME)}`);
  if (plan === "Pro") {
    await check(env, "6a Pro: GM Plan module", { app: true, expectText: [FIX["gm-plan"].headline] });
    if (await env.page.locator('[data-testid="paid-preview"]').count()) { console.log("FAIL 6a Pro sees the paywall"); results.push({ name: "6a", fails: ["Pro sees paywall"] }); }
  } else {
    await check(env, "6b Free: GM Plan paywall", { app: true, expectSel: ['[data-testid="paid-preview"]', '[data-testid="gm-plan-pro-preview"]'] });
    if (await env.page.getByText(FIX["gm-plan"].headline).count()) { console.log("FAIL 6b Free sees the Pro module"); results.push({ name: "6b", fails: ["Free sees Pro module"] }); }
  }
  await goto(env, "/account");
  await check(env, `6c Account plan label (${plan})`, { expectText: ["smoke@example.com"], expectSel: [`dd:text-is("${plan}")`] });
  await env.ctx.close();
}

await browser.close();
const bad = results.filter((r) => r.fails.length);
fs.writeFileSync(`${OUT}/report.json`, JSON.stringify(results, null, 1));
console.log(`${results.length - bad.length}/${results.length} checks passed`);
process.exit(bad.length ? 1 : 0);
