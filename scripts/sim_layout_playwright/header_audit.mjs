// Header audit harness (docs/audits/2026-11-header-audit.md): the phone shell header and the league switcher at 320/360/390/430,
// light and dark, with a long league name, a short one and 12 saved leagues; plus the Fantasy Sim game header.
//   PW_CORE=.../playwright-core/index.mjs CHROME=... BASE=http://localhost:3197 OUT=/tmp/header-audit node scripts/sim_layout_playwright/header_audit.mjs
import fs from "fs";
import { createMock } from "./simmock.mjs";

const { chromium } = await import(process.env.PW_CORE || "playwright-core");
const BASE = process.env.BASE || "http://localhost:3197";
const OUT = process.env.OUT || "/private/tmp/claude-501/header-audit";
const WIDTHS = (process.env.WIDTHS || "320,360,390,430").split(",").map(Number);
fs.mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.CHROME || process.env.HOME + "/Library/Caches/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-mac-arm64/chrome-headless-shell" });
const session = { access_token: "a.b.c", refresh_token: "r", token_type: "bearer", expires_in: 99999, expires_at: Math.floor(Date.now() / 1000) + 99999, user: { id: "u1", aud: "authenticated", role: "authenticated", email: "t@example.com", app_metadata: {}, user_metadata: {}, created_at: "2026-01-01T00:00:00Z" } };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const LID = "1221647449446162432";
const NAMES = ["The Revivalry Dynasty Superflex League of Champions 2026", "Revivalry", "Donk", "Gridiron Gurus", "Sunday Scaries", "The Last Dance Dynasty", "Taco Tuesday Trophy League", "Waiver Wire Warriors", "Bro League", "Money Matters 12 Team PPR", "Office League", "Family Feud"];
const leagues = NAMES.map((n, i) => ({ league_id: i === 0 ? LID : String(900 + i), league_name: n }));
const metrics = () => {
  const out = { overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth };
  const hdr = document.querySelector('[data-testid="shell-header"]') || document.querySelector("header");
  const r = hdr?.getBoundingClientRect();
  out.headerHeight = r ? Math.round(r.height) : null;
  const chip = [...document.querySelectorAll("header button[aria-haspopup=menu]")].find((b) => /Dynasty|Revivalry|Switch league|Your league/.test(b.textContent));
  if (chip) {
    const c = chip.getBoundingClientRect(); const t = chip.querySelector(".truncate");
    out.switcher = { w: Math.round(c.width), h: Math.round(c.height), text: chip.innerText.replace(/\n/g, " | "), truncated: t ? t.scrollWidth > t.clientWidth : false, right: Math.round(window.innerWidth - c.right) };
  }
  const tiny = [...document.querySelectorAll("header *")].filter((e) => e.children.length === 0 && e.textContent.trim() && parseFloat(getComputedStyle(e).fontSize) < 11.5).map((e) => `${parseFloat(getComputedStyle(e).fontSize)}px "${e.textContent.trim().slice(0, 18)}"`);
  out.tinyText = tiny.slice(0, 6);
  out.targets = [...document.querySelectorAll("header button, header a")].map((e) => e.getBoundingClientRect()).filter((b) => b.width > 0 && (b.height < 43.5 || b.width < 43.5)).length;
  const menu = document.querySelector('[role="menu"]');
  if (menu) { const m = menu.getBoundingClientRect(); out.menu = { left: Math.round(m.left), right: Math.round(m.right), top: Math.round(m.top), bottom: Math.round(m.bottom), vh: window.innerHeight, items: menu.querySelectorAll('[role="menuitem"]').length, hasAvatar: Boolean(menu.querySelector("img,svg[data-avatar],[data-testid*=avatar]")), scrolls: menu.scrollHeight > menu.clientHeight + 1, overflowsViewport: m.bottom > window.innerHeight }; }
  return out;
};
async function ctxFor(w, theme, leagueRows) {
  const ctx = await browser.newContext({ viewport: { width: w, height: 844 }, hasTouch: true, isMobile: true, deviceScaleFactor: 2 });
  await ctx.addInitScript(([s, t]) => { try { localStorage.clear(); localStorage.setItem("fgl:theme-mode", t); localStorage.setItem("fgl:nav", "bottom"); localStorage.setItem("sb-dummy-auth-token", JSON.stringify(s)); localStorage.setItem("fgl:onboarding-complete", "1"); } catch (e) {} }, [session, theme]);
  await ctx.route("**/*", async (route) => {
    const u = new URL(route.request().url());
    const cors = { "access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "*" };
    if (u.hostname === "localhost" && u.port === "8000") {
      if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
      if (u.pathname.endsWith("/notifications")) return route.fulfill({ status: 200, contentType: "application/json", headers: cors, body: JSON.stringify({ ok: true, reason: "", seq: 9, unread: 12, items: Array.from({ length: 12 }, (_, i) => ({ id: `n${i}`, title: `Alert ${i}`, body: "x", read: false, created_at: "2026-11-14T00:00:00Z", kind: "news" })) }) });
      return route.fulfill({ status: 200, contentType: "application/json", body: "{}", headers: cors });
    }
    if (u.hostname === "dummy.supabase.co") return route.fulfill({ status: 200, contentType: "application/json", body: u.pathname.includes("saved_leagues") ? JSON.stringify(leagueRows) : u.pathname.startsWith("/rest/v1/") ? "[]" : "{}", headers: cors });
    return route.continue();
  });
  return ctx;
}
const results = [];
for (const theme of ["dark", "light"]) for (const w of WIDTHS) for (const [label, rows, name] of [["long", leagues, NAMES[0]], ["short", leagues.slice(0, 3), "Donk"], ["none", [], ""]]) {
  const ctx = await ctxFor(w, theme, rows);
  const page = await ctx.newPage();
  await page.goto(`${BASE}/dashboard/${LID}${name ? `?name=${encodeURIComponent(name)}` : ""}`, { waitUntil: "domcontentloaded", timeout: 90000 });
  await page.addStyleTag({ content: "nextjs-portal,[data-nextjs-toast]{display:none!important}" }).catch(() => {});
  await sleep(w === WIDTHS[0] && theme === "dark" && label === "long" ? 12000 : 4500);
  const closed = await page.evaluate(metrics);
  if (theme === "dark" || label === "long") await page.screenshot({ path: `${OUT}/header-${theme}-${label}-${w}.png`, clip: { x: 0, y: 0, width: w, height: 130 } });
  await page.locator('header button[aria-haspopup="menu"]').first().click({ timeout: 4000 }).catch(() => {});
  await sleep(500);
  const open = await page.evaluate(metrics);
  if (label !== "none" && theme === "dark") await page.screenshot({ path: `${OUT}/switcher-open-${label}-${w}.png` });
  results.push({ theme, w, label, closed, menu: open.menu });
  await ctx.close();
}
// Sim game header
for (const w of WIDTHS) {
  const mock = createMock({ status: "in_season", week: 10 });
  const ctx = await ctxFor(w, "dark", []);
  await ctx.route("**/v1/sim/**", async (route) => {
    const u = new URL(route.request().url()); const raw = route.request().postData(); let json = null; try { json = raw ? JSON.parse(raw) : null; } catch {}
    const res = mock(route.request().method(), u.pathname, Object.fromEntries(u.searchParams), json);
    return route.fulfill({ status: res?.status ?? 200, contentType: "application/json", body: JSON.stringify(res?.body ?? {}), headers: { "access-control-allow-origin": "*" } });
  });
  const page = await ctx.newPage();
  await page.goto(`${BASE}/gm-game`, { waitUntil: "domcontentloaded" });
  await sleep(9000);
  await page.getByRole("button", { name: "Open game" }).first().dispatchEvent("click").catch(() => {});
  await sleep(2500);
  const sim = await page.evaluate(() => { const h = document.querySelector('[data-testid="sim-game-header"]'); const r = h?.getBoundingClientRect(); const chip = document.querySelector('[data-testid="sim-team-chip"]'); return { present: Boolean(h), height: r ? Math.round(r.height) : null, overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth, chipText: chip?.innerText.replace(/\n/g, " | ") ?? null, rows: h ? new Set([...h.children].map((c) => Math.round(c.getBoundingClientRect().top))).size : 0 }; });
  await page.screenshot({ path: `${OUT}/sim-header-${w}.png`, clip: { x: 0, y: 0, width: w, height: 170 } }).catch(() => {});
  results.push({ sim: true, w, ...sim });
  await ctx.close();
}
await browser.close();
fs.writeFileSync(`${OUT}/report.json`, JSON.stringify(results, null, 1));
for (const r of results) console.log(JSON.stringify(r).slice(0, 420));
