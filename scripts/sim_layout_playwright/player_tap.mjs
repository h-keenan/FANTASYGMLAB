// Every player and pick opens the quick view (docs/ui-patterns.md, "Every player and pick is tappable").
// Drives the Fantasy Sim at a phone viewport against the simmock and, on each main surface, clicks a player (or a pick) and
// asserts the matching sheet opens, then that tapping the REST of an accordion row expands it instead of opening the PQV.
//   PW_CORE=/path/to/playwright-core/index.mjs BASE=http://localhost:3197 node scripts/sim_layout_playwright/player_tap.mjs [name-prefix]
// Exit 1 when any surface fails.
import { createMock } from "./simmock.mjs";

const { chromium } = await import(process.env.PW_CORE || "playwright-core");
const BASE = process.env.BASE || "http://localhost:3197";
const browser = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : { executablePath: process.env.HOME + "/Library/Caches/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-mac-arm64/chrome-headless-shell" });
const session = {
  access_token: "a.b.c", refresh_token: "r", token_type: "bearer", expires_in: 99999, expires_at: Math.floor(Date.now() / 1000) + 99999,
  user: { id: "u1", aud: "authenticated", role: "authenticated", email: "t@example.com", app_metadata: {}, user_metadata: {}, created_at: "2026-01-01T00:00:00Z" },
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const only = process.argv[2];
const results = [];

// Phones navigate through the game orb (a nav sheet); wider layouts have a tab row. Sub-tabs inside a page are role=tab.
const TOP = ["Home", "Team", "Players", "Trades", "League", "More"];
const tab = async (page, name) => {
  if (TOP.includes(name)) {
    await page.getByTestId("sim-game-orb").click({ timeout: 5000 });
    await sleep(500);
    await page.getByTestId("sim-game-nav").getByText(name, { exact: true }).first().click({ timeout: 5000 });
  } else await page.getByRole("tab", { name, exact: false }).first().click({ timeout: 5000 });
  await sleep(1000);
};
const dialog = (page) => page.getByRole("dialog").last();

/** Click a tap target and assert a dialog opens (the PQV peek sheet / pick sheet), then close it. */
async function expectOpens(page, locator, what, { text, minH = 43.5 } = {}) {
  const box = await locator.boundingBox();
  if (!box) throw new Error(`${what}: no tap target found`);
  if (box.height < minH) throw new Error(`${what}: tap target is ${Math.round(box.height)}px tall, expected ${Math.round(minH)}px+ (${await locator.evaluate((e) => e.outerHTML.slice(0, 160))})`);
  await locator.click();
  await sleep(900);
  const d = dialog(page);
  await d.waitFor({ state: "visible", timeout: 4000 });
  if (text && !(await d.innerText()).includes(text)) throw new Error(`${what}: the sheet opened but does not mention "${text}"`);
  await page.keyboard.press("Escape");
  await sleep(500);
  if (await page.getByRole("dialog").count()) await page.getByRole("button", { name: /^Close/ }).first().click({ timeout: 1500 }).catch(() => {});
  await sleep(300);
}

async function scenario(name, steps, { week = 3, status = "in_season" } = {}) {
  if (only && !name.startsWith(only)) return;
  const mock = createMock({ status, week });
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
  await ctx.addInitScript(([t, s]) => { try { localStorage.setItem("fgl:theme-mode", t); localStorage.setItem("sb-dummy-auth-token", JSON.stringify(s)); localStorage.setItem("fgl:onboarding-complete", "1"); } catch (e) {} }, ["dark", session]);
  await ctx.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.hostname === "localhost" && url.port === "8000") {
      const body = route.request().postData(); let json = null; try { json = body ? JSON.parse(body) : null; } catch {}
      const res = mock(route.request().method(), url.pathname, Object.fromEntries(url.searchParams.entries()), json);
      return route.fulfill({ status: res?.status ?? 200, contentType: "application/json", body: JSON.stringify(res?.body ?? {}), headers: { "access-control-allow-origin": "*" } });
    }
    if (url.hostname === "dummy.supabase.co") return route.fulfill({ status: 200, contentType: "application/json", body: "{}", headers: { "access-control-allow-origin": "*" } });
    return route.continue();
  });
  const page = await ctx.newPage();
  try {
    await page.goto(`${BASE}/gm-game`, { waitUntil: "domcontentloaded" });
    await sleep(2500);
    await page.getByRole("button", { name: /Continue|Open game/ }).first().click({ timeout: 8000 }).catch(() => {});
    await sleep(1500);
    await steps(page);
    results.push([name, "PASS", ""]);
  } catch (error) {
    results.push([name, "FAIL", String(error.message || error).split("\n")[0]]);
    if (process.env.OUT) await page.screenshot({ path: `${process.env.OUT}/player_tap-${name}.png` }).catch(() => {});
  }
  await ctx.close();
}

