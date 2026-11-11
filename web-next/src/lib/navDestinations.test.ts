import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import { PAGE_TITLE_BY_SEGMENT, searchNavDestinations, useNavDestinations, type NavDestination } from "./navDestinations";
import { isGmPlanTab } from "@/components/GmPlanSections";
import { parseDraftCenterTab } from "@/components/DraftCenterContent";
import { parseGamesTab, parseRecapsTab, parseWaiverTab } from "@/lib/pageTabs";

const APP_DIR = path.join(process.cwd(), "src", "app");
const MOBILE_CATALOG = path.join(process.cwd(), "..", "mobile", "src", "lib", "navCatalog.ts");

function all() {
  // eslint-disable-next-line react-hooks/rules-of-hooks -- a plain function of its args, not stateful
  const nav = useNavDestinations("L 1", "My League");
  return [...nav.coreLeagueDestinations, ...nav.gmToolsDestinations, ...nav.generalDestinations, ...nav.accountDestinations];
}

const TAB_PARSERS: Record<string, (v: string) => unknown> = {
  "gm-plan": (v) => (isGmPlanTab(v) ? v : undefined),
  "draft-center": (v) => (["overview", "picks", "scouting"].includes(v) ? parseDraftCenterTab(v) : undefined),
  waivers: (v) => parseWaiverTab(v),
  games: (v) => parseGamesTab(v),
  "league-recaps": (v) => parseRecapsTab(v),
};

describe("GM orb tab destinations", () => {
  const withTabs = all().filter((d) => d.tabs?.length);

  it("covers the multi-tab pages", () => {
    expect(withTabs.map((d) => d.label).sort()).toEqual(
      ["Draft Center", "GM Plan", "Games", "League Rankings", "League Recaps", "Trade Hub", "Waivers"].sort(),
    );
  });

  it("every tab resolves to a real route, and a tab param its page accepts", () => {
    for (const page of withTabs) {
      for (const tab of page.tabs!) {
        const url = new URL(tab.path, "https://x.test");
        const segment = url.pathname.split("/")[1];
        const dir = segment === "trade-history" ? path.join(APP_DIR, segment) : path.join(APP_DIR, segment, "[leagueId]");
        expect(existsSync(path.join(dir, "page.tsx")), `${page.label} > ${tab.label}: ${dir}`).toBe(true);
        const param = url.searchParams.get("tab");
        if (param) {
          const parser = TAB_PARSERS[segment];
          expect(parser, `${segment} has a tab parser`).toBeDefined();
          expect(parser(param), `${page.label} > ${tab.label} ?tab=${param}`).toBeTruthy();
          expect(url.searchParams.get("name")).toBe("My League");
        }
      }
    }
  });

  it("opens Playoff Odds on the League Rankings playoff-odds section", () => {
    const rankings = withTabs.find((d) => d.label === "League Rankings")!;
    expect(rankings.tabs!.find((t) => t.label === "Playoff Odds")!.path).toBe("/league-rankings/L%201?name=My%20League#playoff-odds");
    const src = readFileSync(path.join(process.cwd(), "src", "components", "LeagueRankingsContent.tsx"), "utf8");
    expect(src).toContain('id="playoff-odds"');
  });

  it("shares one catalog byte-for-byte with the app", () => {
    const web = readFileSync(path.join(process.cwd(), "src", "lib", "navCatalog.ts"), "utf8");
    expect(readFileSync(MOBILE_CATALOG, "utf8")).toBe(web);
  });
});

