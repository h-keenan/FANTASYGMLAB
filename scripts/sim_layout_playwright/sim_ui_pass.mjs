// Full-page 390px screenshots of every Fantasy Sim screen, plus per-screen height / overflow / collapsed-module facts.
//   PW_CORE=.../playwright-core/index.mjs BASE=http://localhost:3197 OUT=/tmp/simpass [ONLY=home,team] node scripts/sim_layout_playwright/sim_ui_pass.mjs
import fs from "fs";
import { createMock } from "./simmock.mjs";

const { chromium } = await import(process.env.PW_CORE || "playwright-core");
const BASE = process.env.BASE || "http://localhost:3197";
const OUT = process.env.OUT || "/private/tmp/claude-501/simpass";
const ONLY = process.env.ONLY ? process.env.ONLY.split(",") : null;
fs.mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.HOME + "/Library/Caches/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-mac-arm64/chrome-headless-shell" });
const session = { access_token: "a.b.c", refresh_token: "r", token_type: "bearer", expires_in: 99999, expires_at: Math.floor(Date.now() / 1000) + 99999, user: { id: "u1", aud: "authenticated", role: "authenticated", email: "t@example.com", app_metadata: {}, user_metadata: {}, created_at: "2026-01-01T00:00:00Z" } };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const want = (n) => !ONLY || ONLY.some((o) => n.startsWith(o));

async function scenario(name, mockOpts, steps) {
  const mock = createMock(mockOpts);
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true, deviceScaleFactor: 1 });
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
  const click = async (loc) => { await loc.first().dispatchEvent("click"); await sleep(900); };
  const goTab = async (label) => { await click(page.getByTestId("sim-game-orb")); await click(page.getByTestId("sim-game-nav").getByRole("button", { name: new RegExp(`^${label}`) })); };
  const shot = async (n) => {
    if (!want(n)) return;
    await sleep(600);
    const facts = await page.evaluate(() => {
      const root = document.querySelector("main") || document.body;
      const mods = [...document.querySelectorAll("[data-compact-module], .compact-module")];
      return { height: document.documentElement.scrollHeight, scrollWidth: document.documentElement.scrollWidth, modules: mods.length, text: (root.innerText || "").length };
    });
    console.log(n.padEnd(22), JSON.stringify(facts));
    await page.screenshot({ path: `${OUT}/${n}.png`, fullPage: true });
  };
  await page.goto(`${BASE}/gm-game`, { waitUntil: "domcontentloaded" });
  await page.addStyleTag({ content: "nextjs-portal,[data-nextjs-toast]{display:none!important}" }).catch(() => {});
  await sleep(11000);
  try { await steps({ page, click, goTab, shot, sleep }); } catch (e) { console.log("FAIL", name, String(e).slice(0, 200)); }
  await ctx.close();
}

await scenario("hub", { status: "in_season", week: 4 }, async ({ shot, click, page, goTab }) => {
  await shot("hub");
  await click(page.getByRole("button", { name: "Open game" }));
  await shot("home");
  for (const t of ["Team", "Players", "Trades", "League"]) { await goTab(t); await shot(t.toLowerCase()); }
  await goTab("Trades");
  for (const sub of [/Make an offer/, /Inbox|Offers/, /Block|Your block/]) {
    try { await click(page.getByRole("tab", { name: sub })); await shot("trades-" + String(sub).replace(/[^a-z]/gi, "").slice(0, 10)); } catch {}
  }
  await goTab("League");
  for (const sub of ["Scores", "Feed", "Teams", "Players"]) { try { await click(page.getByRole("tab", { name: sub })); await shot("league-" + sub.toLowerCase()); } catch {} }
  await goTab("More"); await shot("more");
});
await scenario("draft", { status: "drafting" }, async ({ shot, click, page }) => {
  await click(page.getByRole("button", { name: "Open game" }));
  await shot("draft");
});
await scenario("complete", { status: "complete", week: 17 }, async ({ shot, click, page }) => {
  await click(page.getByRole("button", { name: "Open game" }));
  await shot("complete");
});
await browser.close();
