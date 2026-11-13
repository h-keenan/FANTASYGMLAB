// Player Compare v2 screenshots + checks. node compareshots.mjs [outDir]
import { openPage, tapAt } from "./repro.mjs";
const OUT = process.argv[2] || "/private/tmp/claude-501/tsp-shots";
let failed = 0;
const check = (ok, msg) => { console.log(`${ok ? "PASS" : "FAIL"}  ${msg}`); if (!ok) failed++; };
for (const [w, h] of [[390, 844], [1280, 900]]) {
  const touch = w < 600;
  const { page, ctx } = await openPage(w, h, { touch, url: "http://localhost:3187/player-compare/L1?name=Mock%20League&a=4001", ready: "[data-testid=compare-slot-b]" });
  const tap = (loc) => tapAt(page, loc);
  await page.waitForSelector("[data-testid=compare-slot-b]");
  await page.screenshot({ path: `${OUT}/c-empty-${w}.png` });
  await tap(page.getByRole("button", { name: "Player B: choose a player" }));
  await page.screenshot({ path: `${OUT}/c-sheet-${w}.png` });
  const hasFilter = await page.getByRole("button", { name: /^Filters \(1\)/ }).count();
  check(hasFilter === 1, `${w}: picker opens pre-filtered to the player's position`);
  await tap(page.getByRole("dialog").locator(".tps-row-main").first());
  check((await page.getByRole("dialog").count()) === 0, `${w}: one tap on a row chooses and closes`);
  await page.waitForSelector("[data-testid=compare-grid]");
  await page.waitForTimeout(1200);
  await page.screenshot({ path: `${OUT}/c-grid-${w}.png`, fullPage: true });
  await tap(page.getByRole("button", { name: /More stats/ }));
  await page.waitForTimeout(600);
  await page.screenshot({ path: `${OUT}/c-more-${w}.png`, fullPage: true });
  check(page.errors.length === 0, `${w}: no page errors ${page.errors.join(" | ")}`);
  await ctx.close();
}
process.exit(failed ? 1 : 0);
