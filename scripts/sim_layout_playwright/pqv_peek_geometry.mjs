// PQV peek geometry guard (manual tool, like pill_geometry.mjs). Builds a tiny harness of the REAL PlayerQuickView (no remote
// fetches) + the real globals.css rules (vite, from web-next/node_modules) and measures at 390x844 and 360x640:
//  - at PEEK: the pill tab row (Overview / Stats / ...) is fully inside the sheet's visible area, each tab tappable
//    (hit-test at its centre returns the tab), the avatar is the compact 56px, and the sheet is as tall as the content needs
//    (header + tab row + one content line, 40-70% of the screen);
//  - at FULL: the big 112px avatar and the three stat tiles are back;
//  - the peek -> full change animates (an in-between avatar size is observed, no jump).
// Usage: PW=/path/to/playwright-core CHROME_PATH=/path/to/chrome node scripts/sim_layout_playwright/pqv_peek_geometry.mjs
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { mkdtempSync, readFileSync, writeFileSync, rmSync } from "node:fs";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const web = path.resolve(here, "../../web-next");
const out = mkdtempSync(path.join(tmpdir(), "pqv-geo-"));
const require = createRequire(import.meta.url);
const { chromium, devices } = require(process.env.PW || "playwright-core");

// globals.css without tailwind (its @import and the @theme block): the plain rules are all the sheet needs
const g = readFileSync(path.join(web, "src/app/globals.css"), "utf8").split("\n");
const themeStart = g.findIndex((l) => l.startsWith("@theme inline"));
let themeEnd = themeStart; while (g[themeEnd] !== "}") themeEnd++;
writeFileSync(path.join(here, "pqv_harness/globals.css"), g.filter((_, i) => i > 0 && (i < themeStart || i > themeEnd)).join("\n"));
const N = (m) => path.join(web, "node_modules", m);
const stubs = path.join(here, "pqv_harness/next-stubs.tsx");
writeFileSync(
  path.join(out, "vite.config.mjs"),
  `export default { root: ${JSON.stringify(path.join(here, "pqv_harness"))}, esbuild: { jsx: "automatic" }, define: { "process.env.NODE_ENV": '"development"', "process.env.NEXT_PUBLIC_SUPABASE_URL": '"http://localhost:1"', "process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY": '"x"', "process.env.NEXT_PUBLIC_API_BASE_URL": '"http://localhost:1"' },
  build: { outDir: ${JSON.stringify(path.join(out, "dist"))}, emptyOutDir: true, minify: false }, cacheDir: ${JSON.stringify(path.join(out, ".vite"))},
  resolve: { alias: [
    { find: "next/link", replacement: ${JSON.stringify(path.join(here, "pill_harness/link.tsx"))} },
    { find: "next/dynamic", replacement: ${JSON.stringify(stubs)} },
    { find: "next/navigation", replacement: ${JSON.stringify(stubs)} },
    { find: /^@\\//, replacement: ${JSON.stringify(path.join(web, "src") + "/")} },
    { find: /^react\\/jsx-dev-runtime$/, replacement: ${JSON.stringify(N("react/jsx-dev-runtime.js"))} },
    { find: /^react\\/jsx-runtime$/, replacement: ${JSON.stringify(N("react/jsx-runtime.js"))} },
    { find: /^react-dom\\/client$/, replacement: ${JSON.stringify(N("react-dom/client.js"))} },
    { find: /^react$/, replacement: ${JSON.stringify(N("react/index.js"))} },
    { find: /^react-dom$/, replacement: ${JSON.stringify(N("react-dom/index.js"))} } ] } };`,
);
const cleanup = () => { rmSync(out, { recursive: true, force: true }); rmSync(path.join(here, "pqv_harness/globals.css"), { force: true }); };
try { execFileSync(N(".bin/vite"), ["build", "--config", path.join(out, "vite.config.mjs")], { stdio: "ignore" }); } catch (e) { cleanup(); throw e; }
const dist = path.join(out, "dist");
const types = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css" };
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
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH });

const measure = () => {
  const modal = document.querySelector(".pqv-modal");
  const m = modal.getBoundingClientRect();
  const inset = parseFloat(getComputedStyle(modal).paddingBottom) || 0;
  const tabs = [...modal.querySelectorAll('[role="tab"]')];
  const hit = tabs.map((t) => { const r = t.getBoundingClientRect(); const e = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2); return { label: t.textContent, top: r.top - m.top, bottom: m.bottom - inset - r.bottom, left: r.left, right: innerWidth - r.right, tappable: !!e && (e === t || t.contains(e)) }; });
  const av = modal.querySelector(".pqv-avatar-glow")?.getBoundingClientRect();
  const tiles = modal.querySelector(".pqv-stat-tiles"), tr = tiles && tiles.getBoundingClientRect();
  const strip = modal.querySelector(".tabs-sticky")?.getBoundingClientRect();
  return { snap: modal.dataset.snap, modalH: m.height, modalBottom: m.bottom, vh: innerHeight, inset, tabs: hit, avatar: av ? av.width : null, tilesVisible: !!tr && tr.height > 4 && getComputedStyle(tiles.parentElement).opacity !== "0", stripBottom: strip ? strip.bottom - m.top : null, peekVar: modal.style.getPropertyValue("--pqv-peek-h") };
};

