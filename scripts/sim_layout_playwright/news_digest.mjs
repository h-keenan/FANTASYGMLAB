// 390px screenshots + geometry of the News digest: compact (roster first), item expanded, player picked, league module open, no-league.
//   PW_CORE=.../playwright-core/index.mjs BASE=http://localhost:3197 OUT=/tmp/news node scripts/sim_layout_playwright/news_digest.mjs
import fs from "fs";

const { chromium } = await import(process.env.PW_CORE || "playwright-core");
const BASE = process.env.BASE || "http://localhost:3197";
const OUT = process.env.OUT || "/private/tmp/claude-501/news-shots";
fs.mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.HOME + "/Library/Caches/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-mac-arm64/chrome-headless-shell" });
const session = { access_token: "a.b.c", refresh_token: "r", token_type: "bearer", expires_in: 99999, expires_at: Math.floor(Date.now() / 1000) + 99999, user: { id: "u1", aud: "authenticated", role: "authenticated", email: "t@example.com", app_metadata: {}, user_metadata: {}, created_at: "2026-01-01T00:00:00Z" } };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const now = Date.now() / 1000;
const mk = (title, ev, ago, extra = {}) => ({ title, link: `https://example.com/${encodeURIComponent(title).slice(0, 20)}`, source: "Beat writer", summary: null, published_ts: now - ago, event_type: ev, speculative: false, ...extra });
const alert = (n, id, name, pos, team, title, ev, ago, rel, read = false) => ({ ...mk(title, ev, ago), alert_key: `k${n}`, read, matched_player: name, matched_player_id: id, matched_player_position: pos, matched_player_team: team, matched_player_tier: null, relevance_reason: null, roster_relationship: rel });
const ALERTS = [
  alert(1, "9221", "Jahmyr Gibbs", "RB", "DET", "Full practice, expects 22 touches", "role/depth chart", 3600, "starter"),
  alert(2, "6804", "Trey Lawrence", "TE", "NYG", "Questionable with ankle, test Friday", "injury/status", 10800, "starter"),
  alert(3, "6794", "Malik Nabers", "WR", "NYG", "Limited again, role unchanged", "injury/status", 21600, "bench", true),
  alert(4, "4881", "Christian Sutton-Washington", "QB", "HOU", "Throws for 3 TDs in the scrimmage", "role/depth chart", 86400, "bench", true),
];
const GENERAL = [
  mk("Example Eagles claim K. Allen off waivers", "transaction", 18000),
  mk("Sample Sharks cut D. Henry", "transaction", 25000, { matched_player: "Devon Henry", matched_player_id: "1111", matched_player_position: "RB", matched_player_team: "MIA" }),
  mk("Test Titans trade for P. Nacua", "transaction", 32000),
];
const J = (b) => ({ status: 200, contentType: "application/json", body: JSON.stringify(b), headers: { "access-control-allow-origin": "*", "access-control-allow-headers": "*" } });
let failed = 0;

async function scenario(name, withLeague, steps) {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true, deviceScaleFactor: 2 });
  await ctx.addInitScript(([s]) => { try { localStorage.setItem("fgl:theme-mode", "dark"); localStorage.setItem("sb-dummy-auth-token", JSON.stringify(s)); localStorage.setItem("fgl:onboarding-complete", "1"); } catch (e) {} }, [session]);
  await ctx.route("**/*", async (route) => {
    const u = new URL(route.request().url());
    if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers: { "access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "*" } });
    if (u.hostname === "localhost" && u.port === "8000") {
      if (u.pathname === "/v1/news") return route.fulfill(J({ ok: true, items: GENERAL }));
      if (/\/alerts$/.test(u.pathname)) return route.fulfill(J({ ok: true, reason: "", items: ALERTS }));
      return route.fulfill(J({ ok: true }));
    }
    if (u.hostname === "dummy.supabase.co") return route.fulfill(J(u.pathname.includes("saved_leagues") && withLeague ? [{ league_id: "L1", league_name: "Dynasty Degens" }] : u.pathname.includes("saved_leagues") ? [] : {}));
    return route.continue();
  });
  const page = await ctx.newPage();
  page.on("pageerror", (e) => console.log("PAGEERR", e.message));
  await page.goto(`${BASE}/news`, { waitUntil: "domcontentloaded" });
  await page.addStyleTag({ content: "nextjs-portal,[data-nextjs-toast]{display:none!important}" }).catch(() => {});
  await page.waitForSelector("[data-testid=news-digest]", { timeout: 90000 }).catch(() => {});
  await sleep(2500);
  const shot = async (n) => {
    await sleep(500);
    const g = await page.evaluate(() => {
      const bad = [...document.querySelectorAll("main *")].filter((el) => { const r = el.getBoundingClientRect(); return r.width && (r.right > innerWidth + 1 || r.left < -1) && !el.closest("[role=group]"); }).map((e) => `${e.tagName}.${String(e.className).slice(0, 24)}`);
      // player names: none may be clipped with an ellipsis, and none may overflow their box
      const names = [...document.querySelectorAll("main [data-player-name], main .font-bold")].filter((e) => getComputedStyle(e).textOverflow === "ellipsis" && e.scrollWidth > e.clientWidth).length;
      return { scrollWidth: document.documentElement.scrollWidth, overflow: bad.slice(0, 5), height: document.documentElement.scrollHeight, ellipsizedNames: names, rows: document.querySelectorAll("[data-testid=news-row]").length };
    });
    console.log(n.padEnd(20), JSON.stringify(g));
    if (g.scrollWidth > 390 || g.overflow.length || g.ellipsizedNames) failed++;
    await page.screenshot({ path: `${OUT}/${n}.png`, fullPage: true });
  };
  try { await steps({ page, shot, sleep }); } catch (e) { failed++; console.log("FAIL", name, String(e).slice(0, 300)); }
  await ctx.close();
}

await scenario("roster", true, async ({ page, shot, sleep }) => {
  await shot("news-compact");
  await page.getByTestId("news-row").nth(1).locator("button").first().dispatchEvent("click"); await sleep(500);
  await shot("news-item-expanded");
  await page.getByRole("button", { name: /Around the NFL/ }).dispatchEvent("click"); await sleep(500);
  await shot("news-league-open");
  await page.getByRole("button", { name: /^Jahmyr Gibbs, 1 item/ }).dispatchEvent("click"); await sleep(500);
  await shot("news-player-picked");
});
await scenario("noleague", false, async ({ shot }) => { await shot("news-no-league"); });
await browser.close();
process.exit(failed ? 1 : 0);
