// Fantasy Sim social ad creatives, regenerated from the real current UI.
//
//   1. CAPTURE: opens web-next's Fantasy Sim at 390px (dark theme, reduced motion) against the Sim mock backend
//      (scripts/sim_layout_playwright/simmock.mjs, fictional data only) and screenshots six scenes.
//   2. COMPOSE: lays each screenshot in a device frame on a branded gradient with a headline + the FantasyDesk
//      wordmark (web-next/public/fantasydesk-wordmark.png) and renders 1080x1080 (feed) and 1080x1920 (stories).
//
//   cd web-next && npm ci && NEXT_PUBLIC_SUPABASE_URL=https://dummy.supabase.co NEXT_PUBLIC_SUPABASE_ANON_KEY=x \
//     NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npx next dev -p 3231 &
//   PW_CORE=/path/to/node_modules/playwright-core/index.mjs BASE=http://localhost:3231 OUT=/tmp/sim-ads \
//     node scripts/marketing/sim_social_ads.mjs [--only draft,trade] [--compose-only]
//
// See scripts/marketing/README.md.
import fs from "fs";
import path from "path";
import os from "os";
import { fileURLToPath } from "url";
import { createMock } from "../sim_layout_playwright/simmock.mjs";
import { compose } from "./sim_social_ads_compose.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "../..");
const { chromium } = await import(process.env.PW_CORE || "playwright-core");
const BASE = process.env.BASE || "http://localhost:3231";
const OUT = process.env.OUT || path.join(os.tmpdir(), "sim-ads");
const RAW = path.join(OUT, "raw");
const argv = process.argv.slice(2);
const only = argv.includes("--only") ? argv[argv.indexOf("--only") + 1].split(",") : null;
const composeOnly = argv.includes("--compose-only");
fs.mkdirSync(RAW, { recursive: true });

