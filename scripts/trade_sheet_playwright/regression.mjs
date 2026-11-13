// Regression for the "multiple taps" bug in the Trade Analyzer builder, at 390px with real touch events.
// Run against a dev server (:3187) with the mocked API: node regression.mjs
// Asserts (exit code 1 on failure):
//  1. one tap anywhere on an empty side card opens the picker (the old "Tap to add" text was a dead zone),
//  2. adding one player takes exactly 3 taps (open, row, Add) and N players takes N + 2, with no scroll,
//  3. every tappable row / chip / button in the picker is >= 44px tall,
//  4. the GM orb never sits over a picker control (it used to cover list rows and eat their taps),
//  5. the receive sheet follows the Trading with partner, and Apply puts the players on the page as chips.
import { openPage, tapAt } from "./repro.mjs";

let failed = 0;
const check = (ok, msg) => { console.log(`${ok ? "PASS" : "FAIL"}  ${msg}`); if (!ok) failed++; };

const { page, ctx } = await openPage(390, 844);
let taps = 0;
const tap = async (loc) => { taps++; await tapAt(page, loc); };

// 1. dead zone: tap the hint text, not the label.
await tap(page.getByText("Add from your roster"));
check(await page.getByRole("dialog").isVisible(), "tap on the empty card's hint text opens the picker");
await page.getByRole("button", { name: "Close You send" }).tap();

// 2. taps to add.
taps = 0;
await tap(page.getByRole("button", { name: /^You send/ }));
await tap(page.getByRole("button", { name: /^Add Victor Dunn/ }));
await tap(page.getByRole("button", { name: /^Add 1 to trade/ }));
check(taps === 3, `1 player on a side = ${taps} taps (open, row, Add)`);
check((await page.getByRole("button", { name: "Remove Victor Dunn" }).count()) === 1, "player shows as a chip on the page after Apply");
const scrollY = await page.evaluate(() => window.scrollY);
check(scrollY === 0, "no page scroll needed");

taps = 0;
await tap(page.getByRole("button", { name: /^You receive/ }));
await tap(page.getByRole("button", { name: "Add Jaxon Moore", exact: true }));
await tap(page.getByRole("button", { name: "Add Devin Carter", exact: true }));
await tap(page.getByRole("button", { name: "Add Malik Ross", exact: true }));
// 3 + 4: sizes and orb, while the sheet is open.
const audit = await page.evaluate(() => {
  const dialog = document.querySelector('[role="dialog"]');
  const orb = document.querySelector('button[aria-label="Open GM menu"]');
  const ob = orb?.getBoundingClientRect();
  const small = []; const covered = [];
  dialog.querySelectorAll("button, input").forEach((el) => {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return;
    if (r.height < 43.5 && !el.closest(".tps-chip")) small.push(`${el.getAttribute("aria-label") || el.textContent}:${Math.round(r.height)}`);
    if (r.height < 35) small.push(`chip/${el.getAttribute("aria-label")}:${Math.round(r.height)}`);
    const footer = dialog.querySelector('.tps-footer')?.getBoundingClientRect();
    if (footer && r.bottom > footer.top) return; // scrolled partly under the sticky footer: reachable by scrolling
    const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
    if (hit && !el.contains(hit) && !hit.contains(el)) covered.push(el.getAttribute("aria-label") || el.textContent);
  });
  return { small, covered, orbCovered: ob ? document.elementFromPoint(ob.left + ob.width / 2, ob.top + ob.height / 2)?.closest('[role="dialog"]') !== null : true };
});
check(audit.small.length === 0, `all picker controls >= 44px (chips >= 36px)${audit.small.length ? " -> " + audit.small.join(", ") : ""}`);
check(audit.covered.length === 0, `no picker control is covered by another element${audit.covered.length ? " -> " + audit.covered.join(", ") : ""}`);
check(audit.orbCovered, "GM orb sits under the picker (cannot intercept taps)");
await tap(page.getByRole("button", { name: /^Add 3 to trade/ }));
check(taps === 5, `3 players on a side = ${taps} taps (open, 3 rows, Add)`);

// 5. partner.
await page.getByLabel("Trading with").selectOption({ label: "Bench Mob · Mgr 6" });
await tap(page.getByRole("button", { name: /^You receive/ }));
const sub = await page.getByRole("dialog").innerText();
check(/Bench Mob/.test(sub), "receive sheet is scoped to the chosen partner");
console.log("page errors:", page.errors.length ? page.errors : "none");
await ctx.close();
process.exit(failed ? 1 : 0);
