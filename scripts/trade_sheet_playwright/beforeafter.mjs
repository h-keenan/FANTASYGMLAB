// Same user task on the old (PORT=3188, origin/main) and new builder: add one player to You receive, at 390 (touch) and 1280.
import { openPage, tapAt } from "./repro.mjs";
const OUT = process.argv[2] || "/private/tmp/claude-501/tsp-shots";
const label = process.env.LABEL || "run";
for (const [w, h] of [[390, 844], [1280, 900]]) {
  const { page, ctx } = await openPage(w, h, { touch: w < 600 });
  await page.screenshot({ path: `${OUT}/ba-${label}-start-${w}.png` });
  if (label === "before") {
    await tapAt(page, page.getByRole("button", { name: "You receive" }).first());
    await tapAt(page, page.locator("div.divide-y.max-h-80 button").first());
    await tapAt(page, page.getByRole("button", { name: "You send" }).first());
    await tapAt(page, page.locator("div.divide-y.max-h-80 button").first());
  } else {
    await tapAt(page, page.getByRole("button", { name: /^You receive/ }));
    await tapAt(page, page.getByRole("button", { name: "Add Jaxon Moore", exact: true }));
    await tapAt(page, page.getByRole("button", { name: /^Add 1 to trade/ }));
    await tapAt(page, page.getByRole("button", { name: /^You send/ }));
    await tapAt(page, page.getByRole("button", { name: /^Add Victor Dunn/ }));
    await tapAt(page, page.getByRole("button", { name: /^Add 1 to trade/ }));
  }
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${OUT}/ba-${label}-two-assets-${w}.png`, fullPage: true });
  console.log(label, w, "page height", await page.evaluate(() => document.documentElement.scrollHeight));
  await ctx.close();
}
process.exit(0);
