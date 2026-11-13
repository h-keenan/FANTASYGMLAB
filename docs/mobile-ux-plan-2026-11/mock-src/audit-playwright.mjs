import { chromium } from "playwright-core";
import fs from "fs";
const OUT = process.env.OUT; fs.mkdirSync(OUT,{recursive:true});
const browser = await chromium.launch({ executablePath: process.env.HOME + "/Library/Caches/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-mac-arm64/chrome-headless-shell" });
const session = { access_token: "a.b.c", refresh_token: "r", token_type: "bearer", expires_in: 99999, expires_at: Math.floor(Date.now()/1000)+99999, user: { id: "u1", aud: "authenticated", role: "authenticated", email: "t@example.com", app_metadata: {}, user_metadata: {}, created_at: "2026-01-01T00:00:00Z" } };
const L = "1001";
const dash = { ok:true, quiet:false, quiet_reason:"", reason:"", items:[
 {category:"top_priority",headline:"Trade for a top-12 RB before the deadline",reason:"Your roster is bottom-third at RB with no clear bench answer.",supporting_context:null,destination:"trade_hub",route_player_id:"4046",route_player_name:"Test Back",route_player_position:"RB",route_player_team:"SF",route_player_tier:"starter",route_player_score:88.4,route_player_injury_status:"",mentioned_players:[],recommendation_narrative:null,presentation:null,recommendation_id:"r1",tier_label:"Top Priority"},
 {category:"watch",headline:"Your WR2 is questionable",reason:"Check status before Sunday lock.",destination:"my_team",mentioned_players:[],recommendation_id:"r2",tier_label:"Watch"},
 {category:"watch",headline:"Waiver target available: K. Pitts-like TE",reason:"TE is your thinnest spot.",destination:"waivers",mentioned_players:[],recommendation_id:"r3",tier_label:"Watch"}],
 team_snapshot:{wins:7,losses:6,ties:0,health_flag:"Stable",key_injuries_summary:"",top_injury_impact_summary:"",top_injury_impact_players:[],injured_starters:1,average_age:26.4,power_rank:2,power_rank_tied:false,franchise_rank:1,franchise_rank_tied:true,starter_rank:3,starter_rank_tied:false,bench_rank:5,bench_rank_tied:false},
 entitlement:{is_premium:true,visible_count:3,hidden_count:0}};
