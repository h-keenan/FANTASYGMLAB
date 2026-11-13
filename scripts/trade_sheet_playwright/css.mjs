import { openPage, tapAt } from "./repro.mjs";
const { page, ctx } = await openPage(390, 844);
const r = await page.evaluate(() => { const el = document.querySelector(".tps-side-open"); const cs = getComputedStyle(el); return { display: cs.display, pad: cs.padding, jc: cs.justifyContent }; });
console.log(r);
const sheets = await page.evaluate(() => [...document.styleSheets].map(s => { try { return [...s.cssRules].filter(r=>r.selectorText && r.selectorText.includes("tps-")).length } catch(e){ return "x" } }));
console.log(sheets);
await ctx.close(); process.exit(0);