describe("one entry point per destination", () => {
  it("has no duplicate paths or labels across the menu", () => {
    const rows = all();
    const labels = rows.map((d) => d.label);
    expect(new Set(labels).size).toBe(labels.length);
    const paths = rows.map((d) => d.path);
    expect(new Set(paths).size).toBe(paths.length);
  });

  it("lists tab-only pages as tabs, not menu rows", () => {
    const labels = all().map((d) => d.label);
    for (const tabOnly of ["Trade History", "College Scouting", "Playoff Odds", "Trade Finder", "Trade Analyzer"]) {
      expect(labels, tabOnly).not.toContain(tabOnly);
    }
    expect(searchNavDestinations(all(), "trade history").map((d) => d.label)).toContain("Trade Hub > History");
    expect(searchNavDestinations(all(), "college scouting").map((d) => d.label)).toContain("Draft Center > Scouting");
  });

  it("hides the College Scouting tab when the college preference is off", () => {
    const nav = useNavDestinations("L 1", "My League", "off");
    const draft = nav.gmToolsDestinations.find((d) => d.label === "Draft Center")!;
    expect(draft.tabs!.map((t) => t.label)).toEqual(["Overview", "Picks"]);
  });

  it("Home is the league switcher and Account owns settings", () => {
    const rows = all();
    const home = rows.find((d) => d.label === "Home")!;
    const account = rows.find((d) => d.label === "Account")!;
    expect(home.subtitle).not.toMatch(/account/i);
    expect(account.subtitle).toMatch(/settings/i);
  });

  it("titles every menu page and keeps retired routes titled", () => {
    for (const row of all()) {
      const segment = new URL(row.path, "https://x.test").pathname.split("/")[1];
      if (!segment || segment === "premium") continue;
      expect(PAGE_TITLE_BY_SEGMENT[segment], row.label).toBeTruthy();
    }
    expect(PAGE_TITLE_BY_SEGMENT["gm-targets"]).toBe("GM Plan");
  });
});

describe("searchNavDestinations", () => {
  const dests = all();
  const labels = (q: string, list: NavDestination[] = dests) => searchNavDestinations(list, q).map((d) => d.label);

  it("returns nothing for an empty query", () => {
    expect(labels("  ")).toEqual([]);
  });

  it("finds tabs by label and keyword and shows them as Page > Tab", () => {
    expect(labels("scouting")).toContain("Draft Center > Scouting");
    expect(labels("playoff odds")).toContain("League Rankings > Playoff Odds");
    expect(labels("finder")).toContain("Trade Hub > Finder");
    expect(labels("pickem")).toContain("Games > Pick'em");
    expect(labels("bench regret")).toContain("League Recaps > Roundup");
    expect(labels("watchlist")).toEqual(expect.arrayContaining(["Waivers > Watchlist"]));
    expect(labels("draft center scouting")).toEqual(["Draft Center > Scouting"]);
  });

  it("opens the exact tab and keeps page matching", () => {
    const hit = searchNavDestinations(dests, "scouting").find((d) => d.label === "Draft Center > Scouting")!;
    expect(hit.path).toBe("/draft-center/L%201?name=My%20League&tab=scouting");
    expect(labels("draft")).toEqual(expect.arrayContaining(["Draft Center", "Draft Center > Picks"]));
  });

  it("finds Trade History only as the Trade Hub tab", () => {
    const history = labels("history");
    expect(history).toContain("Trade Hub > History");
    expect(history).not.toContain("Trade History");
  });

  it("inherits Pro from the page unless the tab overrides it", () => {
    const find = (q: string, label: string) => searchNavDestinations(dests, q).find((d) => d.label === label)!;
    expect(find("scouting", "Draft Center > Scouting").pro).toBe(true);
    expect(find("finder", "Trade Hub > Finder").pro).toBe(true);
    expect(find("analyzer", "Trade Hub > Analyzer").pro).toBeFalsy();
    expect(find("explore", "Waivers > Explore").pro).toBeFalsy();
  });

  it("has no tab rows without a league", () => {
    const nav = useNavDestinations(null, "");
    const noLeague = [...nav.generalDestinations, ...nav.accountDestinations];
    expect(labels("scouting", noLeague)).not.toContain("Draft Center > Scouting");
  });
});
