// Smart-pill geometry guard (manual tool, like footer_pin.mjs). Builds a tiny harness of the REAL BottomTabBar / PillMorph +
// ui.css (vite, from web-next/node_modules), serves it, and measures at 390 and 360 wide: every control in the row (icon
// buttons, page-tab labels, the sliding capsule, the primary chip) must be centered on the row's vertical axis (within 1px)
// and the left / right padding of the row's content must be equal (within 1px).
// Usage: PW=/path/to/playwright-core CHROME_PATH=/path/to/chrome node scripts/sim_layout_playwright/pill_geometry.mjs
//   (WebKit is used when CHROME_PATH is unset and the webkit build is installed.)
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { mkdtempSync, readFileSync, writeFileSync, rmSync } from "node:fs";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const web = path.resolve(here, "../../web-next");
const out = mkdtempSync(path.join(tmpdir(), "pill-geo-"));
const require = createRequire(import.meta.url);
const { webkit, chromium, devices } = require(process.env.PW || "playwright-core");

// tokens: the :root blocks of globals.css (plain CSS; the file's tailwind import is not needed for the pill)
const g = readFileSync(path.join(web, "src/app/globals.css"), "utf8").split("\n");
const tokens = [...g.slice(12, 560), ...g.slice(g.findIndex((l) => l.includes("--motion-instant: 120ms")) - 1, g.findIndex((l) => l.includes("--motion-instant: 120ms")) + 8)].join("\n");
writeFileSync(path.join(here, "pill_harness/tokens.css"), tokens);
const N = (m) => path.join(web, "node_modules", m);
writeFileSync(
  path.join(out, "vite.config.mjs"),
  `export default { root: ${JSON.stringify(path.join(here, "pill_harness"))}, esbuild: { jsx: "automatic" }, define: { "process.env.NODE_ENV": '"development"' },
  build: { outDir: ${JSON.stringify(path.join(out, "dist"))}, emptyOutDir: true, minify: false }, cacheDir: ${JSON.stringify(path.join(out, ".vite"))},
  resolve: { alias: [
    { find: "next/link", replacement: ${JSON.stringify(path.join(here, "pill_harness/link.tsx"))} },
    { find: /^@\\//, replacement: ${JSON.stringify(path.join(web, "src") + "/")} },
    { find: /^react\\/jsx-dev-runtime$/, replacement: ${JSON.stringify(N("react/jsx-dev-runtime.js"))} },
    { find: /^react\\/jsx-runtime$/, replacement: ${JSON.stringify(N("react/jsx-runtime.js"))} },
    { find: /^react-dom\\/client$/, replacement: ${JSON.stringify(N("react-dom/client.js"))} },
    { find: /^react$/, replacement: ${JSON.stringify(N("react/index.js"))} },
    { find: /^react-dom$/, replacement: ${JSON.stringify(N("react-dom/index.js"))} } ] } };`,
);
execFileSync(N(".bin/vite"), ["build", "--config", path.join(out, "vite.config.mjs")], { stdio: "ignore" });
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
const browser = process.env.CHROME_PATH ? await chromium.launch({ executablePath: process.env.CHROME_PATH }) : await webkit.launch();

const measure = () => {
  const vis = (e) => getComputedStyle(e).visibility !== "hidden" && e.closest(".pill-layer") && getComputedStyle(e.closest(".pill-layer")).visibility !== "hidden";
  const layer = [...document.querySelectorAll(".pill-layer--context")].find(vis) || [...document.querySelectorAll(".pill-layer--global")].find(vis);
  const pill = layer.parentElement.closest(".bottom-tab-bar, .action-pill") || layer.parentElement;
  const pr = pill.getBoundingClientRect();
  const cs = getComputedStyle(pill);
  const inner = { top: pr.top + parseFloat(cs.borderTopWidth) + parseFloat(cs.paddingTop), bottom: pr.bottom - parseFloat(cs.borderBottomWidth) - parseFloat(cs.paddingBottom) };
  const midY = (inner.top + inner.bottom) / 2;
  const cy = (r) => r.top + r.height / 2;
  const items = [];
  layer.querySelectorAll(".pill-icon-btn, .pill-primary").forEach((e) => items.push({ what: e.className.split(" ").pop(), dy: cy(e.getBoundingClientRect()) - midY }));
  layer.querySelectorAll(".pill-tab").forEach((e) => {
    // the label text itself, not the element box: a link whose box is centered but whose text sits at the top is the bug
    const range = document.createRange(); range.selectNodeContents(e); const r = range.getBoundingClientRect();
    items.push({ what: "label:" + e.textContent, dy: cy(r) - midY });
  });
  const ind = layer.querySelector(".pill-indicator");
  const act = layer.querySelector('.pill-tab[aria-selected="true"]');
  let capsule = null;
  if (ind && act) { const a = ind.getBoundingClientRect(), b = act.getBoundingClientRect(); capsule = { dy: cy(a) - midY, dx: a.left + a.width / 2 - (b.left + b.width / 2), dw: a.width - b.width }; }
  const kids = [...layer.children].filter((k) => k.getBoundingClientRect().width > 0);
  const lr = layer.getBoundingClientRect();
  const first = kids[0].getBoundingClientRect(), last = kids[kids.length - 1].getBoundingClientRect();
  // the tab strip: its tabs must sit centered in it (equal space either side of the run of tabs, unless it scrolls)
  const strip = layer.querySelector(".pill-tabs");
  let stripPad = null;
  if (strip && strip.scrollWidth <= strip.clientWidth + 1) {
    const t = [...strip.querySelectorAll(".pill-tab")]; const s = strip.getBoundingClientRect();
    stripPad = { left: t[0].getBoundingClientRect().left - s.left, right: s.right - t[t.length - 1].getBoundingClientRect().right };
  }
  // Clipping: every tab label must sit inside the segment (the scroll strip) and clear of the primary chip. Scrolled tabs
  // (only allowed when the strip really overflows) are reachable, so there the check is the LIT tab plus "scrolls".
  const sr = strip ? strip.getBoundingClientRect() : null;
  const prim = layer.querySelector(".pill-primary");
  const clip = strip ? [...strip.querySelectorAll(".pill-tab")].map((e) => {
    const range = document.createRange(); range.selectNodeContents(e.querySelector(".pill-tab-text") || e); const r = range.getBoundingClientRect();
    return { label: e.textContent, active: e.getAttribute("aria-selected") === "true", left: r.left - sr.left, right: sr.right - r.right, overChip: prim ? r.right > prim.getBoundingClientRect().left + 0.5 : false, fullLabel: e.getAttribute("aria-label") };
  }) : [];
  return { dbg: strip ? { strip: strip.clientWidth, tabs: [...strip.querySelectorAll(".pill-tab")].map((e) => Math.round(e.getBoundingClientRect().width)), layer: layer.getBoundingClientRect().width, kids: [...layer.children].map((k) => Math.round(k.getBoundingClientRect().width)) } : null, clip, scrolls: strip ? strip.scrollWidth > strip.clientWidth + 1 : false, fade: strip ? !!strip.dataset.fade : false, primW: prim ? prim.getBoundingClientRect().width : 0, pillH: pr.height, items, capsule, padL: first.left - lr.left, padR: lr.right - last.right, stripPad, overflowX: document.documentElement.scrollWidth - innerWidth };
};

