// 390px mid-state screenshots of the shared Presence on a Fantasy Sim notice (auto-set toast): entering, at rest, auto-dismiss
// exit (collapsing away), gone. Also records the measured heights so a pop (0 -> full in one frame) would show. Manual tool.
//   PW_CORE=... BASE=http://localhost:3187 OUT=/tmp/shots node scripts/sim_layout_playwright/presence_toast.mjs
import fs from "fs";
import { createMock } from "./simmock.mjs";

const { chromium } = await import(process.env.PW_CORE || "playwright-core");
const BASE = process.env.BASE || "http://localhost:3187";
const OUT = process.env.OUT || "/private/tmp/claude-501/presence-shots";
fs.mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || process.env.HOME + "/Library/Caches/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-mac-arm64/chrome-headless-shell" });
const session = { access_token: "a.b.c", refresh_token: "r", token_type: "bearer", expires_in: 99999, expires_at: Math.floor(Date.now() / 1000) + 99999, user: { id: "u1", aud: "authenticated", role: "authenticated", email: "t@example.com", app_metadata: {}, user_metadata: {}, created_at: "2026-01-01T00:00:00Z" } };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
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
await sleep(3000);
const state = () => page.evaluate(() => {
  const el = document.querySelector('[data-testid="sim-notice"]');
  return el ? { phase: el.getAttribute("data-presence"), h: Math.round(el.getBoundingClientRect().height), opacity: getComputedStyle(el).opacity, text: (el.textContent || "").slice(0, 50) } : null;
});
const t0 = Date.now();
const log = [];
const sample = async (label) => { const s = await state(); log.push({ at: Date.now() - t0, label, ...s }); console.log(label, JSON.stringify(s)); };
await page.getByRole("button", { name: /Auto-set/ }).first().dispatchEvent("click");
await page.waitForSelector('[data-testid="sim-notice"]', { timeout: 15000 });
await sample("enter+0");
await page.screenshot({ path: `${OUT}/notice-1-entering.png` });
await sleep(120); await sample("enter+120");
await sleep(400); await sample("rest");
await page.screenshot({ path: `${OUT}/notice-2-rest.png` });
// The notice auto-dismisses after ~4s (noticeDismissMs "success"), then plays its exit (180ms) and unmounts.
for (let i = 0; i < 60; i++) {
  const s = await state();
  if (s && s.phase === "exiting") { await sample("exit+0"); await page.screenshot({ path: `${OUT}/notice-3-exiting.png` }); await sleep(60); await sample("exit+60"); break; }
  await sleep(100);
}
await sleep(400); await sample("after");
await page.screenshot({ path: `${OUT}/notice-4-gone.png` });
const phases = log.map((l) => l.phase);
const ok = phases.includes("entering") && phases.includes("exiting") && log[log.length - 1].phase == null;
console.log(ok ? "PASS notice entered, auto-dismissed through an exit, and unmounted" : "FAIL");
await browser.close();
process.exit(ok ? 0 : 1);
