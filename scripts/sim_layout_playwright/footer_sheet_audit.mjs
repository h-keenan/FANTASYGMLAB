// Footer + sheet audit (manual tool, like pill_geometry.mjs). Builds a harness of the REAL Fantasy Sim bar row (Sim to | game orb | Advance in the
// docked .action-pill), SimGameOrb, the shared Sheet and OverlayRuntime (vite, from web-next/node_modules) and checks, at 430x932, 390x844, 360x640
// and 320x568 (plus huge text), in Chromium iPhone emulation:
//  1. ORB: the circle holds only the brand mark (no text wider than the circle: "TRADES" used to clip on its rim), is >= 44px, the badge is not
//     clipped by the pill / screen, and nothing in the row overflows sideways.
//  2. BAR: Sim to, orb and Advance are each >= 44px tall and wide (hit targets), vertically centred on one row, Advance text fits, the page does
//     not scroll sideways, the pill sits above the safe area with the side inset on both sides.
//  3. SHEET (the "Fantasy Sim - Jump to any page" navigator): opens at its content height up to 88% of the screen, its bottom edge is the screen
//     bottom (it never floats above the footer), every row is reachable (fits, or the body scrolls to it), and it STILL does when the visual
//     viewport is stale-small with no keyboard (the iOS state that cropped it) -- while a focused text field in a sheet still lifts it above a real keyboard.
//  4. LAYERING: the scrim and the sheet are above the footer pill (hit test at the pill centre returns the sheet/scrim, never the pill).
//  Screenshots go to SHOT_DIR (default none).
// Usage: PW=/path/to/playwright-core CHROME_PATH=/path/to/chrome SHOT_DIR=dir node scripts/sim_layout_playwright/footer_sheet_audit.mjs
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { mkdtempSync, readFileSync, writeFileSync, rmSync } from "node:fs";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const web = path.resolve(here, "../../web-next");
const out = mkdtempSync(path.join(tmpdir(), "footer-audit-"));
const require = createRequire(import.meta.url);
const { chromium, devices } = require(process.env.PW || "playwright-core");

// Tailwind (the app's real utility classes: Button's min-h, max-md:*, ...) compiled for just the classes the harness components use.
const twRequire = createRequire(path.join(web, "package.json"));
const { compile } = twRequire("@tailwindcss/node");
const twSrc = ["src/components/Button.tsx", "src/components/SimGameOrb.tsx", "src/components/ui/Sheet.tsx", "src/components/ui/PillMorph.tsx"].map((f) => readFileSync(path.join(web, f), "utf8")).join(" ") + " " + readFileSync(path.join(here, "footer_harness/main.tsx"), "utf8");
const twCss = (await compile('@import "tailwindcss";', { base: web, onDependency() {} })).build([...new Set(twSrc.match(/[A-Za-z0-9_:\-\[\]\.\/%()]+/g))]);
writeFileSync(path.join(here, "footer_harness/tw.css"), twCss);
const g = readFileSync(path.join(web, "src/app/globals.css"), "utf8").split("\n");
const tokens = [...g.slice(12, 560), ...g.slice(g.findIndex((l) => l.includes("--motion-instant: 120ms")) - 1, g.findIndex((l) => l.includes("--motion-instant: 120ms")) + 8)].join("\n");
writeFileSync(path.join(here, "footer_harness/tokens.css"), tokens);
const N = (m) => path.join(web, "node_modules", m);
const stubs = path.join(here, "footer_harness/next-stubs.tsx");
writeFileSync(
  path.join(out, "vite.config.mjs"),
  `export default { root: ${JSON.stringify(path.join(here, "footer_harness"))}, esbuild: { jsx: "automatic" }, define: { "process.env.NODE_ENV": '"development"' },
  build: { outDir: ${JSON.stringify(path.join(out, "dist"))}, emptyOutDir: true, minify: false }, cacheDir: ${JSON.stringify(path.join(out, ".vite"))}, publicDir: ${JSON.stringify(path.join(web, "public"))},
  resolve: { alias: [
    { find: "next/link", replacement: ${JSON.stringify(path.join(here, "footer_harness/link.tsx"))} },
    { find: "next/image", replacement: ${JSON.stringify(stubs)} },
    { find: "next/navigation", replacement: ${JSON.stringify(stubs)} },
    { find: /^@\\//, replacement: ${JSON.stringify(path.join(web, "src") + "/")} },
    { find: /^react\\/jsx-dev-runtime$/, replacement: ${JSON.stringify(N("react/jsx-dev-runtime.js"))} },
    { find: /^react\\/jsx-runtime$/, replacement: ${JSON.stringify(N("react/jsx-runtime.js"))} },
    { find: /^react-dom\\/client$/, replacement: ${JSON.stringify(N("react-dom/client.js"))} },
    { find: /^react-dom$/, replacement: ${JSON.stringify(N("react-dom/index.js"))} },
    { find: /^react$/, replacement: ${JSON.stringify(N("react/index.js"))} } ] } };`,
);
const cleanup = () => { rmSync(out, { recursive: true, force: true }); rmSync(path.join(here, "footer_harness/tokens.css"), { force: true }); rmSync(path.join(here, "footer_harness/tw.css"), { force: true }); };
try { execFileSync(N(".bin/vite"), ["build", "--config", path.join(out, "vite.config.mjs")], { stdio: "ignore" }); } catch (e) { cleanup(); throw e; }
const dist = path.join(out, "dist");
const types = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".png": "image/png" };
const server = createServer((req, res) => {
  const p = path.join(dist, req.url.split("?")[0] === "/" ? "index.html" : req.url.split("?")[0]);
  let body = null;
  try { body = readFileSync(p); } catch { /* not found */ }
  if (!body) { res.writeHead(404); res.end(); return; }
  res.writeHead(200, { "content-type": types[path.extname(p)] || "text/plain" });
  res.end(body);
});
await new Promise((r) => server.listen(0, r));
const base = `http://localhost:${server.address().port}/`;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || undefined });