let bad = 0; const rows = [];
for (const [w, h] of [[390, 844], [360, 640]]) {
  const ctx = await browser.newContext({ ...devices["iPhone 14"], viewport: { width: w, height: h } });
  const page = await ctx.newPage();
  if (process.env.DEBUG_PAGE) page.on("pageerror", (e) => console.log("pageerror", e.message)).on("console", (m) => m.type() === "error" && console.log("console", m.text().slice(0, 300)));
  await page.goto(base, { waitUntil: "load" });
  await page.evaluate(() => document.fonts.ready);
  await sleep(900);
  const peek = await page.evaluate(measure);
  if (process.env.SHOT_DIR) await page.screenshot({ path: path.join(process.env.SHOT_DIR, `pqv-peek-${w}.jpg`), type: "jpeg", quality: 60 });
  const problems = [];
  if (peek.snap !== "peek") problems.push(`opened at ${peek.snap}`);
  if (!peek.tabs.length) problems.push("no pill tabs");
  for (const t of peek.tabs) {
    if (t.bottom < -0.5) problems.push(`tab ${t.label} clipped at the sheet bottom by ${(-t.bottom).toFixed(1)}px`);
    if (t.left < -0.5 || t.right < -0.5) problems.push(`tab ${t.label} off screen sideways`);
    if (!t.tappable) problems.push(`tab ${t.label} not tappable (covered)`);
  }
  if (peek.stripBottom != null && peek.modalH - peek.inset - peek.stripBottom < 40) problems.push(`no content line under the tabs (${(peek.modalH - peek.inset - peek.stripBottom).toFixed(0)}px)`);
  if (Math.abs(peek.avatar - 56) > 1) problems.push(`compact avatar ${peek.avatar}px, want 56`);
  if (peek.tilesVisible) problems.push("stat tiles still visible at peek");
  if (peek.modalH < peek.vh * 0.4 - 1 || peek.modalH > peek.vh * 0.7 + 1) problems.push(`peek height ${peek.modalH} outside 40-70% of ${peek.vh}`);
  // expand: tap the grip, sample the avatar through the animation
  await page.evaluate(() => document.querySelector(".pqv-modal .sheet-handle").dispatchEvent(new MouseEvent("click", { bubbles: true })));
  const samples = [];
  for (let i = 0; i < 12; i++) { samples.push(await page.evaluate(() => document.querySelector(".pqv-avatar-glow").getBoundingClientRect().width)); await sleep(30); }
  await sleep(500);
  const full = await page.evaluate(measure);
  if (process.env.SHOT_DIR) await page.screenshot({ path: path.join(process.env.SHOT_DIR, `pqv-full-${w}.jpg`), type: "jpeg", quality: 60 });
  if (full.snap !== "full") problems.push(`did not expand (${full.snap})`);
  if (Math.abs(full.avatar - 112) > 1) problems.push(`full avatar ${full.avatar}px, want 112`);
  if (!full.tilesVisible) problems.push("stat tiles missing at full");
  if (!samples.some((s) => s > 58 && s < 110)) problems.push(`avatar jumped (samples ${samples.map(Math.round).join(",")})`);
  // and back
  await page.evaluate(() => document.querySelector(".pqv-modal .sheet-handle").dispatchEvent(new MouseEvent("click", { bubbles: true })));
  await sleep(900);
  const back = await page.evaluate(measure);
  for (const t of back.tabs) if (t.bottom < -0.5 || !t.tappable) problems.push(`after full -> peek: tab ${t.label} clipped/covered`);
  if (problems.length) bad++;
  rows.push({ viewport: `${w}x${h}`, peekH: Math.round(peek.modalH), peekPct: +(peek.modalH / peek.vh * 100).toFixed(1), tabsBottomGap: peek.tabs.length ? +Math.min(...peek.tabs.map((t) => t.bottom)).toFixed(1) : null, stripBottom: Math.round(peek.stripBottom), avatarPeek: peek.avatar, avatarFull: full.avatar, problems });
  await ctx.close();
}
console.log(JSON.stringify(rows, null, 1));
console.log(bad ? `FAIL ${bad}` : "PASS");
await browser.close(); server.close(); cleanup();
process.exit(bad ? 1 : 0);
