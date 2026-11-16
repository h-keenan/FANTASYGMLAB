// Composes the captured Fantasy Sim screenshots into social ad creatives (device frame + branded gradient + headline +
// the FantasyDesk wordmark from web-next/public). Used by sim_social_ads.mjs.
import fs from "fs";
import path from "path";

export const SIZES = {
  feed: { w: 1080, h: 1080, file: "1080x1080" },
  story: { w: 1080, h: 1920, file: "1080x1920" },
};
const dataUri = (file) => `data:image/png;base64,${fs.readFileSync(file).toString("base64")}`;

export function creativeHtml(scene, kind, shot, logo) {
  const feed = kind === "feed";
  const phone = feed ? { w: 500, top: 70, left: 540 } : { w: 640, top: 760, left: 220 };
  const head = scene.headline.map((l) => `<span>${l}</span>`).join("");
  return `<!doctype html><html><head><meta charset="utf-8"><style>
  :root{--bg:#04070d;--cyan:#22d3ee;--ink:#f5f8fc;--muted:#9fb0c6}
  *{box-sizing:border-box;margin:0}
  html,body{width:${SIZES[kind].w}px;height:${SIZES[kind].h}px;overflow:hidden;background:var(--bg);font-family:"Helvetica Neue",Helvetica,Arial,sans-serif;color:var(--ink)}
  .bg{position:absolute;inset:0;background:
    radial-gradient(900px 700px at ${feed ? "85% 20%" : "50% 42%"},rgba(34,211,238,.28),transparent 65%),
    radial-gradient(700px 600px at 0% 100%,rgba(245,176,40,.16),transparent 70%),
    linear-gradient(160deg,#0a1424 0%,#050810 60%,#03050a 100%)}
  .grain{position:absolute;inset:0;opacity:.5;background:repeating-linear-gradient(115deg,rgba(255,255,255,.035) 0 2px,transparent 2px 46px)}
  .logo{position:absolute;${feed ? "left:70px;top:70px;width:300px" : "left:0;right:0;margin:auto;top:150px;width:420px"};mix-blend-mode:screen;filter:invert(1)}
  .copy{position:absolute;${feed ? "left:70px;top:250px;width:480px" : "left:0;right:0;top:290px;text-align:center;padding:0 60px"}}
  .tag{display:inline-block;font-weight:800;letter-spacing:.22em;font-size:${feed ? 22 : 28}px;color:var(--cyan);margin-bottom:${feed ? 22 : 26}px}
  h1{font-weight:900;font-style:italic;letter-spacing:-.02em;line-height:.98;font-size:${feed ? 100 : 148}px}
  h1 span{display:block}
  h1 span:last-child{background:linear-gradient(90deg,#67e8f9,#22d3ee 55%,#38bdf8);-webkit-background-clip:text;color:transparent}
  p.sub{margin-top:${feed ? 26 : 30}px;font-size:${feed ? 30 : 36}px;line-height:1.3;color:var(--muted);font-weight:500;${feed ? "" : "max-width:820px;margin-left:auto;margin-right:auto"}}
  .phone{position:absolute;left:${phone.left}px;top:${phone.top}px;width:${phone.w}px;padding:14px;border-radius:${phone.w * 0.13}px;
    background:linear-gradient(145deg,#3a4458,#10141c 40%,#2a3344);box-shadow:0 0 0 2px #05070b,0 50px 120px rgba(0,0,0,.65),0 0 160px rgba(34,211,238,.18)}
  .screen{position:relative;width:100%;aspect-ratio:390/844;border-radius:${phone.w * 0.105}px;overflow:hidden;background:#000}
  .screen img{display:block;width:100%;height:100%}
  .notch{position:absolute;top:14px;left:50%;transform:translateX(-50%);width:${phone.w * 0.27}px;height:${phone.w * 0.07}px;border-radius:99px;background:#000}
  </style></head><body>
  <div class="bg"></div><div class="grain"></div>
  <img class="logo" src="${logo}">
  <div class="copy"><div class="tag">FANTASY SIM</div><h1>${head}</h1><p class="sub">${scene.sub}</p></div>
  <div class="phone"><div class="screen"><img src="${shot}"></div></div>
  </body></html>`;
}

export async function compose({ browser, scenes, repo, raw, out, only }) {
  const logo = dataUri(path.join(repo, "web-next/public/fantasydesk-wordmark.png"));
  const ctx = await browser.newContext({ deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  const written = [];
  for (const [i, scene] of scenes.entries()) {
    if (only && !only.includes(scene.id)) continue;
    const shot = path.join(raw, `${scene.id}.png`);
    if (!fs.existsSync(shot)) { console.log("missing capture, skipped", scene.id); continue; }
    for (const [kind, { w, h, file }] of Object.entries(SIZES)) {
      await page.setViewportSize({ width: w, height: h });
      await page.setContent(creativeHtml(scene, kind, dataUri(shot), logo), { waitUntil: "load" });
      await page.evaluate(() => document.fonts.ready);
      const dest = path.join(out, `${String(i + 1).padStart(2, "0")}-${scene.id}-${file}.png`);
      await page.screenshot({ path: dest });
      written.push(dest);
      console.log("wrote", dest);
    }
  }
  await ctx.close();
  return written;
}
