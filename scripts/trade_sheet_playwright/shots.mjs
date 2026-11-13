import { openPage, tapAt } from "./repro.mjs";
const OUT = process.argv[2] || "/private/tmp/claude-501/tsp-shots";
for (const [w, h] of [[390, 844], [1280, 900]]) {
  const { page, ctx } = await openPage(w, h, { touch: w < 600 });
  const tap = (loc) => tapAt(page, loc);
  await tap(page.getByRole("button", { name: /^You send/ }).first());
  await tap(page.getByRole("button", { name: /^Add Jaxon Moore|^Add .*/ }).nth(0));
  await tap(page.getByRole("button", { name: /^Add / }).nth(1));
  await tap(page.getByRole("button", { name: /^Filters/ }));
  await page.screenshot({ path: `${OUT}/s-filters-${w}.png` });
  await tap(page.getByRole("button", { name: "RB", exact: true }));
  await tap(page.getByRole("button", { name: "Injured" }));
  await tap(page.getByRole("button", { name: "Apply" }));
  await page.screenshot({ path: `${OUT}/s-applied-${w}.png` });
  await tap(page.getByRole("tab", { name: /Picks/ }));
  await page.screenshot({ path: `${OUT}/s-picks-${w}.png` });
  await ctx.close();
}
process.exit(0);
