import { openPage } from "./repro.mjs";
const { page, ctx } = await openPage(390, 844);
await page.getByRole("button", { name: "You receive" }).first().tap();
await page.waitForTimeout(300);
for (const y of [0, 300, 600]) {
  await page.evaluate((y) => window.scrollTo(0, y), y); await page.waitForTimeout(300);
  const res = await page.evaluate(() => {
    const out = [];
    document.querySelectorAll("div.divide-y.max-h-80 button").forEach((b) => {
      const r = b.getBoundingClientRect(); if (r.bottom < 0 || r.top > innerHeight) return;
      const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
      const el = document.elementFromPoint(cx, cy);
      out.push({ h: Math.round(r.height), top: Math.round(r.top), hit: b.contains(el) ? "row" : (el?.closest("[aria-label]")?.getAttribute("aria-label") || el?.tagName + "." + String(el?.className).slice(0, 40)) });
    });
    return out;
  });
  console.log("scrollY", y, JSON.stringify(res));
}
const fixed = await page.evaluate(() => [...document.querySelectorAll("*")].filter((e) => getComputedStyle(e).position === "fixed").map((e) => `${e.tagName}.${String(e.className).slice(0,50)} aria=${e.getAttribute("aria-label")} ${JSON.stringify(e.getBoundingClientRect().toJSON())}`));
console.log(fixed.join("\n"));
await ctx.close(); process.exit(0);
