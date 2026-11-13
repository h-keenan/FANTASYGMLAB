import fs from "fs"; import { ic, page } from "./lib.mjs";
export const CSS = `
body{background:radial-gradient(120% 60% at 50% -10%,rgba(103,232,249,.13),transparent 60%),#000}
.hd{padding:14px 16px 8px;display:flex;align-items:center;gap:10px}
.hd h1{font-size:26px;font-weight:800;letter-spacing:-.02em;flex:1}
.hd .ib{width:44px;height:44px;border-radius:14px;border:1px solid var(--bd);background:rgba(31,34,38,.6);display:grid;place-items:center;color:var(--tx2);position:relative}
.badge{position:absolute;top:6px;right:6px;min-width:16px;height:16px;border-radius:9px;background:var(--bad);font-size:11px;font-weight:800;display:grid;place-items:center;color:#fff;padding:0 4px}
.chip{display:inline-flex;align-items:center;gap:6px;height:30px;padding:0 12px;border-radius:999px;border:1px solid var(--bd);background:rgba(31,34,38,.7);font-size:13px;font-weight:600;color:var(--tx2);margin:0 16px 10px}
.chip b{color:var(--act);font-weight:700}
.card{margin:0 16px 12px;border-radius:20px;border:1px solid var(--bd);background:linear-gradient(180deg,rgba(40,44,50,.78),rgba(25,28,32,.78));backdrop-filter:blur(14px);padding:16px;position:relative}
.kick{font-size:11px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:var(--mut)}
.pill{white-space:nowrap;display:inline-flex;align-items:center;gap:5px;height:24px;padding:0 10px;border-radius:999px;font-size:11px;font-weight:800;letter-spacing:.06em;text-transform:uppercase}
.p-ok{background:rgba(34,197,94,.15);color:var(--ok)}.p-bad{background:rgba(239,68,68,.15);color:#ff8a8a}.p-warn{background:rgba(245,158,11,.15);color:var(--warn)}.p-acc{background:rgba(103,232,249,.13);color:var(--acc)}.p-pro{background:rgba(250,204,21,.14);color:var(--act)}
.hero{font-size:44px;font-weight:800;letter-spacing:-.03em;line-height:1}
.why{font-size:15px;color:var(--mut);line-height:1.35}
.row{display:flex;align-items:center;gap:10px}.sp{flex:1}
.nav{position:absolute;left:0;right:0;bottom:0;height:84px;padding:8px 8px 26px;display:flex;background:rgba(10,12,14,.88);backdrop-filter:blur(18px);border-top:1px solid var(--bd)}
.nav a{flex:1;display:flex;flex-direction:column;align-items:center;gap:3px;color:var(--mut);font-size:11px;font-weight:700;position:relative;padding-top:4px}
.nav a.on{color:var(--acc)}.nav a.on:before{content:"";position:absolute;top:-9px;width:28px;height:3px;border-radius:2px;background:var(--acc);box-shadow:0 0 12px var(--acc)}
.nav .dot{position:absolute;top:0;left:calc(50% + 6px);min-width:16px;height:16px;border-radius:8px;background:var(--bad);color:#fff;font-size:11px;font-weight:800;display:grid;place-items:center;padding:0 4px}
.qa{display:flex;gap:8px;margin:0 16px 12px}.qa a{flex:1;height:78px;border-radius:16px;border:1px solid var(--bd);background:rgba(31,34,38,.6);display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;font-size:13px;font-weight:700;color:var(--tx2);position:relative}
.qa a svg{color:var(--acc)}
.tiles{display:flex;gap:8px;margin:0 16px 12px}.tile{flex:1;border-radius:16px;border:1px solid var(--bd);background:rgba(31,34,38,.6);padding:12px 12px 10px}
.tile .v{font-size:26px;font-weight:800;letter-spacing:-.02em;margin:2px 0 2px}.tile .t{font-size:13px;font-weight:700}
.up{color:var(--ok)}.dn{color:#ff8a8a}
.bar{height:8px;border-radius:4px;background:#2a2e35;overflow:hidden;display:flex;gap:2px}.bar i{display:block;height:100%}
.btn{height:44px;border-radius:14px;background:var(--acc2);color:#0b1220;font-weight:800;font-size:15px;display:inline-flex;align-items:center;gap:6px;padding:0 18px}
`;
const nav = (on) => `<nav class="nav">${[["home","Today"],["team","Team"],["swap","Trades"],["league","League"],["more","More"]].map(([i,l])=>`<a class="${l===on?"on":""}">${ic(i,24)}${l}${l==="Team"?'<span class="dot">1</span>':""}${l==="Trades"?'<span class="dot">3</span>':""}</a>`).join("")}</nav>`;
export const NAV = nav;
const hdr = (title) => `<div class="hd"><h1>${title}</h1><div class="ib">${ic("search",20)}</div><div class="ib">${ic("bell",20)}<span class="badge">2</span></div></div>`;
const ctx = `<div class="chip">Dynasty Overlords <b>· Wk 11</b>${ic("down",14)}</div>`;