const measureBar = () => {
  const r = (e) => e.getBoundingClientRect();
  const pill = document.querySelector(".action-pill"), pr = r(pill);
  const simTo = document.querySelector('[data-testid="sim-to-button"]'), orb = document.querySelector('[data-testid="sim-game-orb"]'), adv = document.querySelector('[data-testid="advance"]');
  const badge = document.querySelector('[data-testid="sim-game-orb-badge"]');
  const orbR = r(orb);
  const textInOrb = [...orb.querySelectorAll("*")].filter((e) => e.textContent.trim() && e !== badge && !badge?.contains(e)).map((e) => e.textContent.trim());
  const midY = (e) => r(e).top + r(e).height / 2;
  const adT = (() => { const range = document.createRange(); range.selectNodeContents(adv); const x = range.getBoundingClientRect(); return { l: x.left - r(adv).left, r: r(adv).right - x.right }; })();
  const stCs = getComputedStyle(document.querySelector('[data-testid="stack"]'));
  return {
    pill: { l: pr.left, r: innerWidth - pr.right, top: pr.top, bottom: innerHeight - pr.bottom },
    simTo: { w: r(simTo).width, h: r(simTo).height, textFits: simTo.scrollWidth <= simTo.clientWidth + 1 },
    orb: { w: orbR.width, h: orbR.height, scrollOk: [...orb.querySelectorAll("img")].every((i) => r(i).left >= orbR.left && r(i).right <= orbR.right && r(i).top >= orbR.top && r(i).bottom <= orbR.bottom), text: textInOrb },
    adv: { w: r(adv).width, h: r(adv).height, textFits: adT.l >= -0.5 && adT.r >= -0.5 && adv.scrollWidth <= adv.clientWidth + 1 },
    rowDy: Math.max(Math.abs(midY(simTo) - midY(orb)), Math.abs(midY(adv) - midY(orb))),
    badge: badge ? { l: r(badge).left - pr.left, r: pr.right - r(badge).right, t: r(badge).top - pr.top, offR: innerWidth - r(badge).right } : null,
    order: r(simTo).right <= orbR.left + 0.5 && orbR.right <= r(adv).left + 0.5,
    overflowX: document.documentElement.scrollWidth - innerWidth,
    hit: (() => { const e = document.elementFromPoint(pr.left + pr.width / 2, pr.top + pr.height / 2); return !!e && pill.contains(e); })(),
  };
};
const measureSheet = () => {
  const sheet = document.querySelector(".ui-sheet"), body = sheet.querySelector(".ui-sheet-body");
  const sr = sheet.getBoundingClientRect(), br = body.getBoundingClientRect();
  const rows = [...body.querySelectorAll(".game-nav-row")];
  const lastRow = rows[rows.length - 1];
  const centerHit = (x, y) => { const e = document.elementFromPoint(x, y); return e && (e.closest(".ui-sheet") ? "sheet" : e.closest(".ui-sheet-backdrop") ? "scrim" : e.closest(".action-pill") ? "pill" : "page"); };
  const pr = document.querySelector(".action-pill").getBoundingClientRect();
  // scroll the body to the end: the last row must then be fully inside the sheet
  body.scrollTop = body.scrollHeight;
  const lr = lastRow ? lastRow.getBoundingClientRect() : null;
  return {
    h: sr.height, vh: innerHeight, bottomGap: innerHeight - sr.bottom, kb: getComputedStyle(document.documentElement).getPropertyValue("--kb-inset"),
    contentFits: body.scrollHeight <= body.clientHeight + 1, canScroll: body.scrollHeight > body.clientHeight + 1,
    lastRowInside: lr ? lr.bottom <= sr.bottom + 0.5 && lr.top >= sr.top : null,
    bottomEdgeHit: centerHit(innerWidth / 2, innerHeight - 2), pillHit: centerHit(pr.left + pr.width / 2, pr.top + pr.height / 2), above: br.top >= sr.top,
  };
};
const shot = async (page, name) => { if (process.env.SHOT_DIR) await page.screenshot({ path: path.join(process.env.SHOT_DIR, name), type: "png" }); };
// A visualViewport that reports a SHORTER viewport than the window although no keyboard is up (the stale iOS state).
const staleViewport = (cut) => {
  const vv = { get height() { return innerHeight - cut; }, offsetTop: 0, offsetLeft: 0, scale: 1, width: innerWidth, pageTop: 0, pageLeft: 0, addEventListener() {}, removeEventListener() {} };
  Object.defineProperty(window, "visualViewport", { value: vv, configurable: true });
};

