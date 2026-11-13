// UI audit harness: renders Fantasy Sim screens at 360/375/390/430px in dark and light, runs DOM checks (horizontal overflow,
// tap targets under 44px, unnamed controls, truncated names, tiny text, contrast, dialog names, button-height spread) and
// writes a JSON report (+ screenshots of a few states).
//   (SCALE=2 emulates 200% text size)
//   PW_CORE=/path/to/playwright-core/index.mjs BASE=http://localhost:3197 OUT=/tmp/audit node scripts/sim_layout_playwright/ui_audit.mjs [screen]
import fs from "fs";
import { createMock } from "./simmock.mjs";

const { chromium } = await import(process.env.PW_CORE || "playwright-core");
const BASE = process.env.BASE || "http://localhost:3197";
const OUT = process.env.OUT || "/private/tmp/claude-501/audit-shots";
const WIDTHS = (process.env.WIDTHS || "360,375,390,430").split(",").map(Number);
const THEMES = (process.env.THEMES || "dark,light").split(",");
const only = process.argv[2];
const axeSource = process.env.AXE === "1" ? fs.readFileSync(process.env.AXE_JS || "/private/tmp/claude-501/pw2/node_modules/axe-core/axe.min.js", "utf8") : "";
fs.mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.HOME + "/Library/Caches/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-mac-arm64/chrome-headless-shell" });
const session = { access_token: "a.b.c", refresh_token: "r", token_type: "bearer", expires_in: 99999, expires_at: Math.floor(Date.now() / 1000) + 99999, user: { id: "u1", aud: "authenticated", role: "authenticated", email: "t@example.com", app_metadata: {}, user_metadata: {}, created_at: "2026-01-01T00:00:00Z" } };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

import { CHECKS } from "./audit_checks.mjs";

async function run() {
  const results = [];
  for (const theme of THEMES) for (const w of WIDTHS) {
    const mock = createMock({ status: "in_season", week: 4, pro: true });
    const ctx = await browser.newContext({ viewport: { width: w, height: 844 }, hasTouch: true, isMobile: true, deviceScaleFactor: 2 });
    await ctx.addInitScript(([t, s]) => { try { localStorage.setItem("fgl:theme-mode", t); localStorage.setItem("sb-dummy-auth-token", JSON.stringify(s)); localStorage.setItem("fgl:onboarding-complete", "1"); } catch (e) {} }, [theme, session]);
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
    const audit = async (name) => {
      if (only && !name.startsWith(only)) return;
      await sleep(700);
      const r = await page.evaluate(CHECKS);
      let axe = null;
      if (process.env.AXE === "1") {
        await page.evaluate(axeSource);
        axe = await page.evaluate(async () => (await window.axe.run(document, { resultTypes: ["violations"] })).violations.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length, sample: v.nodes[0]?.target?.join(" ").slice(0, 90), help: v.help })));
      }
      results.push({ screen: name, width: w, theme, ...r, axe });
      if (w === 390) await page.screenshot({ path: `${OUT}/${name.replace(/[^a-z0-9]+/gi, "-")}-${theme}-${w}.png` });
    };
    const click = async (loc) => { await loc.first().dispatchEvent("click"); await sleep(900); };
    const goTab = async (label) => { await click(page.getByTestId("sim-game-orb")); await click(page.getByTestId("sim-game-nav").getByRole("button", { name: new RegExp(`^${label}`) })); };
    await page.goto(`${BASE}/gm-game`, { waitUntil: "domcontentloaded" });
    await page.addStyleTag({ content: `nextjs-portal,[data-nextjs-toast]{display:none!important}${Number(process.env.SCALE || 1) > 1 ? `html{font-size:${16 * Number(process.env.SCALE)}px!important}` : ""}` }).catch(() => {});
    await sleep(12000);
    await audit("hub");
    await click(page.getByRole("button", { name: "Open game" }));
    await sleep(2000);
    await audit("home");
    for (const tab of ["Team", "Players", "Trades", "League", "More"]) {
      try { await goTab(tab); await audit(tab.toLowerCase()); } catch (e) { console.log("tab fail", tab, w, theme, String(e).slice(0, 80)); }
    }
    try {
      await goTab("League");
      for (const sub of ["Scores", "Feed", "Teams", "Players"]) { await click(page.getByRole("tab", { name: sub })); await audit(`league-${sub.toLowerCase()}`); }
    } catch (e) { console.log("league fail", String(e).slice(0, 80)); }
    try { await goTab("Trades"); await click(page.getByRole("tab", { name: /Make an offer/ })); await audit("trades-build"); } catch (e) { console.log("trades-build fail", String(e).slice(0, 80)); }
    await ctx.close();
  }
  return results;
}
const results = await run();
fs.writeFileSync(`${OUT}/report.json`, JSON.stringify(results, null, 1));
console.log("screens audited:", results.length, "->", `${OUT}/report.json`);
await browser.close();