/** Chrome headless shell: CHROME env, else the newest one in the Playwright cache, else Playwright's own. */
function chromePath() {
  if (process.env.CHROME) return process.env.CHROME;
  const cache = process.env.PLAYWRIGHT_BROWSERS_PATH || path.join(os.homedir(), process.platform === "darwin" ? "Library/Caches/ms-playwright" : ".cache/ms-playwright");
  try {
    const dirs = fs.readdirSync(cache).filter((d) => d.startsWith("chromium_headless_shell-")).sort().reverse();
    for (const d of dirs) {
      for (const sub of fs.readdirSync(path.join(cache, d))) {
        const exe = path.join(cache, d, sub, "chrome-headless-shell");
        if (fs.existsSync(exe)) return exe;
      }
    }
  } catch {}
  return undefined;
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const session = { access_token: "a.b.c", refresh_token: "r", token_type: "bearer", expires_in: 99999, expires_at: Math.floor(Date.now() / 1000) + 99999, user: { id: "u1", aud: "authenticated", role: "authenticated", email: "demo@example.com", app_metadata: {}, user_metadata: {}, created_at: "2026-01-01T00:00:00Z" } };

// A fictional season story for the player card (GET /players/{id}/history `story`, see SimStoryEntry in web-next/src/lib/simGame.ts).
const STORY = [
  { kind: "drafted", season: 1, year: 2026, season_label: "Season 1", week: 0, text: "Drafted in round 3 (pick 31) by Dynasty Dogs.", tone: "neutral" },
  { kind: "depth", season: 1, year: 2026, season_label: "Season 1", week: 4, text: "Moved up to WR1 after an injury ahead of him.", tone: "good" },
  { kind: "traded", season: 1, year: 2026, season_label: "Season 1", week: 6, text: "Traded to Zach's Squad for Ace Receiver.", tone: "neutral" },
  { kind: "season", season: 1, year: 2026, season_label: "Season 1", week: 99, text: "WR1 for 8 games: 121.4 points, 15.2 a game (WR9).", tone: "good", games: 8, points: 121.4, ppg: 15.2, pos_rank: 9 },
  { kind: "injury", season: 2, year: 2027, season_label: "Season 2", week: 5, text: "Hamstring strain, out 2 weeks.", tone: "bad" },
  { kind: "started", season: 2, year: 2027, season_label: "Season 2", week: 7, text: "Back in the lineup and scored 24.6.", tone: "good" },
  { kind: "season", season: 2, year: 2027, season_label: "Season 2", week: 99, text: "WR1 for 3 games so far: 52.9 points, 17.6 a game.", tone: "good", games: 3, points: 52.9, ppg: 17.6, pos_rank: 4 },
];

const FRANCHISE = "Capitol Kings";
// The settings a game created today carries (the mock omits the newer ones, which reads as an old save).
const NEW_GAME_FLAGS = { limit_v: 1, hint_v: 1, kd_v: 1, pos_v: 1, reserve_v: 1, block_v: 1 };

/** Make the mock's "you" record agree everywhere (standings and header disagree in the raw mock). */
function fixup(node, opts) {
  if (!node || typeof node !== "object") return;
  // New-game rule flags (docs/fantasy-sim-api.md, web-next SimGameSettings) so no scene shows an "Update game rules" notice.
  if (node.slots && node.rounds && node.regular_weeks) Object.assign(node, NEW_GAME_FLAGS);
  if (node.team_id === "3" && typeof node.wins === "number" && typeof node.losses === "number") {
    if (opts.status === "complete") { node.wins = 11; node.losses = 3; } else { node.wins = 3; node.losses = 1; }
  }
  for (const v of Object.values(node)) fixup(v, opts);
}

async function openGame(browser, mockOpts, fn) {
  const mock = createMock(mockOpts);
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true, deviceScaleFactor: 3, reducedMotion: "reduce", colorScheme: "dark" });
  await ctx.addInitScript(([s]) => {
    try { localStorage.setItem("fgl:theme-mode", "dark"); localStorage.setItem("sb-dummy-auth-token", JSON.stringify(s)); localStorage.setItem("fgl:onboarding-complete", "1"); } catch (e) {}
  }, [session]);
  await ctx.route("**/*", async (route) => {
    const u = new URL(route.request().url());
    const cors = { "access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "*" };
    if (u.hostname === "localhost" && u.port === "8000") {
      if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
      const raw = route.request().postData(); let json = null; try { json = raw ? JSON.parse(raw) : null; } catch {}
      if (u.pathname.endsWith("/notifications")) return route.fulfill({ status: 200, contentType: "application/json", headers: cors, body: JSON.stringify({ ok: true, reason: "", seq: 9, unread: 0, items: [] }) });
      const res = u.pathname.startsWith("/v1/sim") ? mock(route.request().method(), u.pathname, Object.fromEntries(u.searchParams), json) : { status: 404, body: {} };
      if (res?.body && /\/players\/[^/]+\/history$/.test(u.pathname)) res.body.story = STORY;
      if (res?.body) fixup(res.body, mockOpts);
      // The mock's default team name is a real first name; ads use a fictional franchise instead.
      const body = JSON.stringify(res?.body ?? {}).replaceAll("Zach's Squad", FRANCHISE);
      return route.fulfill({ status: res?.status ?? 200, contentType: "application/json", body, headers: cors });
    }
    if (u.hostname === "dummy.supabase.co") return route.fulfill({ status: 200, contentType: "application/json", body: "{}", headers: cors });
    return route.continue();
  });
  const page = await ctx.newPage();
  await page.goto(`${BASE}/gm-game`, { waitUntil: "domcontentloaded" });
  await page.addStyleTag({ content: "nextjs-portal,[data-nextjs-toast]{display:none!important} *{caret-color:transparent!important}" }).catch(() => {});
  await page.getByRole("button", { name: "Open game" }).first().waitFor({ timeout: 120000 });
  await sleep(1200);
  await page.getByRole("button", { name: "Open game" }).first().dispatchEvent("click");
  await sleep(3000);
  try { await fn(page); } finally { await ctx.close(); }
}

