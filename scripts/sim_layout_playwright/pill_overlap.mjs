// Shared PillRow check: no tab's label overflows its box and no two tabs of one strip overlap (the League Recaps "S WEEK W9EEK 8" bug).
//   PW_CORE=... CHROME=... BASE=http://localhost:3197 [PATH_=/design] node scripts/sim_layout_playwright/pill_overlap.mjs
const { chromium } = await import(process.env.PW_CORE || "playwright-core");
const BASE = process.env.BASE || "http://localhost:3197";
const browser = await chromium.launch({ executablePath: process.env.CHROME || process.env.HOME + "/Library/Caches/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-mac-arm64/chrome-headless-shell" });
let bad = 0;
for (const w of [320, 360, 390, 430]) {
  const ctx = await browser.newContext({ viewport: { width: w, height: 844 }, isMobile: true, hasTouch: true });
  const page = await ctx.newPage();
  await page.goto(`${BASE}${process.env.PATH_ || "/design"}`, { waitUntil: "domcontentloaded", timeout: 90000 });
  await page.waitForTimeout(6000);
  const res = await page.evaluate(() => {
    const out = [];
    for (const list of document.querySelectorAll('[role="tablist"]')) {
      const tabs = [...list.querySelectorAll('[role="tab"]')];
      const boxes = tabs.map((t) => t.getBoundingClientRect());
      tabs.forEach((t, i) => {
        if (t.scrollWidth > t.clientWidth + 1) out.push(`overflow "${t.textContent.trim()}" ${t.scrollWidth}>${t.clientWidth}`);
        if (i > 0 && boxes[i].left < boxes[i - 1].right - 1) out.push(`overlap "${tabs[i - 1].textContent.trim()}" / "${t.textContent.trim()}"`);
      });
    }
    return out;
  });
  console.log(w, res.length ? res.slice(0, 6) : "ok");
  bad += res.length;
  await ctx.close();
}
await browser.close();
process.exit(bad ? 1 : 0);
