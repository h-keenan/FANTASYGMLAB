// Bottom-chrome pin check (manual tool, not CI). Drives the Fantasy Sim in WebKit at an iPhone viewport,
// scrolls through a long page and asserts the sticky `.bottom-stack` stays glued to the visible bottom edge
// at every scroll offset, and that its containing block spans the whole document (the real cause of the
// "footer floats mid-screen" bug: a flex ancestor shrunk to one viewport so sticky ran out of parent).
// Usage: PW=/path/to/node_modules/playwright-core node footer_pin.mjs   (dev server on :3187)
import { createRequire } from "module";
import { createMock } from "./simmock.mjs";
const require = createRequire(import.meta.url);
const { webkit, chromium, devices } = require(process.env.PW || "playwright-core");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const session = { access_token: "a.b.c", refresh_token: "r", token_type: "bearer", expires_in: 99999, expires_at: Math.floor(Date.now() / 1000) + 99999,
  user: { id: "u1", aud: "authenticated", role: "authenticated", email: "t@example.com", app_metadata: {}, user_metadata: {}, created_at: "2026-01-01T00:00:00Z" } };
// WebKit is the target (iOS Safari). CHROME_PATH=... falls back to Chromium: the failure is a CSS layout one (sticky containing block), not an engine quirk.
const browser = process.env.CHROME_PATH ? await chromium.launch({ executablePath: process.env.CHROME_PATH }) : await webkit.launch();
const ctx = await browser.newContext({ ...devices["iPhone 14"], viewport: { width: 390, height: 664 } }); // 664 = 844 minus Safari top+bottom bars
await ctx.addInitScript(([t, s]) => { try { localStorage.setItem("fgl:theme-mode", t); localStorage.setItem("sb-dummy-auth-token", JSON.stringify(s)); localStorage.setItem("fgl:onboarding-complete", "1"); } catch (e) {} }, ["dark", session]);
const mock = createMock({ status: "in_season", week: 4 });
await ctx.route("**/*", async (route) => {
  const url = new URL(route.request().url());
  if (url.hostname === "localhost" && url.port === "8000") {
    const body = route.request().postData(); let json = null; try { json = body ? JSON.parse(body) : null; } catch {}
    const res = mock(route.request().method(), url.pathname, Object.fromEntries(url.searchParams.entries()), json);
    return route.fulfill({ status: res?.status ?? 200, contentType: "application/json", body: JSON.stringify(res?.body ?? {}), headers: { "access-control-allow-origin": "*" } });
  }
  if (url.hostname === "dummy.supabase.co") return route.fulfill({ status: 200, contentType: "application/json", body: "{}", headers: { "access-control-allow-origin": "*" } });
  return route.continue();
});
const page = await ctx.newPage();
await page.goto("http://localhost:3187/gm-game", { waitUntil: "domcontentloaded" });
await sleep(3000);
await page.getByRole("button", { name: /Continue|Open game/ }).first().click({ timeout: 8000 }).catch(() => {}); await sleep(1500);
await page.getByTestId("sim-game-orb").click(); await sleep(600);
await page.getByTestId("sim-game-nav").getByText("Players", { exact: true }).click(); await sleep(1500); // Players: the longest page
// Every sticky-bottom element (the .bottom-stack footer, the .bottom-rail GM orb) must (1) sit on the visible bottom
// edge at this scroll offset and (2) have a parent whose box reaches the end of the document: sticky is clamped to its
// parent, so a one-viewport-tall body or a shrunk flex column makes the bar scroll away mid-page.
const probe = () => page.evaluate(() => {
  const docH = document.documentElement.scrollHeight;
  const bars = [...document.querySelectorAll("*")].filter((e) => { const cs = getComputedStyle(e); return cs.position === "sticky" && cs.bottom !== "auto"; });
  return { scrollY: Math.round(scrollY), docH, vh: innerHeight, bars: bars.map((e) => { const r = e.getBoundingClientRect(), p = e.parentElement.getBoundingClientRect(); return { el: `${e.tagName}.${String(e.className).split(" ")[0]}`, bottomGap: Math.round(innerHeight - r.bottom), parentEndsAt: Math.round(p.bottom + scrollY) }; }) };
});
const rows = [];
const max = await page.evaluate(() => document.documentElement.scrollHeight - innerHeight);
for (const y of [0, 0.25, 0.5, 0.75, 1]) { await page.evaluate((v) => scrollTo(0, v), Math.round(max * y)); await sleep(300); rows.push(await probe()); if (process.env.SHOTS) await page.screenshot({ path: `${process.env.SHOTS}/pin-${Math.round(y*100)}.png` }); }
console.log(JSON.stringify(rows, null, 1));
const bad = rows.filter((r) => r.bars.length === 0 || r.bars.some((b) => Math.abs(b.bottomGap) > 1 || b.parentEndsAt < r.docH - 1));
console.log(bad.length ? `FAIL ${bad.length}/${rows.length}` : "PASS");
await browser.close();
process.exit(bad.length ? 1 : 0);