const click = async (loc) => { await loc.first().dispatchEvent("click"); await sleep(1200); };
// Top pages on a phone are reached through the GM orb's nav sheet; sub-tabs inside a page are role=tab.
const TOP = ["Home", "Team", "Players", "Trades", "League", "More"];
const tab = async (page, name) => {
  if (TOP.includes(name)) {
    await click(page.getByTestId("sim-game-orb"));
    await click(page.getByTestId("sim-game-nav").getByText(name, { exact: true }));
  } else await click(page.getByRole("tab", { name }));
};

// Each scene: mock options, steps to reach the screen, and the marketing copy.
export const SCENES = [
  {
    id: "draft", headline: ["Draft like", "a GM."], sub: "Best available, your needs and every pick, live.",
    mock: { status: "drafting", pickStart: 14 },
    steps: async () => {},
  },
  {
    id: "week", headline: ["Every week", "is a story."], sub: "Live matchups, projections and a win chance.",
    mock: { status: "in_season", week: 4, pro: true },
    steps: async () => {},
  },
  {
    id: "trade", headline: ["Win the", "trade."], sub: "Every offer gets an honest verdict.",
    mock: { status: "in_season", week: 4, pro: true },
    steps: async (page) => {
      await tab(page, "Trades"); await tab(page, "Make an offer");
      await click(page.getByRole("button", { name: /Blitz Brigade.*Trade with this team/ }));
      await click(page.getByRole("button", { name: /You send: add players or picks/ }));
      const apply = () => click(page.locator("footer").getByRole("button").last());
      await click(page.getByLabel("Add Malik Ross", { exact: true }));
      await apply();
      await click(page.getByRole("button", { name: /You receive: add players or picks/ }));
      await click(page.getByLabel("Add Devin Carter", { exact: true }));
      await apply();
      await page.getByTestId("trade-verdict").waitFor({ timeout: 8000 });
      // Put the offer (send / receive / verdict) at the top of the frame.
      await page.evaluate(() => window.scrollTo(0, Math.max(0, [...document.querySelectorAll("*")].find((e) => /^You send/i.test(e.textContent || "") && e.children.length < 4)?.getBoundingClientRect().top + scrollY - 190)));
    },
  },
  {
    id: "player", headline: ["Every player", "has a story."], sub: "Season history, depth moves and injuries.",
    mock: { status: "in_season", week: 4, pro: true },
    steps: async (page) => {
      await tab(page, "Team");
      await click(page.getByRole("button", { name: /^Open Malik Ross/ }));
      await click(page.getByRole("dialog").getByRole("tab", { name: "History" }));
      await page.getByTestId("sim-player-story").waitFor({ timeout: 8000 });
      await page.evaluate(() => {
        const sc = document.querySelector(".pqv-scroll"), el = document.querySelector('[data-testid="sim-player-story"]');
        if (sc && el) sc.scrollTop += el.getBoundingClientRect().top - sc.getBoundingClientRect().top - 330;
      });
    },
  },
  {
    id: "team", headline: ["Scout every", "roster."], sub: "Strengths, needs and who to target.",
    mock: { status: "in_season", week: 4, pro: true },
    steps: async (page) => {
      await tab(page, "League"); await tab(page, "Teams");
      await click(page.getByRole("button", { name: /Gridiron Goats.*Open roster/ }));
      await page.getByTestId("team-sheet-name").waitFor({ timeout: 8000 });
    },
  },
  {
    id: "recap", headline: ["Build a", "dynasty."], sub: "Season grade, awards and the decisions that mattered.",
    mock: { status: "complete", week: 17, pro: true },
    steps: async () => {},
  },
];

async function capture(browser) {
  for (const s of SCENES) {
    if (only && !only.includes(s.id)) continue;
    await openGame(browser, s.mock, async (page) => {
      try { await s.steps(page); } catch (e) { await page.screenshot({ path: path.join(RAW, `${s.id}-FAILED.png`) }); throw e; }
      await sleep(1200);
      await page.screenshot({ path: path.join(RAW, `${s.id}.png`) });
      console.log("captured", s.id);
    });
  }
}

const browser = await chromium.launch({ executablePath: chromePath() });
if (!composeOnly) await capture(browser);
await compose({ browser, scenes: SCENES, repo: REPO, raw: RAW, out: OUT, only });
await browser.close();