fs.writeFileSync("B-today.html", page("B today", CSS, `${hdr("Today")}${ctx}
<div class="card" style="padding:14px 16px">
 <div class="row"><span class="kick">This week &middot; vs Red Zone Rats</span><span class="sp"></span><span class="pill p-ok">Favored</span></div>
 <div class="row" style="margin:10px 0 10px;align-items:baseline"><span class="hero">121.4</span><span style="color:var(--mut);font-size:18px;font-weight:700">to 117.9</span><span class="sp"></span><span style="font-size:26px;font-weight:800;color:var(--ok)">+3.5</span></div>
 <div class="bar"><i style="width:62%;background:var(--ok)"></i><i style="width:38%;background:#4b5260"></i></div>
 <div class="row" style="margin-top:10px"><span class="why">62% to win. 1 starter is Questionable.</span><span class="sp"></span>${ic("chev",18)}</div>
</div>
<div class="card" style="border-color:rgba(239,68,68,.45);padding:14px 16px">
 <div class="row"><span class="pill p-bad">Top priority</span><span class="sp"></span><span class="kick" style="color:var(--mut)">Deadline 5d</span></div>
 <div style="font-size:18px;font-weight:800;margin:10px 0 4px;letter-spacing:-.01em">Trade for a top-12 RB</div>
 <div class="why">Bottom-third at RB with no bench answer.</div>
 <div class="row" style="margin-top:12px"><span class="btn">See 3 offers ${ic("chev",16,2.4)}</span></div>
</div>
<div class="qa"><a>${ic("check")}Set lineup</a><a>${ic("swap")}Grade trade</a><a>${ic("plus")}Waivers<span class="badge" style="background:var(--acc2);color:#0b1220">3</span></a><a>${ic("search")}Player</a></div>
<div class="tiles">
 <div class="tile"><div class="kick">Power</div><div class="v">#2</div><div class="t up">&#9650; 1 this wk</div></div>
 <div class="tile"><div class="kick">Record</div><div class="v">7-6</div><div class="t" style="color:var(--mut)">4th in league</div></div>
 <div class="tile"><div class="kick">Playoffs</div><div class="v">64%</div><div class="t up">&#9650; 8 pts</div></div>
</div>
<div class="card" style="padding:4px 16px">${[["cal","Lineup locks Sun 1:00 PM","Set it before kickoff","var(--warn)"],["plus","Waivers run Wed 3:00 AM","3 recommended pickups","var(--acc)"]].map(([g,t,u,c],i)=>`<div class="row" style="height:56px;${i?"border-top:1px solid var(--bd)":""}"><span style="color:${c}">${ic(g,20)}</span><div style="flex:1"><div style="font-size:15px;font-weight:700">${t}</div><div style="font-size:13px;color:var(--mut)">${u}</div></div>${ic("chev",16)}</div>`).join("")}</div>${nav("Today")}`));

