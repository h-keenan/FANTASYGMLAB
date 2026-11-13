// UI audit harness: renders Fantasy Sim screens at 360/375/390/430px in dark and light, runs DOM checks (horizontal overflow,
// tap targets under 44px, unnamed controls, truncated names, tiny text, contrast, dialog names, button-height spread) and
// writes a JSON report (+ screenshots of a few states).
//   PW_CORE=/path/to/playwright-core/index.mjs BASE=http://localhost:3197 OUT=/tmp/audit node scripts/sim_layout_playwright/ui_audit.mjs [screen]
import fs from "fs";
import { createMock } from "./simmock.mjs";

const { chromium } = await import(process.env.PW_CORE || "playwright-core");
const BASE = process.env.BASE || "http://localhost:3197";
const OUT = process.env.OUT || "/private/tmp/claude-501/audit-shots";
const WIDTHS = (process.env.WIDTHS || "360,375,390,430").split(",").map(Number);
const THEMES = (process.env.THEMES || "dark,light").split(",");
const only = process.argv[2];
fs.mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.HOME + "/Library/Caches/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-mac-arm64/chrome-headless-shell" });
const session = { access_token: "a.b.c", refresh_token: "r", token_type: "bearer", expires_in: 99999, expires_at: Math.floor(Date.now() / 1000) + 99999, user: { id: "u1", aud: "authenticated", role: "authenticated", email: "t@example.com", app_metadata: {}, user_metadata: {}, created_at: "2026-01-01T00:00:00Z" } };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** Runs in the page: returns findings for the current DOM. */
const CHECKS = () => {
  const W = document.documentElement.clientWidth;
  const vis = (el) => { const r = el.getBoundingClientRect(); const cs = getComputedStyle(el); return r.width > 0 && r.height > 0 && cs.visibility !== "hidden" && cs.display !== "none" && cs.opacity !== "0"; };
  const label = (el) => (el.getAttribute("data-testid") ? `[${el.getAttribute("data-testid")}]` : "") + el.tagName.toLowerCase() + (el.className && typeof el.className === "string" ? "." + el.className.trim().split(/\s+/).slice(0, 2).join(".") : "");
  const text = (el) => (el.getAttribute("aria-label") || el.textContent || "").replace(/\s+/g, " ").trim().slice(0, 48);
  const out = { overflow: null, smallTargets: [], unnamed: [], truncated: [], tinyText: [], lowContrast: [], dialogsUnnamed: [], heights: {} };
  if (document.documentElement.scrollWidth > W + 1) out.overflow = { scrollWidth: document.documentElement.scrollWidth, width: W };
  const targets = [...document.querySelectorAll("button, a[href], [role=button], [role=tab], [role=checkbox], [role=switch], input:not([type=hidden]), select, textarea")].filter(vis);
  for (const el of targets) {
    const r = el.getBoundingClientRect();
    const h = Math.round(r.height);
    if (el.tagName === "BUTTON" || el.getAttribute("role") === "button") out.heights[h] = (out.heights[h] || 0) + 1;
    if ((r.height < 43.5 || r.width < 43.5) && !(el.tagName === "A" && el.closest("p, li") && r.height < 43.5 && el.textContent.trim().length > 12)) {
      out.smallTargets.push({ el: label(el), text: text(el), w: Math.round(r.width), h });
    }
    const name = (el.getAttribute("aria-label") || el.getAttribute("aria-labelledby") || el.getAttribute("title") || el.textContent || "").trim();
    if (!name && el.tagName !== "INPUT") out.unnamed.push({ el: label(el) });
    if (el.tagName === "INPUT" && !(el.getAttribute("aria-label") || el.id && document.querySelector(`label[for="${el.id}"]`) || el.getAttribute("placeholder") || el.closest("label"))) out.unnamed.push({ el: label(el) });
  }
  for (const el of document.querySelectorAll("*")) {
    if (!vis(el)) continue;
    const cs = getComputedStyle(el);
    if (el.children.length === 0 && el.textContent.trim()) {
      const size = parseFloat(cs.fontSize);
      if (size < 11.5) out.tinyText.push({ el: label(el), text: text(el), size });
      if ((cs.textOverflow === "ellipsis" || cs.webkitLineClamp !== "none") && el.scrollWidth > el.clientWidth + 1) out.truncated.push({ el: label(el), text: text(el) });
      if (el.scrollHeight > el.clientHeight + 2 && cs.webkitLineClamp && cs.webkitLineClamp !== "none") out.truncated.push({ el: label(el), text: text(el) });
    }
  }
  // contrast of leaf text vs the nearest composited background (page bg is the base)
  const parse = (c) => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(",").map((x) => parseFloat(x)); return { r: p[0], g: p[1], b: p[2], a: p[3] === undefined ? 1 : p[3] }; };
  const lum = ({ r, g, b }) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const over = (top, base) => ({ r: top.r * top.a + base.r * (1 - top.a), g: top.g * top.a + base.g * (1 - top.a), b: top.b * top.a + base.b * (1 - top.a), a: 1 });
  const bgOf = (el) => { const chain = []; for (let n = el; n; n = n.parentElement) { const c = parse(getComputedStyle(n).backgroundColor); if (c && c.a > 0) chain.push(c); if (c && c.a === 1) break; } let base = parse(getComputedStyle(document.body).backgroundColor) || { r: 0, g: 0, b: 0, a: 1 }; if (base.a < 1) base = { r: 12, g: 14, b: 18, a: 1 }; for (const c of chain.reverse()) base = over(c, base); return base; };
  const seen = new Set();
  for (const el of document.querySelectorAll("p, span, a, button, h1, h2, h3, h4, li, label, div")) {
    if (!vis(el) || el.children.length > 0 || !el.textContent.trim()) continue;
    const cs = getComputedStyle(el);
    const fg = parse(cs.color); if (!fg) continue;
    const bg = bgOf(el);
    const f = over(fg, bg);
    const l1 = lum(f), l2 = lum(bg);
    const ratio = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
    const size = parseFloat(cs.fontSize), bold = parseInt(cs.fontWeight, 10) >= 700;
    const need = size >= 24 || (size >= 18.66 && bold) ? 3 : 4.5;
    const key = text(el) + ratio.toFixed(1);
    if (ratio < need && !seen.has(key)) { seen.add(key); out.lowContrast.push({ el: label(el), text: text(el), ratio: Math.round(ratio * 100) / 100, need }); }
  }
  for (const d of document.querySelectorAll("[role=dialog]")) if (vis(d) && !(d.getAttribute("aria-label") || d.getAttribute("aria-labelledby"))) out.dialogsUnnamed.push({ el: label(d) });
  return out;
};

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
      results.push({ screen: name, width: w, theme, ...r });
      if (w === 390) await page.screenshot({ path: `${OUT}/${name.replace(/[^a-z0-9]+/gi, "-")}-${theme}-${w}.png` });
    };
    const click = async (loc) => { await loc.first().dispatchEvent("click"); await sleep(900); };
    const goTab = async (label) => { await click(page.getByTestId("sim-game-orb")); await click(page.getByTestId("sim-game-nav").getByRole("button", { name: new RegExp(`^${label}`) })); };
    await page.goto(`${BASE}/gm-game`, { waitUntil: "domcontentloaded" });
    await page.addStyleTag({ content: "nextjs-portal,[data-nextjs-toast]{display:none!important}" }).catch(() => {});
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
