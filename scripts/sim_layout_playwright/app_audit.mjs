// UI audit for the MAIN app routes (not the Fantasy Sim): same DOM checks as ui_audit.mjs, optional 200% text scaling and axe-core.
// The API is stubbed (set LIVE_API=1 to hit a real local backend: services.mobile_api_service with a fake GoTrue, see docs/audits) (every /v1 call answers an empty 200), so each route renders its loading / empty / error state: that is
// what is audited here (overflow, tap targets, names, truncation, contrast, axe rules), not data-rich layouts.
//   PW_CORE=.../playwright-core/index.mjs AXE_JS=.../axe-core/axe.min.js BASE=http://localhost:3197 OUT=/tmp/app-audit \
//     [WIDTHS=360,390] [THEMES=dark,light] [SCALE=2] [AXE=1] [ROUTES=/,/players] node scripts/sim_layout_playwright/app_audit.mjs
import fs from "fs";

import { CHECKS } from "./audit_checks.mjs";

const { chromium } = await import(process.env.PW_CORE || "playwright-core");
const BASE = process.env.BASE || "http://localhost:3197";
const OUT = process.env.OUT || "/private/tmp/claude-501/app-audit";
const WIDTHS = (process.env.WIDTHS || "360,375,390,430").split(",").map(Number);
const THEMES = (process.env.THEMES || "dark,light").split(",");
const SCALE = Number(process.env.SCALE || 1);
const AXE = process.env.AXE === "1";
const ROUTES = (process.env.ROUTES || "/,/dashboard,/players,/trade-hub,/trade-analyzer,/waivers,/my-team,/league-rankings,/gm-plan,/account,/premium,/connect-league,/news,/matchup,/draft-center,/legal/privacy").split(",");
fs.mkdirSync(OUT, { recursive: true });
const axeSource = AXE ? fs.readFileSync(process.env.AXE_JS || "/private/tmp/claude-501/pw2/node_modules/axe-core/axe.min.js", "utf8") : "";
const browser = await chromium.launch({ executablePath: process.env.HOME + "/Library/Caches/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-mac-arm64/chrome-headless-shell" });
const session = { access_token: "a.b.c", refresh_token: "r", token_type: "bearer", expires_in: 99999, expires_at: Math.floor(Date.now() / 1000) + 99999, user: { id: "u1", aud: "authenticated", role: "authenticated", email: "t@example.com", app_metadata: {}, user_metadata: {}, created_at: "2026-01-01T00:00:00Z" } };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const results = [];
for (const theme of THEMES) for (const w of WIDTHS) {
  const ctx = await browser.newContext({ viewport: { width: w, height: 844 }, hasTouch: true, isMobile: true, deviceScaleFactor: 1 });
  await ctx.addInitScript(([t, s]) => { try { localStorage.setItem("fgl:theme-mode", t); localStorage.setItem("sb-dummy-auth-token", JSON.stringify(s)); localStorage.setItem("fgl:onboarding-complete", "1"); } catch (e) {} }, [theme, session]);
  await ctx.route("**/*", async (route) => {
    const u = new URL(route.request().url());
    const cors = { "access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "*" };
    if (u.hostname === "localhost" && u.port === "8000" && process.env.LIVE_API !== "1") {
      if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
      return route.fulfill({ status: 200, contentType: "application/json", body: "{}", headers: cors });
    }
    if (u.hostname === "dummy.supabase.co") return route.fulfill({ status: 200, contentType: "application/json", body: u.pathname.startsWith("/rest/v1/") ? "[]" : "{}", headers: cors });
    return route.continue();
  });
  const page = await ctx.newPage();
  page.on("pageerror", () => {});
  for (const route of ROUTES) {
    try {
      await page.goto(`${BASE}${route}`, { waitUntil: "domcontentloaded", timeout: 60000 });
      await page.addStyleTag({ content: `nextjs-portal,[data-nextjs-toast]{display:none!important}${SCALE > 1 ? `html{font-size:${16 * SCALE}px!important}` : ""}` }).catch(() => {});
      await sleep(route === ROUTES[0] ? 9000 : 3500);
      const r = await page.evaluate(CHECKS);
      let axe = null;
      if (AXE) {
        await page.evaluate(axeSource);
        axe = await page.evaluate(async () => { const res = await window.axe.run(document, { resultTypes: ["violations"] }); return res.violations.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length, sample: v.nodes[0]?.target?.join(" ").slice(0, 80), help: v.help })); });
      }
      results.push({ route, width: w, theme, scale: SCALE, ...r, axe });
      if (w === 390 && theme === "dark") await page.screenshot({ path: `${OUT}/${route.replace(/[^a-z0-9]+/gi, "-") || "home"}-${SCALE}x.png` });
    } catch (e) {
      results.push({ route, width: w, theme, scale: SCALE, error: String(e).slice(0, 120) });
    }
  }
  await ctx.close();
}
fs.writeFileSync(`${OUT}/report-${SCALE}x${AXE ? "-axe" : ""}.json`, JSON.stringify(results, null, 1));
console.log("routes audited:", results.length);
await browser.close();