// league glance card (standalone, between header and fold)
fs.writeFileSync("B-league.html", page("B league", CSS, `${hdr("League")}${ctx}
<div class="card" style="padding:16px">
 <div class="row"><span class="kick">Your standing</span><span class="sp"></span><span class="pill p-acc">Contender</span></div>
 <div class="row" style="gap:16px;margin:12px 0 12px">
  <svg width="92" height="92" viewBox="0 0 92 92"><circle cx="46" cy="46" r="38" fill="none" stroke="#2a2e35" stroke-width="9"/><text x="46" y="68" text-anchor="middle" font-size="9" font-weight="800" fill="#a8adb7" letter-spacing="1">PLAYOFFS</text><circle cx="46" cy="46" r="38" fill="none" stroke="var(--ok)" stroke-width="9" stroke-linecap="round" stroke-dasharray="${2*Math.PI*38*.64} 999" transform="rotate(-90 46 46)"/><text x="46" y="48" text-anchor="middle" font-size="22" font-weight="800" fill="#f7f8fa">64%</text></svg>
  <div><div class="kick">League rank</div><div class="hero" style="font-size:36px;margin:2px 0">#4 <span style="font-size:15px;color:var(--mut);font-weight:700">of 12</span></div><div class="why">7-6 &middot; Power #2 &middot; <span class="up">&#9650; 1</span></div></div>
 </div>
 <div class="why" style="color:var(--tx2)">Win 2 of your last 3 to lock a bye-week seed.</div>
</div>
<div class="card" style="padding:12px 16px">
 <div class="row" style="margin-bottom:8px"><span class="kick">Standings</span><span class="sp"></span><span style="color:var(--acc);font-size:13px;font-weight:700">All 12 ${ic("chev",12,2.4).replace('class="ic"','class="ic" style="display:inline;vertical-align:middle"')}</span></div>
 ${[["1","Gridiron Goats","9-4","▲",""],["2","Blitz Brigade","8-5","▬",""],["3","Dynasty Dogs","8-5","▼",""],["4","Dynasty Overlords","7-6","▲","you"],["5","Hail Marys","7-6","▼",""]].map(([r,n,w,a,y])=>`<div class="row" style="height:44px;border-top:1px solid var(--bd);${y?"background:rgba(103,232,249,.09);margin:0 -16px;padding:0 16px;border-radius:10px":""}"><span style="width:20px;color:var(--mut);font-weight:700">${r}</span><span style="font-weight:${y?800:600};font-size:15px">${n}</span><span class="sp"></span><span style="font-weight:700">${w}</span><span style="width:18px;text-align:right;font-size:11px;color:${a==="▲"?"var(--ok)":a==="▼"?"#ff8a8a":"var(--mut)"}">${a}</span></div>`).join("")}
</div>
<div class="row" style="gap:8px;margin:0 16px 12px">${["Rankings","Playoff odds","Recaps","Games"].map((t,i)=>`<span class="pill ${i==0?"p-acc":""}" style="height:34px;padding:0 14px;font-size:13px;border:1px solid var(--bd);${i==0?"":"background:rgba(31,34,38,.6);color:var(--tx2)"}">${t}</span>`).join("")}</div>
${nav("League")}`));

// More
const rowm = (g,t,s,extra="") => `<div class="row" style="height:56px;padding:0 4px"><span style="width:36px;height:36px;border-radius:11px;background:rgba(103,232,249,.1);display:grid;place-items:center;color:var(--acc)">${ic(g,19)}</span><div style="flex:1"><div style="font-size:15px;font-weight:700">${t}</div>${s?`<div style="font-size:13px;color:var(--mut)">${s}</div>`:""}</div>${extra}${ic("chev",16)}</div>`;
fs.writeFileSync("B-more.html", page("B more", CSS, `<div class="hd"><h1>More</h1></div>
<div class="card" style="padding:14px 16px;border-color:rgba(250,204,21,.4)"><div class="row"><span style="width:44px;height:44px;border-radius:14px;background:rgba(250,204,21,.14);display:grid;place-items:center;color:var(--act)">${ic("crown",22)}</span><div style="flex:1"><div style="font-size:18px;font-weight:800">Pro &middot; trial ends in 6 days</div><div class="why">Manage plan and billing</div></div>${ic("chev",16)}</div></div>
<div class="card" style="padding:6px 16px"><div class="kick" style="padding:10px 0 2px">Play</div>${rowm("game","Fantasy Sim","Draft a team, play a season")}${rowm("star","Portfolio","Every saved league at a glance",'<span class="pill p-pro">Pro</span>')}${rowm("flag","Draft Center","Picks and prospects",'<span class="pill p-pro">Pro</span>')}</div>
<div class="card" style="padding:6px 16px"><div class="kick" style="padding:10px 0 2px">Follow</div>${rowm("news","News")}${rowm("people","Community","Craziest trades this week")}</div>
<div class="card" style="padding:6px 16px"><div class="kick" style="padding:10px 0 2px">You</div>${rowm("user","Account and leagues")}${rowm("gear","Settings and alerts")}${rowm("info","How we evaluate &middot; Legal")}</div>
${nav("More")}`));

// Trade verdict B
fs.writeFileSync("B-verdict.html", page("B verdict", CSS, `<div class="hd" style="padding-bottom:4px"><div class="ib" style="width:40px">${ic("back",22)}</div><h1 style="font-size:26px">Trade verdict</h1><div class="ib">${ic("share",19)}</div></div>${ctx}
<div class="card" style="text-align:center;padding:20px 16px 16px;border-color:rgba(34,197,94,.5);box-shadow:0 0 40px rgba(34,197,94,.14)">
 <div class="kick">Your verdict</div>
 <svg width="220" height="124" viewBox="0 0 220 124" style="margin-top:6px"><path d="M20 110a90 90 0 0 1 180 0" fill="none" stroke="#2a2e35" stroke-width="14" stroke-linecap="round"/><path d="M20 110a90 90 0 0 1 180 0" fill="none" stroke="url(#g)" stroke-width="14" stroke-linecap="round" pathLength="100" stroke-dasharray="74 100"/><defs><linearGradient id="g"><stop offset="0" stop-color="#f59e0b"/><stop offset="1" stop-color="#22c55e"/></linearGradient></defs><text x="110" y="98" text-anchor="middle" font-size="44" font-weight="800" fill="#f7f8fa">WIN</text></svg>
 <div class="row" style="justify-content:center;gap:6px;margin-top:-4px"><span class="pill p-ok" style="padding:0 8px;letter-spacing:.03em">+130 value</span><span class="pill p-acc" style="padding:0 8px;letter-spacing:.03em">Fills WR2</span><span class="pill p-ok" style="padding:0 8px;letter-spacing:.03em">High conf.</span></div>
 <div class="why" style="margin-top:10px;font-size:15px;color:var(--tx2)">You upgrade your weakest starter slot and lose only depth.</div>
</div>
<div class="card" style="padding:14px 16px"><div class="kick" style="margin-bottom:10px">Value balance</div>
 <div class="row" style="gap:6px"><span style="width:56px;font-size:13px;font-weight:700;color:var(--mut)">You give</span><div class="bar" style="flex:1;height:14px"><i style="width:${1710/1840*100}%;background:#4b5260"></i></div><b style="width:44px;text-align:right">1,710</b></div>
 <div class="row" style="gap:6px;margin-top:8px"><span style="width:56px;font-size:13px;font-weight:700;color:var(--mut)">You get</span><div class="bar" style="flex:1;height:14px"><i style="width:100%;background:var(--ok)"></i></div><b style="width:44px;text-align:right">1,840</b></div>
</div>
<div class="card" style="padding:6px 16px">${[["You give","T. Back RB","2027 2nd","#fb7185"],["You get","J. Smith WR","WR7 · age 24","#38bdf8"]].map(([a,b,c,col])=>`<div class="row" style="height:58px;border-bottom:1px solid var(--bd)"><span class="kick" style="width:62px;white-space:nowrap;letter-spacing:.06em">${a}</span><span style="width:8px;height:30px;border-radius:4px;background:${col}"></span><div style="flex:1"><div style="font-weight:700">${b}</div><div style="font-size:13px;color:var(--mut)">${c}</div></div>${ic("chev",16)}</div>`).join("")}</div>
<div style="position:absolute;left:16px;right:16px;bottom:28px;display:flex;gap:10px"><span class="btn" style="flex:1;justify-content:center">Send offer</span><span class="btn" style="background:transparent;border:1px solid var(--bd2);color:var(--tx)">Tweak</span></div>`));

// Player header B
const spark = (pts,col)=>{const w=120,h=36;const mx=Math.max(...pts),mn=Math.min(...pts);const p=pts.map((v,i)=>`${i*w/(pts.length-1)},${h-(v-mn)/(mx-mn)*(h-6)-3}`).join(" ");return `<svg width="${w}" height="${h}"><polyline points="${p}" fill="none" stroke="${col}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/><circle cx="${w}" cy="${p.split(" ").pop().split(",")[1]}" r="3.5" fill="${col}"/></svg>`};
export { spark };
fs.writeFileSync("B-player.html", page("B player", CSS, `<div class="hd" style="padding-bottom:4px"><div class="ib" style="width:40px">${ic("back",22)}</div><h1 style="font-size:18px;color:var(--mut);font-weight:700">Players</h1><div class="ib">${ic("star",19)}</div></div>${ctx}
<div class="card" style="padding:16px;border-top:3px solid var(--wr)">
 <div class="row" style="gap:14px"><div style="width:64px;height:64px;border-radius:18px;background:linear-gradient(135deg,rgba(56,189,248,.35),rgba(56,189,248,.08));border:1px solid rgba(56,189,248,.5);display:grid;place-items:center;font-weight:800;font-size:26px">JM</div>
 <div style="flex:1"><div style="font-size:26px;font-weight:800;letter-spacing:-.02em">Jaxon Moore</div><div class="row" style="gap:6px;margin-top:4px"><span class="pill" style="background:rgba(56,189,248,.16);color:var(--wr)">WR7</span><span style="font-size:13px;color:var(--mut);font-weight:600">KC &middot; 24 yrs &middot; Bye 9</span></div></div></div>
 <div class="row" style="margin-top:16px;align-items:flex-end"><div><div class="kick">Dynasty value</div><div class="hero">78</div></div><span class="sp"></span><div style="text-align:right"><div class="up" style="font-weight:800;font-size:15px;margin-bottom:2px">&#9650; +4 in 30d</div>${spark([60,62,61,66,70,69,74,78],"var(--ok)")}</div></div>
 <div class="row" style="gap:8px;margin-top:14px"><span class="pill p-ok">Healthy</span><span class="pill p-acc">Elite tier</span><span class="pill p-pro">Buy window</span></div>
 <div class="why" style="margin-top:10px;font-size:15px;color:var(--tx2)">Young WR1 on the rise. Worth more to you than your WR2.</div>
</div>
<div class="tiles"><div class="tile"><div class="kick">PPG</div><div class="v">17.2</div><div class="t up">&#9650; vs 14.1</div></div><div class="tile"><div class="kick">Proj wk 11</div><div class="v">16.8</div><div class="t" style="color:var(--mut)">vs DEN</div></div><div class="tile"><div class="kick">Your lineup</div><div class="v">WR2</div><div class="t" style="color:var(--mut)">starts</div></div></div>
<div style="display:flex;gap:8px;margin:0 16px 12px;overflow:hidden">${["Stats","Trends","Schedule","Career","News"].map((t,i)=>`<span class="pill ${i==0?"p-acc":""}" style="height:34px;padding:0 14px;font-size:13px;border:1px solid var(--bd);${i==0?"":"background:rgba(31,34,38,.6);color:var(--tx2)"}">${t}</span>`).join("")}</div>
<div class="card" style="padding:14px 16px"><div class="row"><span class="kick">Last 6 weeks</span><span class="sp"></span><span style="font-size:13px;color:var(--mut)">pts vs 14 avg</span></div><div class="row" style="gap:8px;align-items:flex-end;height:76px;margin-top:10px">${[9,21,18,12,24,19].map((v,i)=>`<div style="flex:1;text-align:center"><div style="font-size:11px;font-weight:700;color:${v>=14?"var(--tx2)":"var(--mut)"};margin-bottom:3px">${v}</div><div style="height:${v*2.2}px;border-radius:6px 6px 3px 3px;background:${v>=14?"var(--wr)":"#4b5260"}"></div></div>`).join("")}</div></div>
<div style="position:absolute;left:16px;right:16px;bottom:28px;display:flex;gap:10px"><span class="btn" style="flex:1;justify-content:center">${ic("swap",18)} Find trades</span><span class="btn" style="background:transparent;border:1px solid var(--bd2);color:var(--tx)">Add to trade</span></div>`));
