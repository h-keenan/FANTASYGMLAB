import { openPage, tapAt } from "./repro.mjs";
const { page, ctx } = await openPage(390, 844);
const count = async () => (await page.locator("button[aria-label^='Remove ']").count());
let taps = 0, adds = 0;
async function tap(loc, why) { taps++; const b = await count(); await tapAt(page, loc); const a = await count(); console.log(`tap ${taps} ${why}: assets ${b}->${a}`); }
// Add a player to RECEIVE, then another to SEND, scrolling as a user would.
await tap(page.getByRole("button", { name: "You receive" }).first(), "side receive");
const rows = page.locator("div.divide-y.max-h-80 button");
console.log("rows", await rows.count());
for (let i = 0; i < 4 && (await count()) < 1; i++) await tap(rows.first(), "first row");
await tap(page.getByRole("button", { name: "You send" }).first(), "side send");
for (let i = 0; i < 4 && (await count()) < 2; i++) await tap(page.locator("div.divide-y.max-h-80 button").first(), "first row");
console.log("total taps", taps, "errors", page.errors);
await ctx.close(); process.exit(0);