let bad = 0; const rows = [];
const VIEWPORTS = [[430, 932], [390, 844], [360, 640], [320, 568]];
for (const [w, h] of VIEWPORTS) for (const big of [false, true]) {
  const ctx = await browser.newContext({ ...devices["iPhone 14"], viewport: { width: w, height: h } });
  const page = await ctx.newPage();
  if (process.env.DEBUG_PAGE) page.on("pageerror", (e) => console.log("pageerror", e.message)).on("console", (m) => m.type() === "error" && console.log("console", m.text().slice(0, 300)));
  const q = big ? "?big=1&tab=players" : "?tab=trades";
  await page.goto(base + q, { waitUntil: "load" });
  await page.evaluate(() => document.fonts.ready);
  await sleep(500);
  const bar = await page.evaluate(measureBar);
  const problems = [];
  if (bar.orb.text.length) problems.push(`orb carries text ${JSON.stringify(bar.orb.text)} (clipped on the circle rim); it must be the brand mark only`);
  if (!bar.orb.scrollOk) problems.push("orb content overflows its circle");
  for (const [n, o] of [["Sim to", bar.simTo], ["orb", bar.orb], ["Advance", bar.adv]]) { if (o.h < 43.5 || o.w < 43.5) problems.push(`${n} hit target ${o.w.toFixed(0)}x${o.h.toFixed(0)} < 44px`); }
  if (!bar.simTo.textFits) problems.push("Sim to label overflows its button");
  if (!bar.adv.textFits && !big) problems.push("Advance label overflows its button");
  if (bar.rowDy > 1.5) problems.push(`row not centred (orb vs neighbours ${bar.rowDy.toFixed(1)}px)`);
  if (!bar.order) problems.push("Sim to / orb / Advance overlap or are out of order");
  if (bar.badge && (bar.badge.offR < 0 || bar.badge.t < -1 || bar.badge.r < -1)) problems.push(`orb badge pokes out of the pill/screen (${JSON.stringify(bar.badge)})`);
  if (bar.overflowX > 0) problems.push(`page scrolls sideways by ${bar.overflowX}px`);
  if (Math.abs(bar.pill.l - bar.pill.r) > 1) problems.push(`pill side insets ${bar.pill.l} vs ${bar.pill.r}`);
  if (!bar.hit) problems.push("pill is covered (hit test at its centre is not the pill)");
  await shot(page, `footer-bar-${w}${big ? "-bigtext" : ""}.png`);
  // sheet: normal, then with a stale-small visual viewport and NO keyboard
  const sheetCases = big ? [["open", false]] : [["open", false], ["stale visual viewport, no keyboard", true]];
  const sheetRes = {};
  for (const [label, stale] of sheetCases) {
    const p2 = await ctx.newPage();
    if (stale) await p2.addInitScript(staleViewport, Math.round(h * 0.45));
    await p2.goto(base + q, { waitUntil: "load" });
    await p2.evaluate(() => document.fonts.ready);
    await p2.click('[data-testid="sim-game-orb"]');
    await sleep(500);
    const s = await p2.evaluate(measureSheet);
    sheetRes[label] = { h: Math.round(s.h), pct: +(s.h / s.vh * 100).toFixed(0), kb: s.kb };
    if (Math.abs(s.bottomGap) > 1) problems.push(`[${label}] sheet bottom is ${s.bottomGap.toFixed(0)}px above the screen bottom (it must sit on the bottom edge)`);
    if (!s.lastRowInside) problems.push(`[${label}] last row cropped (not reachable inside the sheet)`);
    if (!s.contentFits && !s.canScroll) problems.push(`[${label}] sheet crops content without scrolling`);
    if (s.bottomEdgeHit !== "sheet") problems.push(`[${label}] screen-bottom hit test is "${s.bottomEdgeHit}", not the sheet`);
    if (s.pillHit === "pill") problems.push(`[${label}] footer pill is above the open sheet/scrim`);
    // a content-sized sheet is as tall as its content up to 88%; with a 568-640px screen the full list scrolls
    if (!s.contentFits && s.h < s.vh * 0.85 - 1) problems.push(`[${label}] sheet is only ${(s.h / s.vh * 100).toFixed(0)}% of the screen although its content needs more`);
    await shot(p2, `footer-sheet-${w}${stale ? "-stale-vv" : ""}${big ? "-bigtext" : ""}.png`);
    await p2.close();
  }
  if (!big) {
    // control: a focused text field in a sheet DOES lift it above a real keyboard (visual viewport shorter AND a field focused)
    const p3 = await ctx.newPage();
    await p3.addInitScript(staleViewport, Math.round(h * 0.4));
    await p3.goto(base + "?sheet=search", { waitUntil: "load" });
    await p3.evaluate(() => document.fonts.ready);
    await sleep(300);
    const before = await p3.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue("--kb-inset"));
    await p3.focus('[data-testid="sheet-search"]');
    await sleep(700);
    const after = await p3.evaluate(() => ({ kb: getComputedStyle(document.documentElement).getPropertyValue("--kb-inset"), gap: innerHeight - document.querySelector(".ui-sheet").getBoundingClientRect().bottom }));
    if (process.env.DEBUG_PAGE) console.log("kb debug", before, JSON.stringify(after), await p3.evaluate(() => [document.activeElement?.tagName, window.visualViewport.height, innerHeight]));
    if (parseFloat(before) !== 0) problems.push(`--kb-inset is ${before} with no field focused`);
    if (!(parseFloat(after.kb) > 0 && after.gap > 40)) problems.push(`a focused field does not lift the sheet above the keyboard (kb ${after.kb}, gap ${after.gap})`);
    await p3.close();
  }
  if (problems.length) bad++;
  rows.push({ viewport: `${w}x${h}${big ? " big text" : ""}`, orb: `${bar.orb.w.toFixed(0)}px`, simTo: `${bar.simTo.w.toFixed(0)}x${bar.simTo.h.toFixed(0)}`, advance: `${bar.adv.w.toFixed(0)}x${bar.adv.h.toFixed(0)}`, pillBottomGap: bar.pill.bottom, sheet: sheetRes, problems });
  await ctx.close();
}
console.log(JSON.stringify(rows, null, 1));
console.log(bad ? `FAIL ${bad}` : "PASS");
await browser.close(); server.close(); cleanup();
process.exit(bad ? 1 : 0);