const me = { ok:true, user:{id:"u1",email:"t@example.com",entitlement:"premium",sleeper_username:"zach",profile_status:"ok",league_cap:5}, premium_benefits:[], premium_comparison:[] };
const prefs = { ok:true, ui_density:"guided", theme_mode:"dark", theme_mode_set:true, experience_level:"advanced", experience_goal:"win_now", last_league:{league_id:L,league_name:"Dynasty Overlords"} };
function api(m,p){
  if (p==="/v1/me") return me; if (p==="/v1/preferences") return prefs;
  if (p.endsWith("/dashboard")) return dash;
  if (p.startsWith("/v1/trade-outcomes")) return {ok:true,items:[]};
  return {ok:true};
}
const routes = JSON.parse(process.env.ROUTES);
const results = [];
for (const [name, path] of routes) {
  const ctx = await browser.newContext({ viewport:{width:390,height:844}, deviceScaleFactor:2, hasTouch:true, isMobile:true });
  await ctx.addInitScript(([s]) => { try { localStorage.setItem("fgl:theme-mode","dark"); localStorage.setItem("sb-dummy-auth-token", JSON.stringify(s)); localStorage.setItem("fgl:onboarding-complete","1"); } catch(e){} }, [session]);
  await ctx.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.hostname==="localhost" && url.port==="8000") return route.fulfill({status:200,contentType:"application/json",body:JSON.stringify(api(route.request().method(), url.pathname)),headers:{"access-control-allow-origin":"*"}});
    if (url.hostname==="dummy.supabase.co") { const b = url.pathname.includes("saved_leagues") ? [{league_id:L,league_name:"Dynasty Overlords"},{league_id:"1002",league_name:"Sunday Scaries"}] : {}; return route.fulfill({status:200,contentType:"application/json",body:JSON.stringify(b),headers:{"access-control-allow-origin":"*"}}); }
    return route.continue();
  });
  const page = await ctx.newPage();
  await page.goto("http://localhost:3111"+path, { waitUntil:"networkidle", timeout:90000 }).catch(e=>console.log("goto",name,e.message.slice(0,80)));
  await page.waitForTimeout(2500);
  await page.screenshot({ path:`${OUT}/${name}_fold.png` });
  await page.screenshot({ path:`${OUT}/${name}_full.png`, fullPage:true });
  const m = await page.evaluate(() => {
    const vh = innerHeight, vis=[];
    const parse = (c)=>{const m=c.match(/rgba?\(([^)]+)\)/); if(!m) return null; const a=m[1].split(",").map(s=>parseFloat(s)); return {r:a[0],g:a[1],b:a[2],a:a[3]??1};};
    const lum=(c)=>{const f=v=>{v/=255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4)};return 0.2126*f(c.r)+0.7152*f(c.g)+0.0722*f(c.b)};
    const bgOf=(el)=>{let e=el; while(e){const c=parse(getComputedStyle(e).backgroundColor); if(c&&c.a>0.5) return c; e=e.parentElement;} return {r:0,g:0,b:0,a:1}};
    const sizes={}, low=[]; let textEls=0, fold=0, textFold=0;
    const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
    let n; const seen=new Set();
    while(n=walker.nextNode()){ const t=n.textContent.trim(); if(!t) continue; const el=n.parentElement; if(seen.has(el)) continue; seen.add(el); const cs=getComputedStyle(el); if(cs.visibility==="hidden"||cs.display==="none") continue; const r=el.getBoundingClientRect(); if(r.width===0||r.height===0) continue; if(el.closest("[class*=sr-only]")) continue;
      textEls++; const px=Math.round(parseFloat(cs.fontSize)*2)/2; sizes[px]=(sizes[px]||0)+1;
      const inFold = r.top<vh && r.bottom>0; if(inFold){textFold++;}
      const fg=parse(cs.color), bg=bgOf(el); if(fg&&inFold){ const L1=lum(fg),L2=lum(bg); const cr=(Math.max(L1,L2)+0.05)/(Math.min(L1,L2)+0.05)*1; const large=px>=18; if(cr<(large?3:4.5)) low.push([t.slice(0,24),px,+cr.toFixed(2)]); }
    }
    const tt=[...document.querySelectorAll("a,button,[role=button],[role=tab],input,select")].filter(e=>{const r=e.getBoundingClientRect(); const cs=getComputedStyle(e); return r.width>0&&r.height>0&&cs.visibility!=="hidden"&&r.top<vh&&r.bottom>0});
    const small=tt.filter(e=>{const r=e.getBoundingClientRect(); return r.width<44||r.height<44}).map(e=>{const r=e.getBoundingClientRect();return `${(e.getAttribute("aria-label")||e.textContent||"").trim().slice(0,18)}:${Math.round(r.width)}x${Math.round(r.height)}`});
    return { scrollVh: +(document.documentElement.scrollHeight/vh).toFixed(2), scrollPx: document.documentElement.scrollHeight, distinctSizes:Object.keys(sizes).length, sizes, textEls, textFold, tapFold:tt.length, tapSmall:small.length, smallList:small.slice(0,8), lowContrast:low.length, lowList:low.slice(0,6), title:document.title, h1:document.querySelector("h1")?.textContent?.slice(0,40), minFont:Math.min(...Object.keys(sizes).map(Number)) };
  });
  results.push({name,path,...m}); console.log(name, JSON.stringify({scrollVh:m.scrollVh,sizes:m.distinctSizes,min:m.minFont,textFold:m.textFold,tapFold:m.tapFold,tapSmall:m.tapSmall,low:m.lowContrast}));
  await ctx.close();
}
fs.writeFileSync(`${OUT}/metrics.json`, JSON.stringify(results,null,1));
await browser.close();