// The inbox offer cards (the bug report: "Kayshon Boutte" YOU GIVE did nothing). Home and the Trades tab share the cards.
async function expandOffer(page) {
  if (await page.locator('[data-player-tap="true"]').count()) return; // the first offer opens by default
  await page.getByRole("button", { name: /Red Zone Rats/ }).first().click(); await sleep(600);
}
async function offerCards(page) {
  await expandOffer(page);
  const give = page.locator('[data-testid="compact-player-card"]').first();
  await expectOpens(page, page.locator('[data-player-tap="true"]').first(), "offer card player", {});
  void give;
}
await scenario("1-trades-inbox-player", async (page) => { await tab(page, "Trades"); await offerCards(page); });
await scenario("2-trades-inbox-pick", async (page) => {
  await tab(page, "Trades"); await expandOffer(page);
  const pickButtons = page.locator('[data-pick-tap="true"]');
  if ((await pickButtons.count()) === 0) { results.push(["2-trades-inbox-pick", "SKIP", "the mock inbox holds no picks"]); return; }
  await expectOpens(page, pickButtons.first(), "offer card pick", {});
});
await scenario("3-team-roster-row", async (page) => {
  await tab(page, "Team");
  const row = page.getByTestId("player-accordion-row").first();
  await expectOpens(page, row.locator('[data-player-tap="true"]').first(), "roster row avatar");
  await expectOpens(page, row.locator('[data-player-tap="true"]').nth(1), "roster row name", { minH: 27.5 });
  const m = await row.getByTestId("row-meta").boundingBox(); await page.mouse.click(m.x + m.width * 0.8, m.y + m.height / 2); await sleep(500); // the stats line is under the row expand button
  if ((await row.getAttribute("data-open")) !== "true") throw new Error("tapping the rest of the row must expand it");
});
await scenario("4-league-team-sheet-roster", async (page) => {
  await tab(page, "League"); await tab(page, "Teams");
  await page.getByRole("button", { name: /Open roster/ }).nth(4).click(); await sleep(1500);
  await dialog(page).getByRole("tab", { name: "Roster" }).click(); await sleep(1000);
  await expectOpens(page, dialog(page).locator('[data-player-tap="true"]').first(), "team sheet roster player");
});
await scenario("5-players-list", async (page) => {
  await tab(page, "League"); await page.getByRole("tab", { name: "Players", exact: true }).last().click(); await sleep(1200);
  await expectOpens(page, page.getByTestId("player-accordion-row").first().locator('[data-player-tap="true"]').nth(1), "players list name", { minH: 27.5 });
});
await scenario("6-draft-board", async (page) => {
  await expectOpens(page, page.getByTestId("player-accordion-row").first().locator('[data-player-tap="true"]').first(), "draft board player");
}, { status: "drafting", week: 0 });
await scenario("7-home-offers", async (page) => {
  const taps = page.locator('[data-player-tap="true"]');
  if ((await taps.count()) === 0) throw new Error("Home shows no tappable player at all");
  await expectOpens(page, taps.first(), "home player chip");
});

for (const [name, status, detail] of results) console.log(`${status.padEnd(5)} ${name}${detail ? `  ${detail}` : ""}`);
await browser.close();
process.exit(results.some((r) => r[1] === "FAIL") ? 1 : 0);
