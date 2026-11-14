// Geometry guard for the sticky sheet tab strip (docs/ui-patterns.md "Sheet tabs"). Real CSS rules from globals.css
// (.pqv-scroll, .tabs-sticky) + the real offset math (lib/sheetTabs.ts) in a 390x844 fixture shaped like the PQV:
// a close X floating over a padded scroll container. Asserts at several scroll positions, at a peek-height and a full
// sheet: strip top == chrome bottom (within 1px) and that every sampled point above the strip (inside the sheet)
// is the strip's opaque backing / chrome, never scrolled content.
//   node --experimental-strip-types scripts/sim_layout_playwright/sheet_tabs_dock.mjs   (PW_CORE=path to playwright-core)
import fs from "node:fs";
import { stickyTabsOffset, chromeDock } from "../../web-next/src/lib/sheetTabs.ts";

const { chromium } = await import(process.env.PW_CORE || "playwright-core");
const css = fs.readFileSync(new URL("../../web-next/src/app/globals.css", import.meta.url), "utf8");
const rule = (sel) => { const m = css.match(new RegExp("(^|\\n)" + sel.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + " \\{[^}]*\\}")); if (!m) throw new Error("missing rule " + sel); return m[0]; };
const rules = [".pqv-scroll", ".tabs-sticky", ".tabs-sticky::before"].map(rule).join("\n");
const exe = process.env.CHROMIUM || process.env.HOME + "/Library/Caches/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-mac-arm64/chrome-headless-shell";
const browser = await chromium.launch({ executablePath: fs.existsSync(exe) ? exe : undefined });
let failed = 0;
for (const sheetH of [475, 338, 777]) { // ~56% and ~92% of 844
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  await page.setContent(`<style>:root{--space-lg:1rem;--space-xl:1.25rem;--color-surface-primary:#1f2226;--color-border:#444}body{margin:0;background:#000}
${rules}
.sheet{position:fixed;left:0;right:0;bottom:0;height:${sheetH}px;display:flex;flex-direction:column;background:#1f2226}
.pqv-scroll{flex:1;min-height:0;max-height:none}.x{position:absolute;top:16px;right:16px;width:36px;height:36px;z-index:2;background:#555}
.tabs-sticky::before{pointer-events:auto}/* so elementFromPoint can see the mask */
.hero,.wrap{flex-shrink:0}.hero{height:180px;background:#a33}.panel{height:1500px;background:#363}.wrap{display:flex;flex-direction:column;gap:12px}</style>
<div class="sheet"><button class="x" id="x">x</button><div class="pqv-scroll" id="sc"><div class="hero" id="hero">hero</div>
<div class="wrap"><div class="tabs-sticky" id="strip"><div style="height:36px;background:#246">tabs</div></div><div class="panel">panel</div></div></div></div>`);
  const dock = chromeDock(...(await page.evaluate(() => [document.getElementById("x").getBoundingClientRect().bottom, document.getElementById("sc").getBoundingClientRect().top])));
  const pad = await page.evaluate(() => parseFloat(getComputedStyle(document.getElementById("sc")).paddingTop));
  const { top, mask } = stickyTabsOffset(pad, dock);
  await page.evaluate(([t, m]) => { const s = document.getElementById("strip"); s.style.setProperty("--tabs-top", t + "px"); s.style.setProperty("--tabs-mask", m + "px"); }, [top, mask]);
  for (const y of [0, 120, 400, 900]) {
    await page.evaluate((v) => (document.getElementById("sc").scrollTop = v), y);
    const r = await page.evaluate(() => {
      const sc = document.getElementById("sc").getBoundingClientRect();
      const st = document.getElementById("strip").getBoundingClientRect();
      const x = document.getElementById("x").getBoundingClientRect();
      const pts = [];
      for (let py = Math.ceil(sc.top) + 1; py < st.top - 1; py += 3) {
        const el = document.elementFromPoint(40, py); // left of the X, above the strip
        pts.push(el && (el.id === "strip" || el.closest("#strip")) ? "strip" : el && el.className || el?.tagName);
      }
      return { stripTop: st.top, scTop: sc.top, xBottom: x.bottom, pts };
    });
    const want = r.scTop + dock;
    const pinnedNow = Math.abs(r.stripTop - want) <= 1;
    // Scrolled far enough that the strip must be docked: top == chrome bottom (+-1px) and nothing but the strip's
    // own opaque backing above it. Before that it must never sit ABOVE the dock line.
    const leaks = pinnedNow ? r.pts.filter((p) => p !== "strip" && p !== "pqv-scroll") : [];
    const ok = y >= 300 ? pinnedNow && leaks.length === 0 : r.stripTop >= want - 1 && leaks.length === 0;
    if (!ok) { failed++; console.error("FAIL", { sheetH, y, dock, ...r, leaks }); }
    else console.log("ok", { sheetH, y, stripTop: r.stripTop, expected: r.scTop + dock });
  }
  await page.close();
}
await browser.close();
process.exit(failed ? 1 : 0);
