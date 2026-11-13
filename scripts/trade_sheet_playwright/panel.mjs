import { openPage } from "./repro.mjs";
const { page, ctx } = await openPage(390, 844);
const btn = page.getByRole("button", { name: "You receive" }).first();
console.log("label button box", await btn.boundingBox());
const panel = page.locator(".glass-surface").nth(1);
const pb = await panel.boundingBox(); console.log("panel box", pb);
// tap the "Tap to add" text of the receive panel
const txt = page.getByText("Tap to add").nth(1);
const tb = await txt.boundingBox(); await page.touchscreen.tap(tb.x + tb.width / 2, tb.y + tb.height / 2); await page.waitForTimeout(300);
console.log("receive active after tapping 'Tap to add' text:", await page.evaluate(() => getComputedStyle(document.querySelectorAll(".glass-surface")[1]).borderColor));
await ctx.close(); process.exit(0);