const cases = [["draft 4 + Auto-pick", "?family=draft"], ["draft 5 + Auto-pick", "?family=draft&draft=5"], ["trades + New trade", "?family=trades&primary=1"], ["team", "?family=team"], ["team + primary", "?family=team&primary=1"], ["trades", "?family=trades"], ["league", "?family=league"], ["sim bar", "?family=team&sim=1"]];
const rows = [];
let bad = 0;
for (const w of [390, 360]) {
  const ctx = await browser.newContext({ ...devices["iPhone 14"], viewport: { width: w, height: 664 } });
  const page = await ctx.newPage();
  for (const [name, qs] of cases) {
    await page.goto(base + qs, { waitUntil: "load" });
    await page.evaluate(() => document.fonts.ready);
    await sleep(500);
    const m = await page.evaluate(measure);
    const worst = Math.max(0, ...m.items.map((i) => Math.abs(i.dy)), m.capsule ? Math.abs(m.capsule.dy) : 0);
    const problems = [];
    if (worst > 1) problems.push(`vertical offset ${worst.toFixed(1)}px: ${m.items.filter((i) => Math.abs(i.dy) > 1).map((i) => `${i.what} ${i.dy.toFixed(1)}`).join(", ") || "capsule " + m.capsule.dy.toFixed(1)}`);
    if (m.capsule && (Math.abs(m.capsule.dx) > 1 || Math.abs(m.capsule.dw) > 1)) problems.push(`capsule not on its tab (dx ${m.capsule.dx.toFixed(1)}, dw ${m.capsule.dw.toFixed(1)})`);
    if (Math.abs(m.padL - m.padR) > 1) problems.push(`side padding ${m.padL.toFixed(1)} vs ${m.padR.toFixed(1)}`);
    if (m.stripPad && Math.abs(m.stripPad.left - m.stripPad.right) > 1.5) problems.push(`tab strip unbalanced ${m.stripPad.left.toFixed(1)} vs ${m.stripPad.right.toFixed(1)}`);
    const clipped = m.clip.filter((c) => c.left < -0.5 || c.right < -0.5 || c.overChip);
    // Up to 4 tabs at 390 must all fit; 5 tabs, or 360, may scroll (with the edge fade on) as long as the lit tab is fully shown.
    if (clipped.length && ((w >= 390 && m.clip.length <= 4) || !m.scrolls || !m.fade || clipped.some((c) => c.active))) problems.push(`label clipped: ${clipped.map((c) => `${c.label} (L${c.left.toFixed(1)} R${c.right.toFixed(1)}${c.overChip ? " under chip" : ""})`).join(", ")}`);
    if (m.overflowX > 0) problems.push(`page scrolls sideways by ${m.overflowX}px`);
    if (problems.length) bad++;
    rows.push({ w, case: name, dbg: m.dbg, scrolls: m.scrolls, primW: Math.round(m.primW), pillH: Math.round(m.pillH), worstDy: +worst.toFixed(2), capsule: m.capsule && { dy: +m.capsule.dy.toFixed(2), dx: +m.capsule.dx.toFixed(2) }, padL: +m.padL.toFixed(1), padR: +m.padR.toFixed(1), stripPad: m.stripPad, problems });
  }
  await ctx.close();
}
console.log(JSON.stringify(rows, null, 1));
console.log(bad ? `FAIL ${bad}` : "PASS");
await browser.close();
server.close();
rmSync(out, { recursive: true, force: true });
rmSync(path.join(here, "pill_harness/tokens.css"), { force: true });
process.exit(bad ? 1 : 0);
